from pydantic import BaseModel, Field


class StampSettings(BaseModel):
    x_ratio: float = Field(default=0.65, ge=0, le=1)
    y_ratio: float = Field(default=0.68, ge=0, le=1)
    width_ratio: float = Field(default=0.18, gt=0, le=1)
    height_ratio: float = Field(default=0.18, gt=0, le=1)
    width_mm: float | None = Field(default=None, gt=0)
    height_mm: float | None = Field(default=None, gt=0)
    page_rule: str = "all"


class JobFile(BaseModel):
    id: str
    original_name: str
    status: str
    message: str | None = None
    download_url: str | None = None


class Job(BaseModel):
    id: str
    status: str
    files: list[JobFile]
    zip_url: str | None = None


class StampTemplate(BaseModel):
    id: str
    name: str
    settings: StampSettings


class TemplatesState(BaseModel):
    active_template_id: str | None = None
    templates: list[StampTemplate] = []


class TemplateCreate(BaseModel):
    name: str
    settings: StampSettings
