"""
storage.py
==========
Gera Signed URLs v4 para objetos no Cloud Storage.
A autenticação usa a service account anexada à instância (sem arquivo de chave).
"""

import datetime
import google.auth
import google.auth.transport.requests
from google.cloud import storage

BUCKET = "acervo-criativo-videos"
PREFIXO = "videos"
TTL_VIDEO = datetime.timedelta(hours=8)
TTL_DOWNLOAD = datetime.timedelta(minutes=15)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = storage.Client()
    return _client


def _credenciais():
    """Retorna credenciais frescas da service account da instância."""
    creds, _ = google.auth.default()
    creds.refresh(google.auth.transport.requests.Request())
    return creds


def signed_url_video(nome_arquivo: str) -> str:
    """
    Gera Signed URL de leitura para reprodução no player.
    TTL de 1 hora — suficiente para qualquer reprodução sem quebrar seek.
    """
    creds = _credenciais()
    blob = _get_client().bucket(BUCKET).blob(f"{PREFIXO}/{nome_arquivo}")
    return blob.generate_signed_url(
        version="v4",
        expiration=TTL_VIDEO,
        method="GET",
        service_account_email=creds.service_account_email,
        access_token=creds.token,
    )


def signed_url_download(nome_arquivo: str) -> str:
    """
    Gera Signed URL de download com Content-Disposition forçado.
    TTL menor (15 min) — não precisa de seek, só de baixar uma vez.
    """
    creds = _credenciais()
    blob = _get_client().bucket(BUCKET).blob(f"{PREFIXO}/{nome_arquivo}")
    return blob.generate_signed_url(
        version="v4",
        expiration=TTL_DOWNLOAD,
        method="GET",
        service_account_email=creds.service_account_email,
        access_token=creds.token,
        response_disposition=f'attachment; filename="{nome_arquivo}"',
    )


def listar_nomes_videos() -> set:
    """
    Nomes de arquivo (sem o prefixo videos/) ja existentes no bucket.
    Usado na checagem de colisao antes de subir um video novo.
    """
    blobs = _get_client().list_blobs(BUCKET, prefix=f"{PREFIXO}/")
    return {b.name[len(PREFIXO) + 1:] for b in blobs if b.name != f"{PREFIXO}/"}


def subir_video(caminho_local: str, nome_arquivo: str) -> str:
    """
    Sobe o arquivo local para videos/<nome_arquivo> no bucket.
    Retorna o caminho completo do objeto criado.
    """
    blob = _get_client().bucket(BUCKET).blob(f"{PREFIXO}/{nome_arquivo}")
    blob.upload_from_filename(caminho_local, timeout=600)
    return f"{PREFIXO}/{nome_arquivo}"


def deletar_objeto(nome_arquivo: str) -> bool:
    """
    Remove o objeto do bucket. Retorna True se deletou, False se não existia.
    """
    try:
        blob = _get_client().bucket(BUCKET).blob(f"{PREFIXO}/{nome_arquivo}")
        blob.delete()
        return True
    except Exception:
        return False