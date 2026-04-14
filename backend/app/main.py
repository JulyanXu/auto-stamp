import shutil
import uuid
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path

import fitz
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import FRONTEND_DIST_DIR, PREVIEW_DIR, RESULT_DIR, STAMP_IMAGE_PATH, ensure_data_dirs
from app.converters import ConverterRegistry
from app.models import Job, JobFile, StampSettings, StampTemplate, TemplateCreate, TemplatesState
from app.settings_store import active_settings, create_template, load_settings, load_templates, save_settings, select_template
from app.stamping import stamp_pdf


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_data_dirs()
    yield


app = FastAPI(title="Auto-Stamp API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs: dict[str, Job] = {}
registry = ConverterRegistry()

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/converters")
def list_converters() -> dict:
    return {"converters": registry.describe()}


@app.post("/api/stamp-image")
async def upload_stamp_image(file: UploadFile = File(...)) -> dict:
    if file.content_type not in {"image/png", "application/octet-stream"} and not file.filename.lower().endswith(".png"):
        raise HTTPException(status_code=400, detail="Only transparent PNG stamp images are supported.")
    ensure_data_dirs()
    with STAMP_IMAGE_PATH.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    return {"stamp_image_url": "/api/stamp-image"}


@app.get("/api/stamp-image")
def get_stamp_image() -> FileResponse:
    if not STAMP_IMAGE_PATH.exists():
        raise HTTPException(status_code=404, detail="Stamp image has not been uploaded.")
    return FileResponse(STAMP_IMAGE_PATH, media_type="image/png")


@app.get("/api/stamp-settings", response_model=StampSettings)
def get_stamp_settings() -> StampSettings:
    return load_settings()


@app.put("/api/stamp-settings", response_model=StampSettings)
def put_stamp_settings(settings: StampSettings) -> StampSettings:
    return save_settings(settings)


@app.get("/api/templates", response_model=TemplatesState)
def get_templates() -> TemplatesState:
    return load_templates()


@app.post("/api/templates", response_model=StampTemplate)
def post_template(payload: TemplateCreate) -> StampTemplate:
    return create_template(payload)


@app.put("/api/templates/{template_id}/select", response_model=StampTemplate)
def put_active_template(template_id: str) -> StampTemplate:
    try:
        return select_template(template_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Template not found.") from exc


@app.post("/api/preview")
async def create_preview(file: UploadFile = File(...)) -> dict:
    ensure_data_dirs()
    preview_id = uuid.uuid4().hex
    work_dir = PREVIEW_DIR / preview_id
    work_dir.mkdir(parents=True, exist_ok=True)
    source = await _save_upload(file, work_dir)
    try:
        pdf = registry.convert(source, work_dir)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    pages = _pdf_pages(pdf)
    return {
        "preview_id": preview_id,
        "preview_url": f"/api/previews/{preview_id}/{pdf.name}",
        "page_count": len(pages),
        "pages": pages,
        "page_image_url": f"/api/previews/{preview_id}/pages/1.png",
    }


@app.get("/api/previews/{preview_id}/{filename}")
def get_preview(preview_id: str, filename: str) -> FileResponse:
    path = PREVIEW_DIR / preview_id / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Preview not found.")
    return FileResponse(path, media_type="application/pdf", filename=filename)


@app.get("/api/previews/{preview_id}/pages/{page_number}.png")
def get_preview_page_image(preview_id: str, page_number: int) -> FileResponse:
    preview_dir = PREVIEW_DIR / preview_id
    pdfs = sorted(preview_dir.glob("*.pdf"))
    if not pdfs:
        raise HTTPException(status_code=404, detail="Preview PDF not found.")
    image_path = preview_dir / f"page-{page_number}.png"
    if not image_path.exists():
        _render_pdf_page(pdfs[0], page_number, image_path)
    return FileResponse(image_path, media_type="image/png", filename=image_path.name)


@app.post("/api/jobs", response_model=Job)
async def create_job(background_tasks: BackgroundTasks, files: list[UploadFile] = File(...)) -> Job:
    ensure_data_dirs()
    if not STAMP_IMAGE_PATH.exists():
        raise HTTPException(status_code=400, detail="Upload a transparent PNG stamp image before creating jobs.")
    job_id = uuid.uuid4().hex
    job_dir = RESULT_DIR / job_id
    upload_dir = job_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    job_files: list[JobFile] = []
    saved_sources: list[tuple[str, Path]] = []
    for file in files:
        file_id = uuid.uuid4().hex
        source = await _save_upload(file, upload_dir, prefix=file_id)
        job_files.append(JobFile(id=file_id, original_name=file.filename, status="queued"))
        saved_sources.append((file_id, source))

    job = Job(id=job_id, status="queued", files=job_files)
    jobs[job_id] = job
    background_tasks.add_task(_process_job, job_id, saved_sources)
    return job


@app.get("/api/jobs/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@app.get("/api/jobs/{job_id}/files/{file_id}")
def download_job_file(job_id: str, file_id: str) -> FileResponse:
    job_dir = RESULT_DIR / job_id
    matches = list((job_dir / "outputs").glob(f"{file_id}-*.pdf"))
    if not matches:
        raise HTTPException(status_code=404, detail="Output file not found.")
    output = matches[0]
    return FileResponse(output, media_type="application/pdf", filename=output.name.split("-", 1)[1])


@app.get("/api/jobs/{job_id}/download.zip")
def download_job_zip(job_id: str) -> FileResponse:
    zip_path = RESULT_DIR / job_id / "results.zip"
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="ZIP result is not ready.")
    return FileResponse(zip_path, media_type="application/zip", filename=f"{job_id}.zip")


async def _save_upload(file: UploadFile, directory: Path, prefix: str | None = None) -> Path:
    safe_name = _safe_filename(file.filename or "upload")
    name = f"{prefix}-{safe_name}" if prefix else safe_name
    path = directory / name
    with path.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    return path


def _safe_filename(filename: str) -> str:
    cleaned = "".join(char for char in Path(filename).name if char not in {"/", "\\", "\0"})
    return cleaned or "upload"


def _pdf_pages(pdf: Path) -> list[dict]:
    document = fitz.open(pdf)
    try:
        return [
            {
                "page": index + 1,
                "width_mm": round(page.rect.width * 25.4 / 72, 2),
                "height_mm": round(page.rect.height * 25.4 / 72, 2),
            }
            for index, page in enumerate(document)
        ]
    finally:
        document.close()


def _render_pdf_page(pdf: Path, page_number: int, image_path: Path) -> Path:
    if page_number < 1:
        raise HTTPException(status_code=400, detail="Page number starts at 1.")
    document = fitz.open(pdf)
    try:
        if page_number > len(document):
            raise HTTPException(status_code=404, detail="Page not found.")
        page = document[page_number - 1]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.75, 1.75), alpha=False)
        pixmap.save(image_path)
    finally:
        document.close()
    return image_path


