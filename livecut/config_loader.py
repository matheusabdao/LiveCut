import json
import os
from pathlib import Path
from typing import Any, Dict


def _get_default_config() -> Dict[str, Any]:
    return {
        "clip": {
            "min_duration": 20,
            "max_duration": 50,
            "max_clips": 8,
            "pre_padding": 5,
            "post_padding": 3,
            "target_aspect_ratio": "16:9",
            "fallback_aspect_ratio": "16:9",
        },
        "audio": {
            "sample_rate": 16000,
            "volume_peak_threshold": 0.55,
            "peak_min_distance_seconds": 6,
            "silence_threshold_db": -40,
        },
        "transcription": {
            "whisper_model": "small",
            "language": "pt",
            "compute_type": "int8",
            "device": "cpu",
            "beam_size": 5,
        },
        "scoring": {
            "volume_weight": 0.35,
            "keyword_weight": 0.30,
            "speech_density_weight": 0.15,
            "excitement_words_weight": 0.20,
        },
        "keywords": [
            "caralho", "porra", "foda-se", "merda", "cu",
            "incrivel", "incrível", "impressionante", "uau", "wow",
            "nossa", "meu deus", "santo", "caraca",
            "ganhei", "perdi", "morri", "matei",
            "insano", "doido", "louco", "surreal",
            "melhor", "pior", "historico", "histórico",
            "veja isso", "olha so", "olha só", "presta atenção",
            "que isso", "que porra", "cacilda", "tá doido",
            "vamos", "bom demais", "ruim demais", "puta que pariu",
            "sacanagem", "brincadeira", "deixa eu ver", "olha aí",
        ],
        "paths": {
            "output_dir": "output",
            "temp_dir": "temp",
        },
        "ffmpeg": {
            "preset": "slow",
            "crf": 18,
            "audio_bitrate": "256k",
        },
    }


def _write_default_config(config_path: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    default_config = _get_default_config()
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(default_config, f, indent=4, ensure_ascii=False)


def load_config(config_path: str) -> Dict[str, Any]:
    path = Path(config_path)

    if not path.exists():
        _write_default_config(path)

    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)

    defaults = _get_default_config()
    merged = _deep_merge(defaults, config)

    return merged


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
