"""Keeps the model call behind one interface so it can be swapped
(CLAUDE.md section 4.3). Real usage: Anthropic Claude via the
provider-native SDK, through Pydantic AI's own model abstraction --
swapping providers means changing AGENT_MODEL, not code. Needs
ANTHROPIC_API_KEY set to actually call Claude; without one, only the
test suite (which uses Pydantic AI's own FunctionModel test double)
runs.
"""

from __future__ import annotations

import os

DEFAULT_MODEL = "anthropic:claude-sonnet-4-5"


def configured_model_name() -> str:
    return os.environ.get("AGENT_MODEL", DEFAULT_MODEL)
