import sqlite3, unicodedata, shutil, datetime

def norm(t):
    t = t.strip().lower()
    return ''.join(c for c in unicodedata.normalize('NFKD', t) if not unicodedata.combining(c))

stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
shutil.copy('data/catalog.db', f'data/catalog.db.backup_{stamp}')
print('Backup do banco criado: catalog.db.backup_' + stamp)

c = sqlite3.connect('data/catalog.db')
pares = c.execute('SELECT video_id, tag FROM tags').fetchall()
alterados = 0
for video_id, tag in pares:
    nova = norm(tag)
    if nova == tag:
        continue
    existe = c.execute('SELECT 1 FROM tags WHERE video_id=? AND tag=?', (video_id, nova)).fetchone()
    if existe:
        c.execute('DELETE FROM tags WHERE video_id=? AND tag=?', (video_id, tag))
    else:
        c.execute('UPDATE tags SET tag=? WHERE video_id=? AND tag=?', (nova, video_id, tag))
    alterados += 1
c.commit()
print('Registros de tag ajustados:', alterados)
print('Tags distintas agora:')
for r in c.execute('SELECT DISTINCT tag FROM tags ORDER BY tag'):
    print('  ' + r[0])
