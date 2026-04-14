import { ChangeEvent, PointerEvent, useEffect, useMemo, useRef, useState } from "react";

type Converter = {
  name: string;
  label: string;
  available: boolean;
  supported_extensions: string[];
  unavailable_reason: string | null;
};

type StampSettings = {
  x_ratio: number;
  y_ratio: number;
  width_ratio: number;
  height_ratio: number;
  width_mm?: number | null;
  height_mm?: number | null;
  page_rule: string;
};

type JobFile = {
  id: string;
  original_name: string;
  status: string;
  message?: string | null;
  download_url?: string | null;
};

type Job = {
  id: string;
  status: string;
  files: JobFile[];
  zip_url?: string | null;
};

type Preview = {
  preview_id: string;
  preview_url: string;
  page_count: number;
  pages: Array<{ page: number; width_mm: number; height_mm: number }>;
  page_image_url: string;
};

type StampTemplate = {
  id: string;
  name: string;
  settings: StampSettings;
};

type TemplatesState = {
  active_template_id: string | null;
  templates: StampTemplate[];
};

const defaultSettings: StampSettings = {
  x_ratio: 0.65,
  y_ratio: 0.68,
  width_ratio: 0.18,
  height_ratio: 0.18,
  width_mm: 40,
  height_mm: 40,
  page_rule: "all"
};

const api = {
  async json<T>(url: string, init?: RequestInit): Promise<T> {
    const response = await fetch(url, init);
    if (!response.ok) {
      const detail = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(detail.detail || "请求失败");
    }
    return response.json();
  }
};

