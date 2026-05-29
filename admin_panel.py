from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import mimetypes
import os

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from openai import OpenAIError
from pydantic import BaseModel

from connectors.aisearch import AISearch


BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGEBASE_DIR = BASE_DIR / "knowledgebase"
DOCUMENTS_DIR = KNOWLEDGEBASE_DIR / "documents"
PROMPT_ROOT = BASE_DIR / "orc"
INDEX_FILE = KNOWLEDGEBASE_DIR / "index.faiss"

ALLOWED_PROMPT_NAMES = {"skprompt.txt", "bot_description.prompt"}
TEXT_DOCUMENT_EXTENSIONS = {
    ".txt",
    ".md",
    ".json",
    ".csv",
    ".html",
    ".htm",
    ".xml",
    ".yaml",
    ".yml",
}


class PromptUpdateRequest(BaseModel):
    content: str


class DocumentUpdateRequest(BaseModel):
    content: str


router = APIRouter(tags=["admin"])


def _ensure_storage() -> None:
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)


def _isoformat(value: float | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _relative_prompt_id(path: Path) -> str:
    return path.relative_to(BASE_DIR).as_posix()


def _get_prompt_paths() -> list[Path]:
    prompt_paths = [PROMPT_ROOT / "bot_description.prompt"]
    prompt_paths.extend(sorted(PROMPT_ROOT.glob("plugins/**/skprompt.txt")))
    return [path for path in prompt_paths if path.exists()]


def _resolve_prompt_path(prompt_id: str) -> Path:
    prompt_path = (BASE_DIR / prompt_id).resolve()
    if not prompt_path.exists():
        raise HTTPException(status_code=404, detail="Prompt not found")
    if prompt_path.name not in ALLOWED_PROMPT_NAMES:
        raise HTTPException(status_code=400, detail="Unsupported prompt file")
    if not prompt_path.is_relative_to(BASE_DIR):
        raise HTTPException(status_code=400, detail="Invalid prompt path")
    return prompt_path


def _sanitize_document_name(name: str) -> str:
    candidate = Path(name).name.strip()
    if not candidate:
        raise HTTPException(status_code=400, detail="Document name is required")
    if Path(candidate).suffix.lower() not in TEXT_DOCUMENT_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported document type. Use a text-based file such as .txt, .md, .json, or .csv.",
        )
    return candidate


