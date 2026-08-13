import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_SETTINGS = {
    "playground_url": "https://dashboard.bfl.ai/7f3cb5b5-a118-4d2e-bd83-14e0ce3c53ed/5a1c9613-7710-40dd-915f-33875651ba2e/playground",
    "email": "",
    "ratio": "16:9",
    "resolution": "hd",
    "fps": 24,
    "duration_target": 20.0,
    "keep_audio": True,
    "music_bed": False,
    "continuation": "i2v",
    "retries": 3,
    "headless": False,
    "output_dir": str(PROJECT_ROOT / "output"),
    "chrome_profile": str(PROJECT_ROOT / "chrome-profile"),
    "settings_file": str(PROJECT_ROOT / "settings.json"),
    "session_file": str(PROJECT_ROOT / "session.json"),
    "state_file": str(PROJECT_ROOT / "pipeline_state.json"),
    "prompts_file": str(PROJECT_ROOT / "prompts.txt"),
}

DIMENSIONS = {
    "hd": {"16:9": (1280, 720), "9:16": (720, 1280)},
    "fhd": {"16:9": (1920, 1080), "9:16": (1080, 1920)},
}


def load_settings():
    settings = dict(DEFAULT_SETTINGS)
    path = Path(settings["settings_file"])
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            settings.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS})
        except Exception:
            pass
    return settings


def save_settings(settings):
    path = Path(settings["settings_file"])
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {k: settings[k] for k in DEFAULT_SETTINGS if k in settings}
    payload["settings_file"] = str(path)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def output_dirs(settings):
    base = Path(settings["output_dir"])
    return {
        "clips": base / "clips",
        "normalized": base / "normalized",
        "frames": base / "frames",
        "audio": base / "audio",
    }


def target_dims(settings):
    return DIMENSIONS[settings.get("resolution", "hd")][settings.get("ratio", "16:9")]


def ensure_dirs(settings):
    dirs = output_dirs(settings)
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    Path(settings["chrome_profile"]).mkdir(parents=True, exist_ok=True)
    return dirs


def credible_user_agent():
    return ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")