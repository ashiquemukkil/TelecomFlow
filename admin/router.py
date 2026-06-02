from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import hashlib
from html import escape
import hmac
import mimetypes
import os
from pathlib import Path
import time
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from openai import OpenAIError
from pydantic import BaseModel

from connectors.aisearch import AISearch


PACKAGE_DIR = Path(__file__).resolve().parent
ROOT_DIR = PACKAGE_DIR.parent
TEMPLATE_DIR = PACKAGE_DIR / "templates"
STATIC_DIR = PACKAGE_DIR / "static"
KNOWLEDGEBASE_DIR = ROOT_DIR / "knowledgebase"
DOCUMENTS_DIR = KNOWLEDGEBASE_DIR / "documents"
PROMPT_ROOT = ROOT_DIR / "orc"
INDEX_FILE = KNOWLEDGEBASE_DIR / "index.faiss"

ALLOWED_PROMPT_NAMES = {"skprompt.txt", "bot_description.prompt"}
ALLOWED_STATIC_ASSETS = {"admin.css", "admin.js", "login.css"}
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
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me-admin")
ADMIN_SESSION_SECRET = os.getenv("ADMIN_SESSION_SECRET", f"{ROOT_DIR.name}-admin-session")
ADMIN_SESSION_COOKIE = "telecrmflow_admin_session"
ADMIN_SESSION_MAX_AGE = 60 * 60 * 8


class PromptUpdateRequest(BaseModel):
    content: str


class DocumentUpdateRequest(BaseModel):
    content: str


router = APIRouter(tags=["admin"])


def _ensure_storage() -> None:
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=None)
def _load_template(template_name: str) -> str:
    template_path = (TEMPLATE_DIR / template_name).resolve()
    if not template_path.is_relative_to(TEMPLATE_DIR.resolve()) or not template_path.exists():
        raise RuntimeError(f"Missing admin template: {template_name}")
    return template_path.read_text(encoding="utf-8")


def _sign_admin_session(username: str, issued_at: int) -> str:
    payload = f"{username}:{issued_at}"
    signature = hmac.new(
        ADMIN_SESSION_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}:{signature}"


def _is_authenticated(request: Request) -> bool:
    token = request.cookies.get(ADMIN_SESSION_COOKIE)
    if not token:
        return False

    try:
        username, issued_at_raw, signature = token.split(":", 2)
        issued_at = int(issued_at_raw)
    except ValueError:
        return False

    if username != ADMIN_USERNAME:
        return False
    if int(time.time()) - issued_at > ADMIN_SESSION_MAX_AGE:
        return False

    expected = _sign_admin_session(username, issued_at)
    return hmac.compare_digest(expected, token)


def _require_admin_session(request: Request) -> None:
    if not _is_authenticated(request):
        raise HTTPException(status_code=401, detail="Admin login required")


def _login_page_html(error_message: str = "") -> str:
    notice_class = "login-error" if error_message else "login-hint"
    notice_text = error_message or "Use the configured admin credentials to continue."
    notice_html = f'<div class="{notice_class}">{escape(notice_text)}</div>'
    return _load_template("login.html").replace("{{ login_notice }}", notice_html)


def _admin_page_html() -> str:
    return _load_template("admin.html")


def _isoformat(value: float | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _relative_prompt_id(path: Path) -> str:
    return path.relative_to(ROOT_DIR).as_posix()


def _get_prompt_paths() -> list[Path]:
    prompt_paths = [PROMPT_ROOT / "bot_description.prompt"]
    prompt_paths.extend(sorted(PROMPT_ROOT.glob("plugins/**/skprompt.txt")))
    return [path for path in prompt_paths if path.exists()]


def _resolve_prompt_path(prompt_id: str) -> Path:
    prompt_path = (ROOT_DIR / prompt_id).resolve()
    if not prompt_path.exists():
        raise HTTPException(status_code=404, detail="Prompt not found")
    if prompt_path.name not in ALLOWED_PROMPT_NAMES:
        raise HTTPException(status_code=400, detail="Unsupported prompt file")
    if not prompt_path.is_relative_to(ROOT_DIR):
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


def _resolve_static_asset(asset_name: str) -> Path:
    safe_name = Path(asset_name).name
    if safe_name not in ALLOWED_STATIC_ASSETS:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset_path = (STATIC_DIR / safe_name).resolve()
    if not asset_path.is_relative_to(STATIC_DIR.resolve()) or not asset_path.exists():
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset_path


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
async def admin_page(request: Request) -> HTMLResponse:
    if not _is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=303)
    return HTMLResponse(_admin_page_html())


