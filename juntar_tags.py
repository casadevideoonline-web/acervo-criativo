import sqlite3, shutil, datetime

# Pares para juntar: (tag_de, tag_para) -> a "de" vira a "para"
PARES = [
    ("stop-motion", "stop motion"),
    ("tiltshift", "tilt shift"),
    ("letterings", "lettering"),
    ("gcs", "gc"),
    ("vimheta", "vinheta"),
    ("heart", "coracao"),
    ("video abertura", "abertura"),
    ("agro", "agricultura"),
]

# Tags para apagar de vez
APAGAR = ["teste", "teste 3", "teste4"]

DB = '/data/catalog.db'
stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
shutil.copy(DB, DB + '.backup_' + stamp)
print('Backup criado: catalog.db.backup_' + stamp)

c = sqlite3.connect(DB)

print('--- Juntando ---')
for de, para in PARES:
    videos_de = [r[0] for r in c.execute('SELECT video_id FROM tags WHERE tag=?', (de,)).fetchall()]
    if not videos_de:
        print(f'  (pulado) "{de}" nao existe')
        continue
    for video_id in videos_de:
        ja_tem = c.execute('SELECT 1 FROM tags WHERE video_id=? AND tag=?', (video_id, para)).fetchone()
        if ja_tem:
            c.execute('DELETE FROM tags WHERE video_id=? AND tag=?', (video_id, de))
        else:
            c.execute('UPDATE tags SET tag=? WHERE video_id=? AND tag=?', (para, video_id, de))
    print(f'  "{de}" -> "{para}"  ({len(videos_de)} video(s))')

print('--- Apagando ---')
for tag in APAGAR:
    n = c.execute('DELETE FROM tags WHERE tag=?', (tag,)).rowcount
    print(f'  apagado "{tag}"  ({n} registro(s))')

c.commit()
print('Pronto!')
