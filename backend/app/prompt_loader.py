from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
SYSTEM_PROMPTS_DIR = PROMPTS_DIR / "system"
PLAYER_PROMPTS_DIR = PROMPTS_DIR / "players"
NARRATIVE_LENSES_DIR = PROMPTS_DIR / "narrative_lenses"


def _read_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def load_system_prompt(filename: str) -> str:
    return _read_markdown(SYSTEM_PROMPTS_DIR / filename)


def load_player_persona(player_name: str) -> str:
    return _read_markdown(PLAYER_PROMPTS_DIR / f"Player-{player_name}.md")


def load_narrative_lens(player_name: str) -> str:
    return _read_markdown(NARRATIVE_LENSES_DIR / f"Lens-{player_name}.md")