def _resolve_document_path(document_name: str) -> Path:
    safe_name = _sanitize_document_name(document_name)
    document_path = (DOCUMENTS_DIR / safe_name).resolve()
    if not document_path.is_relative_to(DOCUMENTS_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid document path")
    return document_path


def _read_text_document(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Document is not UTF-8 text: {path.name}") from exc


def _document_status(path: Path, index_mtime: float | None) -> str:
    if index_mtime is None:
        return "not_indexed"
    return "indexed" if path.stat().st_mtime <= index_mtime else "stale"


def _list_documents() -> list[dict[str, Any]]:
    _ensure_storage()
    index_mtime = INDEX_FILE.stat().st_mtime if INDEX_FILE.exists() else None
    documents = []
    for path in sorted(DOCUMENTS_DIR.iterdir()):
        if not path.is_file():
            continue
        stat = path.stat()
        documents.append(
            {
                "name": path.name,
                "content_type": mimetypes.guess_type(path.name)[0] or "text/plain",
                "size": stat.st_size,
                "updated_at": _isoformat(stat.st_mtime),
                "status": _document_status(path, index_mtime),
                "is_editable": path.suffix.lower() in TEXT_DOCUMENT_EXTENSIONS,
            }
        )
    return documents


def _knowledge_base_status() -> dict[str, Any]:
    _ensure_storage()
    index_mtime = INDEX_FILE.stat().st_mtime if INDEX_FILE.exists() else None
    return {
        "document_count": len(_list_documents()),
        "index_exists": INDEX_FILE.exists(),
        "last_refreshed_at": _isoformat(index_mtime),
    }


def _rebuild_knowledge_base() -> dict[str, Any]:
    _ensure_storage()
    documents = []
    indexed_files = []
    for path in sorted(DOCUMENTS_DIR.iterdir()):
        if not path.is_file():
            continue
        content = _read_text_document(path).strip()
        if not content:
            continue
        documents.append(f"Source: {path.name}\n\n{content}")
        indexed_files.append(path.name)

    search = AISearch(str(KNOWLEDGEBASE_DIR))
    search.setup_vector_store(documents)

    status = _knowledge_base_status()
    status["indexed_files"] = indexed_files
    return status


@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_page() -> HTMLResponse:
    return HTMLResponse(ADMIN_PAGE_HTML)


@router.get("/admin/api/prompts")
async def list_prompts() -> dict[str, Any]:
    prompts = []
    for path in _get_prompt_paths():
        prompts.append(
            {
                "id": _relative_prompt_id(path),
                "name": path.parent.name if path.name == "skprompt.txt" else path.name,
                "path": _relative_prompt_id(path),
                "updated_at": _isoformat(path.stat().st_mtime),
            }
        )
    return {"items": prompts}


@router.get("/admin/api/prompts/{prompt_id:path}")
async def get_prompt(prompt_id: str) -> dict[str, Any]:
    prompt_path = _resolve_prompt_path(prompt_id)
    return {
        "id": _relative_prompt_id(prompt_path),
        "name": prompt_path.parent.name if prompt_path.name == "skprompt.txt" else prompt_path.name,
        "path": _relative_prompt_id(prompt_path),
        "content": prompt_path.read_text(encoding="utf-8"),
        "updated_at": _isoformat(prompt_path.stat().st_mtime),
    }


@router.put("/admin/api/prompts/{prompt_id:path}")
async def update_prompt(prompt_id: str, payload: PromptUpdateRequest) -> dict[str, Any]:
    prompt_path = _resolve_prompt_path(prompt_id)
    prompt_path.write_text(payload.content, encoding="utf-8")
    return {
        "message": "Prompt saved",
        "id": _relative_prompt_id(prompt_path),
        "updated_at": _isoformat(prompt_path.stat().st_mtime),
    }


@router.get("/admin/api/knowledge-base/status")
async def knowledge_base_status() -> dict[str, Any]:
    return _knowledge_base_status()


@router.get("/admin/api/knowledge-base/documents")
async def list_knowledge_base_documents() -> dict[str, Any]:
    return {"items": _list_documents(), "status": _knowledge_base_status()}


@router.get("/admin/api/knowledge-base/documents/{document_name:path}")
async def get_knowledge_base_document(document_name: str) -> dict[str, Any]:
    document_path = _resolve_document_path(document_name)
    if not document_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "name": document_path.name,
        "content": _read_text_document(document_path),
        "updated_at": _isoformat(document_path.stat().st_mtime),
    }


@router.post("/admin/api/knowledge-base/documents")
async def upload_knowledge_base_document(file: UploadFile = File(...)) -> dict[str, Any]:
    _ensure_storage()
    document_path = _resolve_document_path(file.filename or "")
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Only UTF-8 text documents are supported") from exc
    document_path.write_text(text, encoding="utf-8")
    return {
        "message": "Document uploaded",
        "name": document_path.name,
        "updated_at": _isoformat(document_path.stat().st_mtime),
    }


@router.put("/admin/api/knowledge-base/documents/{document_name:path}")
async def update_knowledge_base_document(document_name: str, payload: DocumentUpdateRequest) -> dict[str, Any]:
    document_path = _resolve_document_path(document_name)
    if not document_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")
    document_path.write_text(payload.content, encoding="utf-8")
    return {
        "message": "Document updated",
        "name": document_path.name,
        "updated_at": _isoformat(document_path.stat().st_mtime),
    }


@router.delete("/admin/api/knowledge-base/documents/{document_name:path}")
async def delete_knowledge_base_document(document_name: str) -> dict[str, Any]:
    document_path = _resolve_document_path(document_name)
    if not document_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")
    os.remove(document_path)
    return {"message": "Document deleted", "name": document_path.name}


@router.post("/admin/api/knowledge-base/refresh")
async def refresh_knowledge_base() -> dict[str, Any]:
  try:
    status = _rebuild_knowledge_base()
  except OpenAIError as exc:
    raise HTTPException(
      status_code=400,
      detail="Knowledge base refresh requires a valid OPENAI_API_KEY for embeddings.",
    ) from exc
    return {"message": "Knowledge base refreshed", "status": status}


ADMIN_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>TeleCRMFlow Admin</title>
  <style>
    :root {
      --bg: #f4efe5;
      --surface: rgba(255, 252, 247, 0.92);
      --surface-strong: #fffaf2;
      --text: #182126;
      --muted: #5a6770;
      --accent: #0f766e;
      --accent-strong: #115e59;
      --accent-soft: #c9efe7;
      --warning: #b45309;
      --danger: #b91c1c;
      --border: rgba(24, 33, 38, 0.12);
      --shadow: 0 24px 80px rgba(24, 33, 38, 0.12);
      --radius: 22px;
      --font: "Avenir Next", "Segoe UI", sans-serif;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      font-family: var(--font);
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(15, 118, 110, 0.18), transparent 32%),
        radial-gradient(circle at top right, rgba(180, 83, 9, 0.14), transparent 28%),
        linear-gradient(160deg, #f6f1e7 0%, #eef5f0 50%, #edf4f8 100%);
      min-height: 100vh;
    }

    .shell {
      width: min(1400px, calc(100vw - 32px));
      margin: 24px auto;
      display: grid;
      gap: 20px;
    }

    .hero, .panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      backdrop-filter: blur(14px);
    }

    .hero {
      padding: 28px;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 24px;
      overflow: hidden;
      position: relative;
    }

    .hero::after {
      content: "";
      position: absolute;
      inset: auto -40px -40px auto;
      width: 220px;
      height: 220px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(15, 118, 110, 0.18), transparent 72%);
      pointer-events: none;
    }

    h1, h2, h3, p { margin: 0; }
    h1 { font-size: clamp(2rem, 5vw, 3.5rem); letter-spacing: -0.04em; }
    h2 { font-size: 1.15rem; }

    .hero p {
      margin-top: 10px;
      color: var(--muted);
      max-width: 720px;
      line-height: 1.5;
    }

    .status-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(150px, 1fr));
      gap: 14px;
      min-width: 320px;
    }

    .status-card {
      background: var(--surface-strong);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 16px;
    }

    .status-card span {
      display: block;
      color: var(--muted);
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 10px;
    }

    .status-card strong {
      font-size: 1.5rem;
      display: block;
    }

    .grid {
      display: grid;
      grid-template-columns: 1.05fr 1fr;
      gap: 20px;
    }

    .panel {
      padding: 22px;
      display: grid;
      gap: 18px;
    }

    .panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
    }

    .panel-header p {
      color: var(--muted);
      margin-top: 6px;
      line-height: 1.45;
    }

    .split {
      display: grid;
      grid-template-columns: 280px minmax(0, 1fr);
      gap: 16px;
      min-height: 520px;
    }

    .list-box {
      border: 1px solid var(--border);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.5);
      overflow: auto;
    }

    .list-item {
      padding: 14px 16px;
      border-bottom: 1px solid var(--border);
      cursor: pointer;
      transition: background 0.2s ease, transform 0.2s ease;
    }

    .list-item:last-child { border-bottom: none; }
    .list-item:hover { background: rgba(15, 118, 110, 0.08); }
    .list-item.active {
      background: linear-gradient(135deg, rgba(15, 118, 110, 0.16), rgba(201, 239, 231, 0.65));
      transform: translateX(4px);
    }

    .list-item strong {
      display: block;
      font-size: 0.96rem;
      margin-bottom: 4px;
    }

    .list-item small {
      display: block;
      color: var(--muted);
      line-height: 1.4;
    }

    textarea, input[type="text"], input[type="file"] {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 14px 16px;
      font: inherit;
      color: var(--text);
      background: rgba(255, 255, 255, 0.72);
    }

    textarea {
      min-height: 390px;
      resize: vertical;
      font-family: "SFMono-Regular", "Menlo", monospace;
      line-height: 1.45;
    }

    .actions, .upload-row, .doc-actions {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      align-items: center;
    }

    button {
      border: none;
      border-radius: 999px;
      padding: 12px 18px;
      font: inherit;
      font-weight: 600;
      cursor: pointer;
      transition: transform 0.18s ease, opacity 0.18s ease, background 0.18s ease;
    }

    button:hover { transform: translateY(-1px); }
    button.primary { background: var(--accent); color: white; }
    button.primary:hover { background: var(--accent-strong); }
    button.secondary { background: rgba(24, 33, 38, 0.08); color: var(--text); }
    button.danger { background: rgba(185, 28, 28, 0.12); color: var(--danger); }

    .meta {
      color: var(--muted);
      font-size: 0.92rem;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 7px 12px;
      border-radius: 999px;
      background: rgba(15, 118, 110, 0.1);
      color: var(--accent-strong);
      font-size: 0.84rem;
      font-weight: 600;
    }

    .badge.stale {
      background: rgba(180, 83, 9, 0.14);
      color: var(--warning);
    }

    .status-line {
      min-height: 24px;
      color: var(--muted);
      font-size: 0.94rem;
    }

    .status-line.error { color: var(--danger); }
    .status-line.success { color: var(--accent-strong); }

    .document-panel {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr);
      gap: 16px;
      min-height: 520px;
    }

    .doc-editor {
      display: grid;
      gap: 12px;
      align-content: start;
    }

    .hint {
      font-size: 0.9rem;
      color: var(--muted);
      line-height: 1.4;
    }

    @media (max-width: 1100px) {
      .grid, .document-panel { grid-template-columns: 1fr; }
      .split { grid-template-columns: 1fr; min-height: 0; }
      .status-grid { min-width: 0; }
      .hero { flex-direction: column; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div>
        <h1>Admin Management</h1>
        <p>Update the live prompt files and maintain the source documents behind retrieval without editing Python code or shipping a new deployment.</p>
      </div>
      <div class="status-grid">
        <div class="status-card">
          <span>Prompt Files</span>
          <strong id="promptCount">0</strong>
        </div>
        <div class="status-card">
          <span>Knowledge Docs</span>
          <strong id="docCount">0</strong>
        </div>
        <div class="status-card">
          <span>Last Refresh</span>
          <strong id="lastRefresh">Never</strong>
        </div>
      </div>
    </section>

    <div class="grid">
      <section class="panel">
        <div class="panel-header">
          <div>
            <h2>Prompt Management</h2>
            <p>Edit the prompt files the orchestrator already reads from disk for each request.</p>
          </div>
          <button class="secondary" id="reloadPrompts">Reload</button>
        </div>

        <div class="split">
          <div class="list-box" id="promptList"></div>

          <div>
            <div class="actions">
              <span class="badge" id="promptPathBadge">Select a prompt</span>
              <span class="meta" id="promptUpdated"></span>
            </div>
            <textarea id="promptEditor" placeholder="Select a prompt to edit"></textarea>
            <div class="actions">
              <button class="primary" id="savePrompt">Save Prompt</button>
            </div>
            <div class="status-line" id="promptStatus"></div>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <h2>Knowledge Base Management</h2>
            <p>Manage editable knowledge documents and rebuild the FAISS store when content changes.</p>
          </div>
          <button class="primary" id="refreshKnowledgeBase">Refresh Index</button>
        </div>

        <div class="upload-row">
          <input type="file" id="documentUpload" accept=".txt,.md,.json,.csv,.html,.htm,.xml,.yaml,.yml" />
          <button class="secondary" id="uploadDocument">Upload Document</button>
        </div>
        <div class="hint">Supported formats: UTF-8 text files such as .txt, .md, .json, .csv, .html, .xml, .yaml.</div>

        <div class="document-panel">
          <div class="list-box" id="documentList"></div>

          <div class="doc-editor">
            <input type="text" id="documentName" placeholder="Document name" readonly />
            <textarea id="documentEditor" placeholder="Select a document to view or edit"></textarea>
            <div class="doc-actions">
              <button class="primary" id="saveDocument">Save Document</button>
              <button class="danger" id="deleteDocument">Delete Document</button>
            </div>
            <div class="status-line" id="documentStatus"></div>
          </div>
        </div>
      </section>
    </div>
  </div>

  <script>
    const state = {
      selectedPromptId: null,
      selectedDocument: null,
    };

    const promptList = document.getElementById('promptList');
    const promptEditor = document.getElementById('promptEditor');
    const promptPathBadge = document.getElementById('promptPathBadge');
    const promptUpdated = document.getElementById('promptUpdated');
    const promptStatus = document.getElementById('promptStatus');
    const promptCount = document.getElementById('promptCount');

    const documentList = document.getElementById('documentList');
    const documentName = document.getElementById('documentName');
    const documentEditor = document.getElementById('documentEditor');
    const documentStatus = document.getElementById('documentStatus');
    const docCount = document.getElementById('docCount');
    const lastRefresh = document.getElementById('lastRefresh');

    function setStatus(element, message, type = '') {
      element.textContent = message;
      element.className = `status-line ${type}`.trim();
    }

    function formatDate(value) {
      if (!value) {
        return 'Never';
      }
      return new Date(value).toLocaleString();
    }

    function renderPromptList(items) {
      promptCount.textContent = String(items.length);
      promptList.innerHTML = '';
      for (const item of items) {
        const row = document.createElement('div');
        row.className = `list-item ${state.selectedPromptId === item.id ? 'active' : ''}`.trim();
        row.innerHTML = `<strong>${item.name}</strong><small>${item.path}</small><small>Updated ${formatDate(item.updated_at)}</small>`;
        row.addEventListener('click', () => loadPrompt(item.id));
        promptList.appendChild(row);
      }
    }

    function renderDocumentList(items) {
      docCount.textContent = String(items.length);
      documentList.innerHTML = '';
      for (const item of items) {
        const row = document.createElement('div');
        row.className = `list-item ${state.selectedDocument === item.name ? 'active' : ''}`.trim();
        const badgeClass = item.status === 'stale' ? 'badge stale' : 'badge';
        row.innerHTML = `<strong>${item.name}</strong><small>${item.size} bytes</small><small>Updated ${formatDate(item.updated_at)}</small><div class="${badgeClass}">${item.status}</div>`;
        row.addEventListener('click', () => loadDocument(item.name));
        documentList.appendChild(row);
      }
    }

    async function loadPrompts() {
      const response = await fetch('/admin/api/prompts');
      const data = await response.json();
      renderPromptList(data.items || []);
      if (!state.selectedPromptId && data.items && data.items.length > 0) {
        await loadPrompt(data.items[0].id);
      }
    }

    async function loadPrompt(id) {
      state.selectedPromptId = id;
      const response = await fetch(`/admin/api/prompts/${encodeURIComponent(id).replace(/%2F/g, '/')}`);
      const data = await response.json();
      promptPathBadge.textContent = data.path;
      promptUpdated.textContent = `Last updated ${formatDate(data.updated_at)}`;
      promptEditor.value = data.content;
      setStatus(promptStatus, '');
      await loadPrompts();
    }

    async function savePrompt() {
      if (!state.selectedPromptId) {
        setStatus(promptStatus, 'Select a prompt first.', 'error');
        return;
      }
      const response = await fetch(`/admin/api/prompts/${encodeURIComponent(state.selectedPromptId).replace(/%2F/g, '/')}` , {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: promptEditor.value }),
      });
      const data = await response.json();
      if (!response.ok) {
        setStatus(promptStatus, data.detail || 'Unable to save prompt.', 'error');
        return;
      }
      promptUpdated.textContent = `Last updated ${formatDate(data.updated_at)}`;
      setStatus(promptStatus, data.message, 'success');
      await loadPrompts();
    }

    async function loadKnowledgeBase() {
      const response = await fetch('/admin/api/knowledge-base/documents');
      const data = await response.json();
      renderDocumentList(data.items || []);
      docCount.textContent = String(data.status?.document_count || 0);
      lastRefresh.textContent = formatDate(data.status?.last_refreshed_at);
      if (!state.selectedDocument && data.items && data.items.length > 0) {
        await loadDocument(data.items[0].name);
      }
    }

    async function loadDocument(name) {
      state.selectedDocument = name;
      const response = await fetch(`/admin/api/knowledge-base/documents/${encodeURIComponent(name)}`);
      const data = await response.json();
      if (!response.ok) {
        setStatus(documentStatus, data.detail || 'Unable to load document.', 'error');
        return;
      }
      documentName.value = data.name;
      documentEditor.value = data.content;
      setStatus(documentStatus, '');
      await loadKnowledgeBase();
    }

    async function saveDocument() {
      if (!state.selectedDocument) {
        setStatus(documentStatus, 'Select a document first.', 'error');
        return;
      }
      const response = await fetch(`/admin/api/knowledge-base/documents/${encodeURIComponent(state.selectedDocument)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: documentEditor.value }),
      });
      const data = await response.json();
      if (!response.ok) {
        setStatus(documentStatus, data.detail || 'Unable to save document.', 'error');
        return;
      }
      setStatus(documentStatus, `${data.message}. Refresh the index to apply it to search.`, 'success');
      await loadKnowledgeBase();
    }

    async function deleteDocument() {
      if (!state.selectedDocument) {
        setStatus(documentStatus, 'Select a document first.', 'error');
        return;
      }
      const confirmed = window.confirm(`Delete ${state.selectedDocument}?`);
      if (!confirmed) {
        return;
      }
      const response = await fetch(`/admin/api/knowledge-base/documents/${encodeURIComponent(state.selectedDocument)}`, {
        method: 'DELETE',
      });
      const data = await response.json();
      if (!response.ok) {
        setStatus(documentStatus, data.detail || 'Unable to delete document.', 'error');
        return;
      }
      documentName.value = '';
      documentEditor.value = '';
      state.selectedDocument = null;
      setStatus(documentStatus, `${data.message}. Refresh the index to remove it from search.`, 'success');
      await loadKnowledgeBase();
    }

    async function uploadDocument() {
      const input = document.getElementById('documentUpload');
      const file = input.files && input.files[0];
      if (!file) {
        setStatus(documentStatus, 'Choose a document to upload.', 'error');
        return;
      }
      const formData = new FormData();
      formData.append('file', file);
      const response = await fetch('/admin/api/knowledge-base/documents', {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      if (!response.ok) {
        setStatus(documentStatus, data.detail || 'Unable to upload document.', 'error');
        return;
      }
      input.value = '';
      setStatus(documentStatus, `${data.message}. Refresh the index to include it in search.`, 'success');
      await loadKnowledgeBase();
      await loadDocument(data.name);
    }

    async function refreshKnowledgeBase() {
      const response = await fetch('/admin/api/knowledge-base/refresh', { method: 'POST' });
      const data = await response.json();
      if (!response.ok) {
        setStatus(documentStatus, data.detail || 'Unable to refresh knowledge base.', 'error');
        return;
      }
      lastRefresh.textContent = formatDate(data.status?.last_refreshed_at);
      setStatus(documentStatus, `${data.message}. Indexed ${data.status?.indexed_files?.length || 0} files.`, 'success');
      await loadKnowledgeBase();
    }

    document.getElementById('reloadPrompts').addEventListener('click', () => loadPrompts());
    document.getElementById('savePrompt').addEventListener('click', savePrompt);
    document.getElementById('uploadDocument').addEventListener('click', uploadDocument);
    document.getElementById('saveDocument').addEventListener('click', saveDocument);
    document.getElementById('deleteDocument').addEventListener('click', deleteDocument);
    document.getElementById('refreshKnowledgeBase').addEventListener('click', refreshKnowledgeBase);

    Promise.all([loadPrompts(), loadKnowledgeBase()]).catch((error) => {
      console.error(error);
      setStatus(promptStatus, 'Unable to load admin data.', 'error');
      setStatus(documentStatus, 'Unable to load admin data.', 'error');
    });
  </script>
</body>
</html>
"""