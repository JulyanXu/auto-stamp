import json
import uuid
from pathlib import Path

from app.config import STAMP_SETTINGS_PATH, TEMPLATES_PATH, ensure_data_dirs
from app.models import StampSettings, StampTemplate, TemplateCreate, TemplatesState


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


def load_templates(path: Path = TEMPLATES_PATH) -> TemplatesState:
    ensure_data_dirs()
    if not path.exists():
        return TemplatesState()
    return TemplatesState.model_validate_json(path.read_text(encoding="utf-8"))


def save_templates(state: TemplatesState, path: Path = TEMPLATES_PATH) -> TemplatesState:
    ensure_data_dirs()
    path.write_text(
        json.dumps(state.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return state


def create_template(
    payload: TemplateCreate,
    templates_path: Path = TEMPLATES_PATH,
    settings_path: Path = STAMP_SETTINGS_PATH,
) -> StampTemplate:
    state = load_templates(templates_path)
    template = StampTemplate(id=uuid.uuid4().hex, name=payload.name.strip() or "未命名模板", settings=payload.settings)
    state.templates.append(template)
    state.active_template_id = template.id
    save_templates(state, templates_path)
    save_settings(template.settings, settings_path)
    return template


def select_template(
    template_id: str,
    templates_path: Path = TEMPLATES_PATH,
    settings_path: Path = STAMP_SETTINGS_PATH,
) -> StampTemplate:
    state = load_templates(templates_path)
    for template in state.templates:
        if template.id == template_id:
            state.active_template_id = template.id
            save_templates(state, templates_path)
            save_settings(template.settings, settings_path)
            return template
    raise KeyError(template_id)


def active_settings() -> StampSettings:
    state = load_templates()
    for template in state.templates:
        if template.id == state.active_template_id:
            return template.settings
    return load_settings()