def _process_job(job_id: str, saved_sources: list[tuple[str, Path]]) -> None:
    job = jobs[job_id]
    job.status = "processing"
    settings = active_settings()
    output_dir = RESULT_DIR / job_id / "outputs"
    converted_dir = RESULT_DIR / job_id / "converted"
    output_dir.mkdir(parents=True, exist_ok=True)
    converted_dir.mkdir(parents=True, exist_ok=True)

    success_count = 0
    for file_id, source in saved_sources:
        item = next(file_item for file_item in job.files if file_item.id == file_id)
        item.status = "processing"
        try:
            pdf = registry.convert(source, converted_dir)
            output_name = f"{file_id}-{_output_pdf_name(source)}"
            output_pdf = output_dir / output_name
            stamp_pdf(pdf, STAMP_IMAGE_PATH, output_pdf, settings)
            item.status = "completed"
            item.download_url = f"/api/jobs/{job_id}/files/{file_id}"
            success_count += 1
        except Exception as exc:
            item.status = "failed"
            item.message = str(exc)

    if success_count:
        _write_zip(job_id, output_dir)
        job.zip_url = f"/api/jobs/{job_id}/download.zip"
    if success_count == len(saved_sources):
        job.status = "completed"
    elif success_count == 0:
        job.status = "failed"
    else:
        job.status = "partial_failed"


def _output_pdf_name(source: Path) -> str:
    original_name = source.name.split("-", 1)[1] if "-" in source.name else source.name
    return f"{Path(original_name).stem}.pdf"


def _write_zip(job_id: str, output_dir: Path) -> Path:
    zip_path = RESULT_DIR / job_id / "results.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for pdf in sorted(output_dir.glob("*.pdf")):
            archive.write(pdf, arcname=pdf.name.split("-", 1)[1])
    return zip_path


if FRONTEND_DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST_DIR, html=True), name="frontend")
