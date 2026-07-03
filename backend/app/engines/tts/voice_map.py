VOICE_ALIAS_MAP: dict[str, str] = {
    "xiaozhupeiqi": "zh_female_peiqi_uranus_bigtts",
    "xiaoxinjiejie": "zh_female_chunribu_uranus_bigtts",
    "zizi": "zh_female_qingchezizi_uranus_bigtts",
    "yunzhou": "zh_male_m191_uranus_bigtts",
    "xiaohe": "zh_female_xiaohe_uranus_bigtts",
}


def resolve_speaker(alias: str) -> str:
    """Return fire speaker ID for alias; fall back to alias itself if not found."""
    return VOICE_ALIAS_MAP.get(alias, alias)
