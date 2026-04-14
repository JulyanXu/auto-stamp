# Auto-Stamp

Auto-Stamp 是一个轻量 WebUI，用于把 PDF 或可转换的 Office 文件批量盖章并输出 PDF。

## 能力边界

- 盖章只发生在 PDF 上。
- PDF 输入会直接进入盖章流程。
- Word、Excel、PowerPoint 等文件需要运行环境提供可用转换器。
- 应用本体不强制内置 LibreOffice。当前支持检测/调用：
  - PDF passthrough
  - LibreOffice headless
  - macOS Office/iWork AppleScript 适配器
  - Windows Microsoft Office COM 导出适配器（需要本机已安装 Word/Excel/PowerPoint）
  - `AUTOSTAMP_EXTERNAL_CONVERTER` 外部命令适配器

外部命令示例：

```bash
export AUTOSTAMP_EXTERNAL_CONVERTER='your-converter --input "{input}" --output "{output}"'
```

## 本地开发

安装后端依赖：

```bash
cd backend
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

安装前端依赖并启动：

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 `http://localhost:5173`。

## 生产运行

构建前端：

```bash
cd frontend
npm install
npm run build
```

启动后端：

```bash
cd backend
python -m pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

构建后的前端会由 FastAPI 直接托管，访问 `http://localhost:8000`。

## 使用流程

1. 上传透明 PNG 印章。
2. 上传样本文档生成 PDF 预览。
3. 在预览中拖拽盖章位置，拖右下角调整大小。
4. 选择盖章页规则：全部、首页、尾页或指定页/范围。
5. 保存默认模板。
6. 批量上传文件，下载单个 PDF 或 ZIP 包。

## 测试

```bash
cd backend
python -m pytest

cd ../frontend
npm run build
```
