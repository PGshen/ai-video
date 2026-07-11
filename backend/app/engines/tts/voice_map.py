VOICE_MAP_BY_ENGINE: dict[str, dict[str, str]] = {
    "doubao_1.0": {
        "sisi": "zh_female_shuangkuaisisi_moon_bigtts",
    },
    "doubao_2.0": {
        "xiaozhupeiqi": "zh_female_peiqi_uranus_bigtts",
        "xiaoxinjiejie": "zh_female_chunribu_uranus_bigtts",
        "zizi": "zh_female_qingchezizi_uranus_bigtts",
        "yunzhou": "zh_male_m191_uranus_bigtts",
        "xiaohe": "zh_female_xiaohe_uranus_bigtts",
    },
}


def resolve_speaker(alias: str, engine: str) -> str:
    """Resolve an alias and ensure its voice belongs to the selected TTS engine."""
    voices = VOICE_MAP_BY_ENGINE.get(engine)
    if voices is None:
        raise ValueError(f"Unsupported TTS engine: {engine}")
    try:
        return voices[alias]
    except KeyError as exc:
        raise ValueError(f"Voice {alias!r} is not available for {engine}") from exc
