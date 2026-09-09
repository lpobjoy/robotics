"""CLAUDE.md section 6, step 6's acceptance tests: the agent takes a
released work order to Completed on the fake adapter, and the escalation
path is tested with a forced failure.

Real MCP server (subprocess, real stdio), real router, real fake
adapter, real EAM (background thread) -- only the "model" is a scripted
stand-in for Claude (see scripted_model.py for why).

The dispatch and supervise steps need two different Agent instances with
two different scripted models (the supervise script needs the real
mission_id, which is only known after dispatch actually runs), so these
tests build MissionAgent's pieces directly rather than through
build_mission_agent's single-model convenience wiring.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from agent.mission_agent import (
    EscalatedError,
    MissionAgent,
    build_dispatch_agent,
    build_supervise_agent,
    mcp_toolset,
)
from agent.state import MissionPhase, MissionStateStore
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from scripted_model import last_tool_result, scripted_model

Step = Callable[[list[ModelMessage]], ModelResponse]


def _release(eam_base_url: str, work_order_id: int) -> None:
    response = httpx.patch(
        f"{eam_base_url}/api/work-orders/{work_order_id}/status", json={"status": "Released"}
    )
    response.raise_for_status()


def _first_draft_work_order_id(eam_base_url: str) -> int:
    drafts = httpx.get(f"{eam_base_url}/api/work-orders", params={"status": "Draft"}).json()
    return int(drafts[0]["id"])


def _qualified_robot_id(eam_base_url: str, work_order_id: int) -> str:
    work_order = httpx.get(f"{eam_base_url}/api/work-orders/{work_order_id}").json()
    robots = httpx.get(f"{eam_base_url}/api/robots").json()
    required = set(work_order["required_capabilities"])
    return str(next(r["id"] for r in robots if required <= set(r["capabilities"])))


def _dispatch_steps(work_order_id: int) -> list[Step]:
    def step_qualify(messages: list[ModelMessage]) -> ModelResponse:
        return ModelResponse(
            parts=[ToolCallPart("qualify_robots", {"work_order_id": work_order_id})]
        )

    def step_dispatch(messages: list[ModelMessage]) -> ModelResponse:
        qualification = last_tool_result(messages, "qualify_robots")
        return ModelResponse(
            parts=[
                ToolCallPart(
                    "dispatch_mission",
                    {
                        "work_order_id": work_order_id,
                        "target_location_id": qualification["target_location_id"],
                        "required_capabilities": qualification["required_capabilities"],
                        "requested_by": "mission-agent",
                    },
                )
            ]
        )

    def step_mark_in_progress(messages: list[ModelMessage]) -> ModelResponse:
        return ModelResponse(
            parts=[ToolCallPart("mark_in_progress", {"work_order_id": work_order_id})]
        )

    def step_final(messages: list[ModelMessage]) -> ModelResponse:
        handle = last_tool_result(messages, "dispatch_mission")
        return ModelResponse(parts=[TextPart(f"DISPATCHED {handle['mission_id']}")])

    return [step_qualify, step_dispatch, step_mark_in_progress, step_final]


def _supervise_completed_steps(robot_id: str, mission_id: str, work_order_id: int) -> list[Step]:
    def step_advance(messages: list[ModelMessage]) -> ModelResponse:
        # Stands in for "wait for the real robot to finish" -- see
        # advance_fake_mission's docstring for why this exists.
        return ModelResponse(
            parts=[
                ToolCallPart(
                    "advance_fake_mission",
                    {"robot_id": robot_id, "mission_id": mission_id, "status": "completed"},
                )
            ]
        )

    def step_poll(messages: list[ModelMessage]) -> ModelResponse:
        return ModelResponse(
            parts=[ToolCallPart("get_mission_status", {"mission_id": mission_id})]
        )

    def step_mark_completed(messages: list[ModelMessage]) -> ModelResponse:
        status = last_tool_result(messages, "get_mission_status")
        assert status["status"] == "completed"
        return ModelResponse(
            parts=[ToolCallPart("mark_completed", {"work_order_id": work_order_id})]
        )

    def step_final(messages: list[ModelMessage]) -> ModelResponse:
        return ModelResponse(parts=[TextPart("COMPLETED")])

    return [step_advance, step_poll, step_mark_completed, step_final]


def _supervise_escalate_steps(robot_id: str, mission_id: str, work_order_id: int) -> list[Step]:
    def step_advance(messages: list[ModelMessage]) -> ModelResponse:
        return ModelResponse(
            parts=[
                ToolCallPart(
                    "advance_fake_mission",
                    {"robot_id": robot_id, "mission_id": mission_id, "status": "aborted"},
                )
            ]
        )

    def step_poll(messages: list[ModelMessage]) -> ModelResponse:
        return ModelResponse(
            parts=[ToolCallPart("get_mission_status", {"mission_id": mission_id})]
        )

    def step_escalate(messages: list[ModelMessage]) -> ModelResponse:
        status = last_tool_result(messages, "get_mission_status")
        assert status["status"] == "aborted"
        return ModelResponse(
            parts=[
                ToolCallPart(
                    "escalate_to_human",
                    {"work_order_id": work_order_id, "reason": "mission aborted mid-flight"},
                )
            ]
        )

    def step_final(messages: list[ModelMessage]) -> ModelResponse:
        return ModelResponse(parts=[TextPart("ESCALATED mission aborted mid-flight")])

    return [step_advance, step_poll, step_escalate, step_final]


@pytest.mark.anyio
async def test_agent_takes_a_released_work_order_to_completed(running_eam: str) -> None:
    work_order_id = _first_draft_work_order_id(running_eam)
    _release(running_eam, work_order_id)
    robot_id = _qualified_robot_id(running_eam, work_order_id)

    toolset = mcp_toolset(eam_base_url=running_eam)
    dispatch_agent = build_dispatch_agent(toolset, scripted_model(_dispatch_steps(work_order_id)))
    state_store = MissionStateStore(":memory:")
    mission_agent = MissionAgent(dispatch_agent, dispatch_agent, state_store)

    mission_id = await mission_agent._run_dispatch(work_order_id)

    mission_agent._supervise_agent = build_supervise_agent(
        toolset, scripted_model(_supervise_completed_steps(robot_id, mission_id, work_order_id))
    )
    outcome = await mission_agent._run_supervise(work_order_id, mission_id)

    assert outcome == "COMPLETED"
    final_status = httpx.get(f"{running_eam}/api/work-orders/{work_order_id}").json()["status"]
    assert final_status == "Completed"

    state = state_store.get(work_order_id)
    assert state is not None
    assert state.phase == MissionPhase.DONE


@pytest.mark.anyio
async def test_escalation_path_on_forced_failure(running_eam: str) -> None:
    work_order_id = _first_draft_work_order_id(running_eam)
    _release(running_eam, work_order_id)
    robot_id = _qualified_robot_id(running_eam, work_order_id)

    toolset = mcp_toolset(eam_base_url=running_eam)
    dispatch_agent = build_dispatch_agent(toolset, scripted_model(_dispatch_steps(work_order_id)))
    state_store = MissionStateStore(":memory:")
    mission_agent = MissionAgent(dispatch_agent, dispatch_agent, state_store)

    mission_id = await mission_agent._run_dispatch(work_order_id)

    mission_agent._supervise_agent = build_supervise_agent(
        toolset, scripted_model(_supervise_escalate_steps(robot_id, mission_id, work_order_id))
    )

    with pytest.raises(EscalatedError):
        await mission_agent._run_supervise(work_order_id, mission_id)

    final_status = httpx.get(f"{running_eam}/api/work-orders/{work_order_id}").json()["status"]
    assert final_status == "AwaitingHuman"

    state = state_store.get(work_order_id)
    assert state is not None
    assert state.phase == MissionPhase.AWAITING_HUMAN


@pytest.mark.anyio
async def test_resumes_after_restart_without_redispatching(
    running_eam: str, tmp_path: object
) -> None:
    """CLAUDE.md section 4.3: 'the agent must survive its own restart
    mid-mission. Persist mission state; resume from it.' Simulates that
    by dispatching with one MissionAgent, discarding it, then building a
    brand new MissionAgent (new state store re-reading the same file,
    new dispatch/supervise Agent objects) sharing the same underlying
    toolset -- the same "mcp_server stayed up" scenario the resume
    mechanism actually targets, per state.py's module docstring. The new
    agent's dispatch model raises if called at all, proving it resumed
    straight into supervise instead of dispatching a duplicate mission.
    """
    work_order_id = _first_draft_work_order_id(running_eam)
    _release(running_eam, work_order_id)
    robot_id = _qualified_robot_id(running_eam, work_order_id)
    state_path = f"{tmp_path}/mission_state.db"

    toolset = mcp_toolset(eam_base_url=running_eam)

    first_state_store = MissionStateStore(state_path)
    first_dispatch_agent = build_dispatch_agent(
        toolset, scripted_model(_dispatch_steps(work_order_id))
    )
    first_agent = MissionAgent(first_dispatch_agent, first_dispatch_agent, first_state_store)
    mission_id = await first_agent._run_dispatch(work_order_id)
    first_state_store.close()

    def _must_not_be_called(messages: list[ModelMessage]) -> ModelResponse:
        raise AssertionError("dispatch was re-run after restart -- resume should have skipped it")

    second_state_store = MissionStateStore(state_path)
    second_dispatch_agent = build_dispatch_agent(toolset, scripted_model([_must_not_be_called]))
    second_supervise_agent = build_supervise_agent(
        toolset, scripted_model(_supervise_completed_steps(robot_id, mission_id, work_order_id))
    )
    second_agent = MissionAgent(second_dispatch_agent, second_supervise_agent, second_state_store)

    outcome = await second_agent.process_released_work_order(work_order_id)

    assert outcome == "COMPLETED"
    final_status = httpx.get(f"{running_eam}/api/work-orders/{work_order_id}").json()["status"]
    assert final_status == "Completed"