export default function App() {
  const [converters, setConverters] = useState<Converter[]>([]);
  const [settings, setSettings] = useState<StampSettings>(defaultSettings);
  const [stampVersion, setStampVersion] = useState(0);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewPage, setPreviewPage] = useState(1);
  const [message, setMessage] = useState("上传透明 PNG 印章，然后用样本文档定位盖章区域。");
  const [job, setJob] = useState<Job | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [batchFiles, setBatchFiles] = useState<File[]>([]);
  const [isCreatingJob, setIsCreatingJob] = useState(false);
  const [templates, setTemplates] = useState<StampTemplate[]>([]);
  const [activeTemplateId, setActiveTemplateId] = useState<string | null>(null);
  const [templateName, setTemplateName] = useState("模板 1");
  const [isSavingTemplate, setIsSavingTemplate] = useState(false);

  useEffect(() => {
    api.json<{ converters: Converter[] }>("/api/converters").then((data) => setConverters(data.converters));
    api.json<StampSettings>("/api/stamp-settings").then(setSettings);
    refreshTemplates(true);
  }, []);

  useEffect(() => {
    if (!job || ["completed", "failed", "partial_failed"].includes(job.status)) {
      return;
    }
    const timer = window.setInterval(async () => {
      const next = await api.json<Job>(`/api/jobs/${job.id}`);
      setJob(next);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [job]);

  const availableFormats = useMemo(() => {
    const formats = new Set<string>();
    converters.filter((item) => item.available).forEach((item) => item.supported_extensions.forEach((ext) => formats.add(ext)));
    return Array.from(formats).sort().join(", ");
  }, [converters]);

  async function uploadStamp(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const form = new FormData();
      form.append("file", file);
      await api.json("/api/stamp-image", { method: "POST", body: form });
      setStampVersion((value) => value + 1);
      setMessage("印章已更新。上传样本文档后可拖拽设置默认位置。");
    } catch (err) {
      setMessage(`印章上传失败：${err instanceof Error ? err.message : "未知错误"}`);
    }
  }

  async function uploadPreview(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setMessage(`正在转换 ${file.name}，请稍候...`);
    const form = new FormData();
    form.append("file", file);
    try {
      const data = await api.json<Preview>("/api/preview", { method: "POST", body: form });
      setPreview(data);
      setPreviewPage(1);
      setMessage("预览已生成。选择要查看的页面，拖动红章调整位置，拖右下角调整大小。");
    } catch (err) {
      setMessage(`转换失败：${err instanceof Error ? err.message : "未知错误"}`);
    }
  }

  async function saveSettings() {
    setIsSaving(true);
    try {
      const saved = await api.json<StampSettings>("/api/stamp-settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings)
      });
      setSettings(saved);
      setMessage("默认盖章模板已保存。");
    } finally {
      setIsSaving(false);
    }
  }

  async function saveTemplate() {
    setIsSavingTemplate(true);
    try {
      const created = await api.json<StampTemplate>("/api/templates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: templateName, settings })
      });
      await refreshTemplates(false);
      setActiveTemplateId(created.id);
      setSettings(created.settings);
      setTemplateName(created.name);
      setMessage(`已保存并启用模板：${created.name}`);
    } catch (err) {
      setMessage(`保存模板失败：${err instanceof Error ? err.message : "未知错误"}`);
    } finally {
      setIsSavingTemplate(false);
    }
  }

  async function selectTemplate(templateId: string) {
    if (!templateId) return;
    const selected = await api.json<StampTemplate>(`/api/templates/${templateId}/select`, { method: "PUT" });
    setActiveTemplateId(selected.id);
    setSettings(selected.settings);
    setTemplateName(selected.name);
    setMessage(`已切换到模板：${selected.name}`);
  }

  async function refreshTemplates(applyActive: boolean) {
    const data = await api.json<TemplatesState>("/api/templates");
    setTemplates(data.templates);
    setActiveTemplateId(data.active_template_id);
    const active = data.templates.find((template) => template.id === data.active_template_id);
    if (applyActive && active) {
      setSettings(active.settings);
      setTemplateName(active.name);
    }
  }

  function updateStampSize(field: "width_mm" | "height_mm", value: string) {
    const next = Number(value);
    setSettings({
      ...settings,
      [field]: Number.isFinite(next) && next > 0 ? next : null
    });
  }

  function selectBatchFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    setBatchFiles(files);
    if (files.length) {
      setMessage(`已选择 ${files.length} 个文件。点击“批量盖章”开始处理。`);
    }
  }

  async function createJob() {
    const files = batchFiles;
    if (!files.length) return;
    setIsCreatingJob(true);
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    try {
      const created = await api.json<Job>("/api/jobs", { method: "POST", body: form });
      setJob(created);
      setMessage("批量作业已创建，正在转换和盖章。");
    } catch (err) {
      setMessage(`创建作业失败：${err instanceof Error ? err.message : "未知错误"}`);
    } finally {
      setIsCreatingJob(false);
    }
  }

  return (
    <main>
      <header className="topbar">
        <div>
          <p className="eyebrow">Auto-Stamp</p>
          <h1>批量固化 PDF，再统一盖章</h1>
        </div>
        <div className="status-pill">{availableFormats || ".pdf"}</div>
      </header>

      <section className="template-ribbon">
        <div>
          <strong>当前批量盖章模板</strong>
          <span>{templates.find((template) => template.id === activeTemplateId)?.name ?? "未选择模板"}</span>
        </div>
        <label>
          选择保存好的默认模板
          <select value={activeTemplateId ?? ""} onChange={(event) => selectTemplate(event.target.value)}>
            <option value="">未选择模板</option>
            {templates.map((template) => (
              <option value={template.id} key={template.id}>
                {template.name}
              </option>
            ))}
          </select>
        </label>
      </section>

      <section className="workspace">
        <aside className="settings-panel">
          <section>
            <h2>默认印章</h2>
            <p>使用透明 PNG，盖章效果会直接叠加在 PDF 页面上。</p>
            <label className="file-action">
              上传印章 PNG
              <input id="stamp-upload" type="file" accept="image/png" onChange={uploadStamp} />
            </label>
            <div className="stamp-sample">
              <img src={`/api/stamp-image?t=${stampVersion}`} alt="当前印章" onError={(event) => (event.currentTarget.style.display = "none")} />
            </div>
          </section>

          <section>
            <h2>样本文档</h2>
            <p>先转换成 PDF 预览，再保存默认盖章位置。</p>
            <label className="file-action">
              上传样本文档
              <input id="preview-upload" type="file" onChange={uploadPreview} />
            </label>
          </section>

          <section>
            <h2>默认模板管理</h2>
            <p>保存多个默认模板，批量盖章会使用当前启用的模板。</p>
            <label className="field-label">
              选择保存好的默认模板（批量盖章使用）
            </label>
            <select value={activeTemplateId ?? ""} onChange={(event) => selectTemplate(event.target.value)}>
              <option value="">未选择模板</option>
              {templates.map((template) => (
                <option value={template.id} key={template.id}>
                  {template.name}
                </option>
              ))}
            </select>
            <div className="active-template">
              当前模板：{templates.find((template) => template.id === activeTemplateId)?.name ?? "未选择"}
            </div>
            <label className="field-label">
              保存当前设置为新模板
            </label>
            <input
              className="rule-input"
              value={templateName}
              onChange={(event) => setTemplateName(event.target.value)}
              placeholder="模板名称，例如：合同首页章"
            />
            <button onClick={saveTemplate} disabled={isSavingTemplate}>
              {isSavingTemplate ? "保存中..." : "保存为模板"}
            </button>
          </section>

          <section>
            <h2>页面规则</h2>
            <select value={settings.page_rule} onChange={(event) => setSettings({ ...settings, page_rule: event.target.value })}>
              <option value="all">全部页面</option>
              <option value="first">首页</option>
              <option value="last">尾页</option>
              <option value="1">指定页：第 1 页</option>
            </select>
            <input
              className="rule-input"
              value={settings.page_rule}
              onChange={(event) => setSettings({ ...settings, page_rule: event.target.value })}
              placeholder="例如 1,3,5 或 2-4"
            />
            <button onClick={saveSettings} disabled={isSaving}>{isSaving ? "保存中..." : "保存默认模板"}</button>
          </section>

          <section>
            <h2>印章大小</h2>
            <p>用毫米固定输出大小，批量盖章时不会随页面尺寸自动变大或变小。</p>
            <div className="size-grid">
              <label>
                宽度 mm
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={settings.width_mm ?? ""}
                  onChange={(event) => updateStampSize("width_mm", event.target.value)}
                />
              </label>
              <label>
                高度 mm
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={settings.height_mm ?? ""}
                  onChange={(event) => updateStampSize("height_mm", event.target.value)}
                />
              </label>
            </div>
          </section>
        </aside>

        <section className="preview-panel">
          <div className="preview-header">
            <div>
              <h2>PDF 预览定位</h2>
              <p>{message}</p>
            </div>
            {preview && (
              <label className="page-picker">
                预览页
                <select value={previewPage} onChange={(event) => setPreviewPage(Number(event.target.value))}>
                  {Array.from({ length: preview.page_count }, (_, index) => index + 1).map((page) => (
                    <option value={page} key={page}>
                      第 {page} 页
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
          <PdfPreview
            preview={preview}
            previewPage={previewPage}
            settings={settings}
            onChange={setSettings}
            stampUrl={`/api/stamp-image?t=${stampVersion}`}
          />
        </section>
      </section>

      <section className="batch-panel">
        <div>
          <h2>批量处理</h2>
          <p>上传文件后逐个转换为 PDF 并盖章；失败文件不会阻塞其他文件。</p>
        </div>
        <div className="batch-template">
          <label className="field-label">使用保存好的默认模板</label>
          <select value={activeTemplateId ?? ""} onChange={(event) => selectTemplate(event.target.value)}>
            <option value="">未选择模板</option>
            {templates.map((template) => (
              <option value={template.id} key={template.id}>
                {template.name}
              </option>
            ))}
          </select>
          <span>当前模板：{templates.find((template) => template.id === activeTemplateId)?.name ?? "未选择"}</span>
        </div>
        <label className="file-action primary">
          选择批量文件
          <input id="batch-upload" type="file" multiple onChange={selectBatchFiles} />
        </label>
        <button className="stamp-button" onClick={createJob} disabled={!batchFiles.length || isCreatingJob}>
          {isCreatingJob ? "处理中..." : "批量盖章"}
        </button>
        {batchFiles.length > 0 && (
          <div className="selected-files">
            <strong>已选择 {batchFiles.length} 个文件</strong>
            <span>{batchFiles.map((file) => file.name).join("、")}</span>
          </div>
        )}
        {job && <JobStatus job={job} />}
      </section>
    </main>
  );
}

function PdfPreview({
  preview,
  previewPage,
  settings,
  stampUrl,
  onChange
}: {
  preview: Preview | null;
  previewPage: number;
  settings: StampSettings;
  stampUrl: string;
  onChange: (settings: StampSettings) => void;
}) {
  const frameRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ mode: "move" | "resize"; startX: number; startY: number; settings: StampSettings } | null>(null);
  const selectedPage = preview?.pages.find((page) => page.page === previewPage) ?? null;

  function startDrag(mode: "move" | "resize", event: PointerEvent) {
    event.preventDefault();
    dragRef.current = { mode, startX: event.clientX, startY: event.clientY, settings };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function onPointerMove(event: PointerEvent) {
    if (!dragRef.current || !frameRef.current) return;
    const bounds = frameRef.current.getBoundingClientRect();
    const dx = (event.clientX - dragRef.current.startX) / bounds.width;
    const dy = (event.clientY - dragRef.current.startY) / bounds.height;
    if (dragRef.current.mode === "move") {
      onChange({
        ...settings,
        x_ratio: clamp(dragRef.current.settings.x_ratio + dx, 0, 0.95),
        y_ratio: clamp(dragRef.current.settings.y_ratio + dy, 0, 0.95)
      });
    } else {
      const widthRatio = clamp(dragRef.current.settings.width_ratio + dx, 0.04, 0.8);
      const heightRatio = clamp(dragRef.current.settings.height_ratio + dy, 0.04, 0.8);
      onChange({
        ...settings,
        width_ratio: widthRatio,
        height_ratio: heightRatio,
        width_mm: selectedPage ? Math.round(widthRatio * selectedPage.width_mm * 10) / 10 : settings.width_mm,
        height_mm: selectedPage ? Math.round(heightRatio * selectedPage.height_mm * 10) / 10 : settings.height_mm
      });
    }
  }

  const overlayWidth = settings.width_mm && selectedPage
    ? `${(settings.width_mm / selectedPage.width_mm) * 100}%`
    : `${settings.width_ratio * 100}%`;
  const overlayHeight = settings.height_mm && selectedPage
    ? `${(settings.height_mm / selectedPage.height_mm) * 100}%`
    : `${settings.height_ratio * 100}%`;

  return (
    <div className="pdf-stage">
      {preview ? (
        <>
          <div className="preview-loaded">PDF 第 {previewPage} 页已加载，可拖动印章定位。</div>
          <div
            className="page-canvas"
            ref={frameRef}
            onPointerMove={onPointerMove}
            onPointerUp={() => (dragRef.current = null)}
            onPointerCancel={() => (dragRef.current = null)}
          >
            <img
              className="page-image"
              src={`/api/previews/${preview.preview_id}/pages/${previewPage}.png?t=${Date.now()}`}
              alt={`第 ${previewPage} 页预览`}
              draggable={false}
            />
            <div
              className="stamp-overlay"
              style={{
                left: `${settings.x_ratio * 100}%`,
                top: `${settings.y_ratio * 100}%`,
                width: overlayWidth,
                height: overlayHeight
              }}
              onPointerDown={(event) => startDrag("move", event)}
            >
              <img src={stampUrl} alt="盖章位置" draggable={false} />
              <span onPointerDown={(event) => startDrag("resize", event)} />
            </div>
          </div>
        </>
      ) : (
        <div className="empty-preview" role="status">请先点击“上传样本文档”，这里会显示可定位的 PDF 单页预览</div>
      )}
    </div>
  );
}

function JobStatus({ job }: { job: Job }) {
  return (
    <div className="job-status">
      <div className="job-summary">
        <strong>作业 {job.status}</strong>
        {job.zip_url && <a href={job.zip_url}>下载 ZIP</a>}
      </div>
      <div className="job-list">
        {job.files.map((file) => (
          <div className="job-row" key={file.id}>
            <span>{file.original_name}</span>
            <small>{file.status}</small>
            {file.message && <em>{file.message}</em>}
            {file.download_url && <a href={file.download_url}>下载 PDF</a>}
          </div>
        ))}
      </div>
    </div>
  );
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}
