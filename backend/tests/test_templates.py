from app.models import StampSettings, TemplateCreate
from app.settings_store import create_template, load_templates, select_template


def test_templates_can_be_created_listed_and_selected(tmp_path):
    templates_path = tmp_path / "templates.json"
    settings_path = tmp_path / "settings.json"
    payload = TemplateCreate(
        name="模板 1",
        settings=StampSettings(
            x_ratio=0.1,
            y_ratio=0.2,
            width_ratio=0.3,
            height_ratio=0.4,
            width_mm=42,
            height_mm=24,
            page_rule="first",
        )
    )

    created = create_template(payload, templates_path=templates_path, settings_path=settings_path)
    selected = select_template(created.id, templates_path=templates_path, settings_path=settings_path)
    listed = load_templates(templates_path)
    settings = StampSettings.model_validate_json(settings_path.read_text(encoding="utf-8"))

    assert selected.id == created.id
    assert listed.active_template_id == created.id
    assert any(template.name == "模板 1" for template in listed.templates)
    assert settings.page_rule == "first"
