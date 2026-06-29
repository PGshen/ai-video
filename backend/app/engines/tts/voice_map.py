VOICE_ALIAS_MAP: dict[str, str] = {
    "alloy": "zh_male_xionger_uranus_bigtts",
    "nova": "zh_female_wenjingmaomao_uranus_bigtts",
    "echo": "zh_female_chunribu_uranus_bigtts",
}


def resolve_speaker(alias: str) -> str:
    """Return fire speaker ID for alias; fall back to alias itself if not found."""
    return VOICE_ALIAS_MAP.get(alias, alias)
