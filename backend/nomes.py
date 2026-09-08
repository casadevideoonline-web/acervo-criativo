"""
nomes.py
========
Tratamento de nomes de arquivos de video para o padrao do acervo:
ASCII puro, minusculas, sem espacos — regras definidas em 03/09/2026.
"""

import os
import re
import unicodedata


def tratar_nome_arquivo(nome_original: str) -> str:
    """Ex.: 'Reuniao Externa (FINAL) v2.MP4' -> 'reuniao_externa_final_v2.mp4'"""
    raiz, extensao = os.path.splitext(nome_original)

    # translitera acentos: a~ -> a, c, -> c, e' -> e...
    raiz = unicodedata.normalize("NFKD", raiz)
    raiz = raiz.encode("ascii", "ignore").decode("ascii")

    raiz = raiz.lower()
    raiz = re.sub(r"[^a-z0-9_-]+", "_", raiz)   # tudo que nao e permitido vira _
    raiz = re.sub(r"_+", "_", raiz)             # __ duplicados viram um so
    raiz = raiz.strip("_-")                     # sem _ ou - nas pontas

    if not raiz:
        raiz = "video_sem_nome"

    return raiz + extensao.lower()


def resolver_colisao(nome_tratado: str, nomes_existentes: set[str]) -> str:
    """Se 'video.mp4' ja existe, tenta 'video_2.mp4', 'video_3.mp4'..."""
    if nome_tratado not in nomes_existentes:
        return nome_tratado
    raiz, extensao = os.path.splitext(nome_tratado)
    contador = 2
    while f"{raiz}_{contador}{extensao}" in nomes_existentes:
        contador += 1
    return f"{raiz}_{contador}{extensao}"
