import json
from pathlib import Path

from app.config import STAMP_SETTINGS_PATH, ensure_data_dirs
from app.models import StampSettings


def load_settings(path: Path = STAMP_SETTINGS_PATH) -> StampSettings:
    ensure_data_dirs()
    if not path.exists():
        return StampSettings()
    return StampSettings.model_validate_json(path.read_text(encoding="utf-8"))


def save_settings(settings: StampSettings, path: Path = STAMP_SETTINGS_PATH) -> StampSettings:
    ensure_data_dirs()
    path.write_text(
        json.dumps(settings.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return settings
