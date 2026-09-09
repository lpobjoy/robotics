"""The canonical fleet telemetry topic scheme (CLAUDE.md section 4.6):
`fleet/<robot_id>/state`, `.../images`, `.../events`.
"""

from __future__ import annotations


def state_topic(robot_id: str) -> str:
    return f"fleet/{robot_id}/state"


def images_topic(robot_id: str) -> str:
    return f"fleet/{robot_id}/images"


def events_topic(robot_id: str) -> str:
    return f"fleet/{robot_id}/events"


STATE_WILDCARD = "fleet/+/state"
IMAGES_WILDCARD = "fleet/+/images"
EVENTS_WILDCARD = "fleet/+/events"


def robot_id_from_topic(topic: str) -> str:
    return topic.split("/")[1]
