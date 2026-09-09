"""A scripted stand-in for the LLM, used in place of a real Anthropic API
call in tests (no live key available, and tests shouldn't hit a live
model regardless). This is Pydantic AI's own sanctioned test-double
mechanism (FunctionModel) -- not a fake of anything this repo owns.

Each "step" is a function of the message history so far, producing the
next ModelResponse (a tool call, or the final text). Scripts are
hand-written per test scenario to match exactly what a correctly-behaving
Claude, given the real system prompts in mission_agent.py, would do --
proving the agent's orchestration, the real MCP server, router, and fake
adapter work together, without needing a live model.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic_ai.messages import ModelMessage, ModelResponse, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

Step = Callable[[list[ModelMessage]], ModelResponse]


def last_tool_result(messages: list[ModelMessage], tool_name: str) -> Any:
    for message in reversed(messages):
        for part in getattr(message, "parts", []):
            if isinstance(part, ToolReturnPart) and part.tool_name == tool_name:
                return part.content
    raise LookupError(f"no tool result for {tool_name!r} in message history")


def scripted_model(steps: list[Step]) -> FunctionModel:
    index = {"i": 0}

    def run(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        step = steps[index["i"]]
        index["i"] += 1
        return step(messages)

    return FunctionModel(run)
