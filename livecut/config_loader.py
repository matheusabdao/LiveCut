import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from . import app_paths


def _get_default_config() -> Dict[str, Any]:
    return {
        "clip": {
            "min_duration_seconds": 20,
            "max_duration_seconds": 50,
            "max_clips": 8,
            "pre_padding_seconds": 5,
            "post_padding_seconds": 3,
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
        "excitement_words": [
            "caralho", "porra", "foda", "cu", "merda",
            "uau", "wow", "nossa", "caraca", "insano", "doido",
            "louco", "surreal", "incrivel", "impressionante",
            "cacilda", "sacanagem", "puta",
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


def _seed_config(config_path: Path, seed: Optional[Path]) -> None:
    """Create the user config from the bundled seed, falling back to defaults."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if seed is not None and seed.exists() and seed.resolve() != config_path.resolve():
        try:
            shutil.copyfile(seed, config_path)
            return
        except OSError:
            pass
    _write_default_config(config_path)


def _apply_runtime_paths(config: Dict[str, Any]) -> None:
    """Point output/temp to writable absolute folders when running packaged."""
    if not app_paths.is_frozen():
        return
    paths = config.setdefault("paths", {})
    output_dir = paths.get("output_dir")
    if not output_dir or not Path(output_dir).is_absolute():
        paths["output_dir"] = str(app_paths.default_output_dir())
    temp_dir = paths.get("temp_dir")
    if not temp_dir or not Path(temp_dir).is_absolute():
        paths["temp_dir"] = str(app_paths.default_temp_dir())


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    if config_path is None:
        path = app_paths.default_config_path()
        seed: Optional[Path] = app_paths.bundled_default_config()
    else:
        path = Path(config_path)
        seed = None

    if not path.exists():
        _seed_config(path, seed)

    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)

    defaults = _get_default_config()
    merged = _deep_merge(defaults, config)
    _apply_runtime_paths(merged)

    return merged


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
