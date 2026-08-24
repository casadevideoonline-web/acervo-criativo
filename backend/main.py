"""
main.py — API do buscador de videos.
"""

import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")

import urllib.parse
import unicodedata
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, Request, Header
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import secrets

from .search import VideoIndex, search_videos, get_similar_videos, suggest_tags, get_connection
from .storage import signed_url_video, signed_url_download, deletar_objeto

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
DB_PATH = str(DATA_DIR / "catalog.db")


def normalize_tag(tag: str) -> str:
    """Remove acentos, espacos extras e deixa minusculo. "projeção" -> "projecao"."""
    tag = tag.strip().lower()
    nfkd = unicodedata.normalize("NFKD", tag)
    return "".join(c for c in nfkd if not unicodedata.combining(c))
APP_USER = os.environ.get("APP_USER", "admin")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "mude-esta-senha")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "mude-esta-senha-admin")

app = FastAPI(title="Video Search")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

security = HTTPBasic()
video_index = VideoIndex(DB_PATH)


def require_login(credentials: HTTPBasicCredentials = Depends(security)):
    ok_user = secrets.compare_digest(credentials.username, APP_USER)
    ok_pass = secrets.compare_digest(credentials.password, APP_PASSWORD)
    if not (ok_user and ok_pass):
        raise HTTPException(status_code=401, detail="Credenciais invalidas",
                             headers={"WWW-Authenticate": "Basic"})
    return credentials.username


def require_admin(x_admin_password: str = Header(default="")):
    if not secrets.compare_digest(x_admin_password, ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="Senha de admin invalida")
    return True


class TagIn(BaseModel):
    video_id: str
    tag: str


class RenameIn(BaseModel):
    filename: str


@app.get("/api/search")
def search(q: str = "", tags: str = "", limit: int = 60,
           user: str = Depends(require_login)):
    conn = get_connection(DB_PATH)
    tag_list = [normalize_tag(t) for t in tags.split(",") if t.strip()] or None
    results = search_videos(conn, video_index, query=q or None, tags=tag_list, limit=limit)
    conn.close()
    return {"results": results}


@app.get("/api/similar/{video_id}")
def similar_videos(video_id: str, limit: int = 6, user: str = Depends(require_login)):
    conn = get_connection(DB_PATH)
    results = get_similar_videos(conn, video_index, video_id, limit=limit)
    conn.close()
    return {"results": results}


@app.get("/api/suggest-tags/{video_id}")
def suggest_tags_endpoint(video_id: str, user: str = Depends(require_login)):
    conn = get_connection(DB_PATH)
    suggestions = suggest_tags(conn, video_index, video_id)
    conn.close()
    return {"suggestions": suggestions}


@app.get("/api/tags/top")
def top_tags(user: str = Depends(require_login)):
    conn = get_connection(DB_PATH)
    rows = conn.execute(
        "SELECT tag, COUNT(*) as count FROM tags GROUP BY tag ORDER BY count DESC, tag ASC"
    ).fetchall()
    conn.close()
    return {"tags": [{"tag": r["tag"], "count": r["count"]} for r in rows]}


@app.get("/api/stats")
def stats(user: str = Depends(require_login)):
    conn = get_connection(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    conn.close()
    return {"total_videos": total}


@app.post("/api/tags")
def add_tag(payload: TagIn, user: str = Depends(require_login)):
    conn = get_connection(DB_PATH)
    conn.execute("INSERT INTO tags (video_id, tag) VALUES (?, ?)",
                 (payload.video_id, normalize_tag(payload.tag)))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.delete("/api/tags")
def remove_tag(payload: TagIn, user: str = Depends(require_login)):
    conn = get_connection(DB_PATH)
    conn.execute("DELETE FROM tags WHERE video_id = ? AND tag = ?",
                 (payload.video_id, normalize_tag(payload.tag)))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.post("/api/admin/rename/{video_id}")
def admin_rename_video(video_id: str, payload: RenameIn):
    novo_nome = payload.filename.strip()
    if not novo_nome:
        raise HTTPException(400, "O nome nao pode ficar vazio")
    conn = get_connection(DB_PATH)
    row = conn.execute("SELECT id FROM videos WHERE id = ?", (video_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Video nao encontrado")
    conn.execute("UPDATE videos SET filename = ? WHERE id = ?", (novo_nome, video_id))
    conn.commit()
    conn.close()
    return {"ok": True, "filename": novo_nome}


@app.delete("/api/admin/delete/{video_id}")
def admin_delete_video(video_id: str):
    conn = get_connection(DB_PATH)
    row = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Video nao encontrado")
    try:
        import os
        nome_arquivo = os.path.basename(row["filepath"])
        deletar_objeto(nome_arquivo)
    except Exception:
        pass
    try:
        tp = row["thumbnail_path"]
        if tp and Path(tp).exists():
            Path(tp).unlink()
    except Exception:
        pass
    conn.execute("DELETE FROM tags WHERE video_id = ?", (video_id,))
    conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))
    conn.commit()
    conn.close()
    video_index.reload()
    return {"ok": True}


@app.post("/api/reload-index")
def reload_index(user: str = Depends(require_login)):
    video_index.reload()
    return {"ok": True, "total_videos": video_index.index.ntotal}


@app.get("/api/thumbnail/{video_id}")
def get_thumbnail(video_id: str, user: str = Depends(require_login)):
    conn = get_connection(DB_PATH)
    row = conn.execute("SELECT thumbnail_path FROM videos WHERE id = ?", (video_id,)).fetchone()
    conn.close()
    if not row or not Path(row["thumbnail_path"]).exists():
        raise HTTPException(404, "Thumbnail nao encontrada")
    return FileResponse(row["thumbnail_path"], media_type="image/jpeg")


def _get_video_row(video_id: str):
    conn = get_connection(DB_PATH)
    row = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Video nao encontrado")
    filepath = Path(row["filepath"])
    if not filepath.exists():
        raise HTTPException(404, "Arquivo de video nao esta mais no armazenamento")
    return row, filepath


def parse_range_header(range_header: str, file_size: int):
    if not range_header or not range_header.startswith("bytes="):
        return None
    spec = range_header[len("bytes="):].split(",")[0].strip()
    if "-" not in spec:
        return None
    start_str, end_str = spec.split("-", 1)
    try:
        if start_str == "":
            if end_str == "":
                return None
            suffix_len = int(end_str)
            start = max(file_size - suffix_len, 0)
            end = file_size - 1
        else:
            start = int(start_str)
            end = int(end_str) if end_str else file_size - 1
    except ValueError:
        return None
    end = min(end, file_size - 1)
    if start < 0 or start > end:
        return None
    return start, end

@app.get("/api/video/{video_id}")
def stream_video(video_id: str, user: str = Depends(require_login)):
    conn = get_connection(DB_PATH)
    row = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Video nao encontrado")
    import os
    nome_arquivo = os.path.basename(row["filepath"])
    url = signed_url_video(nome_arquivo)
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=url, status_code=302)


@app.get("/api/download/{video_id}")
def download_video(video_id: str, user: str = Depends(require_login)):
    conn = get_connection(DB_PATH)
    row = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Video nao encontrado")
    import os
    nome_arquivo = os.path.basename(row["filepath"])
    url = signed_url_download(nome_arquivo)
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=url, status_code=302)


frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
