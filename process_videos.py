"""
process_videos.py
==================
Varre uma pasta de vídeos e, para cada um: extrai UMA imagem (thumbnail)
representativa e gera um "embedding" visual (CLIP) para permitir busca por
conteúdo. Um vídeo = uma linha no catálogo = uma thumbnail.

Uso:
    python process_videos.py --videos /caminho/para/seus/videos --out ./data

Pode ser rodado de novo a qualquer momento: vídeos já processados (mesmo nome
+ tamanho) são pulados automaticamente, então dá para ir adicionando vídeos
novos à pasta e rodar o script de novo só para eles.
"""

import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")  # evita crash de bibliotecas de IA duplicadas no macOS

import argparse
import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# CLIP embeddings — carregado sob demanda (é a parte "pesada" da pipeline).
# Se você só quiser testar a extração de thumbnail primeiro, rode com
# --no-embeddings.
# ---------------------------------------------------------------------------
_clip_model = None
_clip_preprocess = None


def _load_clip():
    global _clip_model, _clip_preprocess
    if _clip_model is None:
        import open_clip

        _clip_model, _, _clip_preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="laion2b_s34b_b79k"
        )
        _clip_model.eval()
    return _clip_model, _clip_preprocess


def embed_image(image_path: str):
    """Retorna o embedding CLIP (lista de floats) de uma imagem."""
    import torch
    from PIL import Image

    model, preprocess = _load_clip()
    image = preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0)
    with torch.no_grad():
        features = model.encode_image(image)
        features /= features.norm(dim=-1, keepdim=True)
    return features[0].tolist()


# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------

def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY,
            filename TEXT,
            filepath TEXT,
            duration REAL,
            thumbnail_path TEXT,
            embedding_json TEXT,
            file_hash TEXT UNIQUE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT,
            tag TEXT,
            FOREIGN KEY(video_id) REFERENCES videos(id)
        )
    """)
    conn.commit()
    return conn


def file_signature(path: str) -> str:
    """Hash rápido baseado em nome + tamanho (não lê o arquivo inteiro,
    importante com vídeos grandes)."""
    stat = os.stat(path)
    raw = f"{os.path.basename(path)}::{stat.st_size}"
    return hashlib.sha1(raw.encode()).hexdigest()


def get_duration(video_path: str) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", video_path,
        ],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def extract_thumbnail(video_path: str, timestamp: float, out_path: str):
    subprocess.run(
        [
            "ffmpeg", "-y", "-ss", str(timestamp), "-i", video_path,
            "-frames:v", "1", "-q:v", "3", out_path,
        ],
        capture_output=True,
    )


def process_video(video_path: str, conn: sqlite3.Connection, thumb_dir: str,
                   compute_embeddings: bool = True):
    file_hash = file_signature(video_path)
    existing = conn.execute(
        "SELECT id FROM videos WHERE file_hash = ?", (file_hash,)
    ).fetchone()
    if existing:
        print(f"  [pulado, já processado] {os.path.basename(video_path)}")
        return

    video_id = file_hash[:12]
    duration = get_duration(video_path)

    # thumbnail tirada a ~35% do vídeo (evita aberturas pretas/escuras)

    timestamp = max(duration * 0.35, 1.0) if duration > 0 else 0.0
    thumb_path = os.path.join(thumb_dir, f"{video_id}.jpg")
    extract_thumbnail(video_path, timestamp, thumb_path)

    embedding_json = None
    if compute_embeddings and os.path.exists(thumb_path):
        try:
            embedding_json = json.dumps(embed_image(thumb_path))
        except Exception as e:
            print(f"    [aviso] falha ao gerar embedding: {e}")

    conn.execute(
        """INSERT INTO videos
           (id, filename, filepath, duration, thumbnail_path, embedding_json, file_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (video_id, os.path.basename(video_path), video_path, duration,
         thumb_path, embedding_json, file_hash),
    )
    conn.commit()
    print(f"  -> processado ({duration:.1f}s)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--videos", required=True, help="Pasta com os vídeos")
    parser.add_argument("--out", default="./data", help="Pasta de saída (banco + thumbnails)")
    parser.add_argument("--no-embeddings", action="store_true",
                         help="Pula a geração de embeddings CLIP (só extrai a thumbnail)")
    parser.add_argument("--extensions", default=".mp4,.mov,.avi,.mkv,.webm")
    args = parser.parse_args()

    out_dir = Path(args.out)
    thumb_dir = out_dir / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    db_path = out_dir / "catalog.db"

    conn = init_db(str(db_path))
    exts = tuple(e.strip().lower() for e in args.extensions.split(","))

    video_files = [
        os.path.join(root, f)
        for root, _, files in os.walk(args.videos)
        for f in files if f.lower().endswith(exts)
    ]
    print(f"Encontrados {len(video_files)} vídeos em {args.videos}\n")

    for i, video_path in enumerate(video_files, 1):
        print(f"[{i}/{len(video_files)}] {os.path.basename(video_path)}")
        try:
            process_video(video_path, conn, str(thumb_dir),
                          compute_embeddings=not args.no_embeddings)
        except Exception as e:
            print(f"  [ERRO] {e}")

    conn.close()
    print(f"\nPronto. Banco salvo em {db_path}")


if __name__ == "__main__":
    main()
