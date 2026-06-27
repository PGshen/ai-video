VOICE_ALIAS_MAP: dict[str, str] = {
    "alloy": "zh_male_xionger_uranus_bigtts",
    "female_warm": "zh_female_story_F271_expressive",
}


def resolve_speaker(alias: str) -> str:
    """Return fire speaker ID for alias; fall back to alias itself if not found."""
    return VOICE_ALIAS_MAP.get(alias, alias)