@router.get("/admin/login", response_class=HTMLResponse, include_in_schema=False)
async def admin_login_page(request: Request) -> HTMLResponse:
    if _is_authenticated(request):
        return RedirectResponse(url="/admin", status_code=303)
    return HTMLResponse(_login_page_html())


@router.get("/admin/assets/{asset_name}", include_in_schema=False)
async def admin_asset(asset_name: str) -> FileResponse:
    return FileResponse(_resolve_static_asset(asset_name))


@router.post("/admin/login", include_in_schema=False)
async def admin_login(username: str = Form(...), password: str = Form(...)) -> HTMLResponse:
    if not (
        hmac.compare_digest(username, ADMIN_USERNAME)
        and hmac.compare_digest(password, ADMIN_PASSWORD)
    ):
        return HTMLResponse(_login_page_html("Invalid username or password."), status_code=401)

    response = RedirectResponse(url="/admin", status_code=303)
    response.set_cookie(
        key=ADMIN_SESSION_COOKIE,
        value=_sign_admin_session(username, int(time.time())),
        max_age=ADMIN_SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response


@router.post("/admin/logout", include_in_schema=False)
async def admin_logout() -> RedirectResponse:
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie(ADMIN_SESSION_COOKIE)
    return response


@router.get("/admin/api/prompts")
async def list_prompts(request: Request) -> dict[str, Any]:
    _require_admin_session(request)
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
async def get_prompt(prompt_id: str, request: Request) -> dict[str, Any]:
    _require_admin_session(request)
    prompt_path = _resolve_prompt_path(prompt_id)
    return {
        "id": _relative_prompt_id(prompt_path),
        "name": prompt_path.parent.name if prompt_path.name == "skprompt.txt" else prompt_path.name,
        "path": _relative_prompt_id(prompt_path),
        "content": prompt_path.read_text(encoding="utf-8"),
        "updated_at": _isoformat(prompt_path.stat().st_mtime),
    }


@router.put("/admin/api/prompts/{prompt_id:path}")
async def update_prompt(prompt_id: str, payload: PromptUpdateRequest, request: Request) -> dict[str, Any]:
    _require_admin_session(request)
    prompt_path = _resolve_prompt_path(prompt_id)
    prompt_path.write_text(payload.content, encoding="utf-8")
    return {
        "message": "Prompt saved",
        "id": _relative_prompt_id(prompt_path),
        "updated_at": _isoformat(prompt_path.stat().st_mtime),
    }


@router.get("/admin/api/knowledge-base/status")
async def knowledge_base_status(request: Request) -> dict[str, Any]:
    _require_admin_session(request)
    return _knowledge_base_status()


@router.get("/admin/api/knowledge-base/documents")
async def list_knowledge_base_documents(request: Request) -> dict[str, Any]:
    _require_admin_session(request)
    return {"items": _list_documents(), "status": _knowledge_base_status()}


@router.get("/admin/api/knowledge-base/documents/{document_name:path}")
async def get_knowledge_base_document(document_name: str, request: Request) -> dict[str, Any]:
    _require_admin_session(request)
    document_path = _resolve_document_path(document_name)
    if not document_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "name": document_path.name,
        "content": _read_text_document(document_path),
        "updated_at": _isoformat(document_path.stat().st_mtime),
    }


@router.post("/admin/api/knowledge-base/documents")
async def upload_knowledge_base_document(request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
    _require_admin_session(request)
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
async def update_knowledge_base_document(
    document_name: str,
    payload: DocumentUpdateRequest,
    request: Request,
) -> dict[str, Any]:
    _require_admin_session(request)
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
async def delete_knowledge_base_document(document_name: str, request: Request) -> dict[str, Any]:
    _require_admin_session(request)
    document_path = _resolve_document_path(document_name)
    if not document_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")
    os.remove(document_path)
    return {"message": "Document deleted", "name": document_path.name}


@router.post("/admin/api/knowledge-base/refresh")
async def refresh_knowledge_base(request: Request) -> dict[str, Any]:
    _require_admin_session(request)
    try:
        status = _rebuild_knowledge_base()
    except OpenAIError as exc:
        raise HTTPException(
            status_code=400,
            detail="Knowledge base refresh requires a valid OPENAI_API_KEY for embeddings.",
        ) from exc
    return {"message": "Knowledge base refreshed", "status": status}