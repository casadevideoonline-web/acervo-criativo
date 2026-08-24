"""
checar_duplicatas.py — compara videos de uma pasta com o acervo existente
e avisa quais parecem visualmente duplicados. NAO sobe nem apaga nada.

Uso:
    python checar_duplicatas.py --videos /pasta/dos/novos --db /data/catalog.db
"""
import os, sys, json, argparse, tempfile
import numpy as np
from process_videos import embed_image, get_duration, extract_thumbnail
import sqlite3

LIMITE = 0.92  # 0 a 1. Acima disso, considera "muito parecido". Ajustavel.

def carregar_acervo(db_path):
    conn = sqlite3.connect(db_path)
    itens = []
    for r in conn.execute("SELECT filename, embedding_json FROM videos WHERE embedding_json IS NOT NULL"):
        try:
            vec = np.array(json.loads(r[1]), dtype=np.float32)
            vec = vec / (np.linalg.norm(vec) + 1e-9)
            itens.append((r[0], vec))
        except Exception:
            pass
    conn.close()
    return itens

def embedding_do_video(video_path, thumb_dir):
    dur = get_duration(video_path)
    ts = max(1.0, min(5.0, dur * 0.1)) if dur else 1.0
    base = os.path.splitext(os.path.basename(video_path))[0]
    thumb = os.path.join(thumb_dir, base + ".jpg")
    extract_thumbnail(video_path, ts, thumb)
    if not os.path.exists(thumb):
        return None
    vec = np.array(embed_image(thumb), dtype=np.float32)
    return vec / (np.linalg.norm(vec) + 1e-9)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--videos", required=True, help="Pasta com os videos novos")
    p.add_argument("--db", default="/data/catalog.db", help="Banco do acervo")
    p.add_argument("--extensions", default=".mp4,.mov,.avi,.mkv,.webm")
    p.add_argument("--limite", type=float, default=LIMITE)
    args = p.parse_args()

    exts = tuple(e.strip().lower() for e in args.extensions.split(","))
    novos = [os.path.join(r, f)
             for r, _, files in os.walk(args.videos)
             for f in files if f.lower().endswith(exts)]

    if not novos:
        print("Nenhum video encontrado na pasta:", args.videos)
        return

    print(f"Carregando acervo de {args.db}...")
    acervo = carregar_acervo(args.db)
    print(f"  {len(acervo)} videos no acervo com impressao visual.")
    print(f"Analisando {len(novos)} videos novos (limite de parecenca: {int(args.limite*100)}%)\n")

    provaveis_novos = []
    provaveis_dup = []

    with tempfile.TemporaryDirectory() as tmp:
        for i, vp in enumerate(novos, 1):
            nome = os.path.basename(vp)
            print(f"[{i}/{len(novos)}] {nome}")
            try:
                vec = embedding_do_video(vp, tmp)
            except Exception as e:
                print(f"    [erro ao analisar: {e}] — pulando\n")
                continue
            if vec is None:
                print("    [nao consegui gerar thumbnail] — pulando\n")
                continue
            melhores = sorted(
                ((float(np.dot(vec, a[1])), a[0]) for a in acervo),
                reverse=True
            )[:3]
            top_score = melhores[0][0] if melhores else 0
            if top_score >= args.limite:
                provaveis_dup.append((nome, melhores))
                print(f"    ⚠️  PARECE DUPLICADO ({int(top_score*100)}% parecido com \"{melhores[0][1]}\")")
                for s, n in melhores[1:]:
                    print(f"         tambem parecido: {int(s*100)}% -> \"{n}\"")
            else:
                provaveis_novos.append(nome)
                print(f"    ✓ provavelmente novo (mais parecido: {int(top_score*100)}%)")
            print()

    print("=" * 60)
    print(f"RESUMO: {len(provaveis_novos)} provavelmente novos | {len(provaveis_dup)} provavelmente duplicados")
    print("=" * 60)
    if provaveis_dup:
        print("\nPROVAVELMENTE DUPLICADOS (confira antes de subir):")
        for nome, melhores in provaveis_dup:
            print(f"  {nome}  ->  \"{melhores[0][1]}\" ({int(melhores[0][0]*100)}%)")
    if provaveis_novos:
        print("\nPROVAVELMENTE NOVOS (parecem seguros pra subir):")
        for nome in provaveis_novos:
            print(f"  {nome}")

if __name__ == "__main__":
    main()
