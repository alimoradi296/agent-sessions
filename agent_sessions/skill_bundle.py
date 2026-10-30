"""Read the packaged continuation skill without changing agent configuration."""

from importlib.resources import files


def continuation_skill():
    return files('agent_sessions').joinpath('skills').joinpath('agent-sessions-continuation').joinpath('SKILL.md').read_text(encoding='utf-8')
