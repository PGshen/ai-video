VOICE_ALIAS_MAP: dict[str, str] = {
    "male_calm": "zh_male_rap_M392_expressive",
    "female_warm": "zh_female_story_F271_expressive",
}


def resolve_speaker(alias: str) -> str:
    """Return fire speaker ID for alias; fall back to alias itself if not found."""
    return VOICE_ALIAS_MAP.get(alias, alias)
