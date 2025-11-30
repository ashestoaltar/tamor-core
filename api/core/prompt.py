# core/prompt.py
from .config import personality, modes


def build_system_prompt(active_mode: str) -> str:
    mode_data = modes.get(active_mode, modes.get("Scholar", {}))

    name = personality.get("name", "Tamor")
    identity = personality.get(
        "identity", "Tamor is an aligned, steady, illuminating intelligence."
    )
    directives = personality.get("directives", [])
    tone = personality.get("tone", {})

    directives_text = "\n".join(f"- {d}" for d in directives) if directives else ""
    tone_text = ", ".join(f"{k}: {v}" for k, v in tone.items()) if tone else ""

    mode_label = mode_data.get("label", active_mode)
    mode_summary = mode_data.get("summary", "")
    mode_style = mode_data.get("style", "")
    mode_when = mode_data.get("when_to_use", "")
    mode_persona = mode_data.get("persona", "")

    system_prompt = f"""
You are {name}, a personal AI agent.

Identity:
{identity}

Global directives:
{directives_text}

Tone profile:
{tone_text}

Active mode: {mode_label}

Mode summary:
{mode_summary}

Mode style:
{mode_style}

When to use this mode:
{mode_when}

Mode persona (deep behavior spec):
{mode_persona}

General rules:
- Stay within the active mode's behavior and style unless the user explicitly asks to switch modes.
- Respect the user's values and constraints.
- Prefer clarity over cleverness. If you must make assumptions, state them briefly.
""".strip()

    return system_prompt
