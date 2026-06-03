"""Migración única SQLite -> PostgreSQL (Neon) para OdontoCare Respire.

Transfiere todas las filas de data/odontocare_respire.sqlite3 a la base apuntada por
DATABASE_URL, conservando los id originales (clave para documents y doc_chunks, la
biblioteca indexada del chatbot). La columna generada `tsv` de doc_chunks se calcula
sola en PostgreSQL, así que NO se copia. Al final ajusta las secuencias con setval y
siembra/actualiza el administrador y el usuario demo.

Es re-ejecutable de forma segura: usa ON CONFLICT DO NOTHING en todas las inserciones.

Uso:
    python migrate_to_postgres.py
"""
import os
import sqlite3
from pathlib import Path

# Evita que main.py dispare init_db() y el auto-indexado al importarlo:
# aquí controlamos manualmente el orden (esquema -> datos -> secuencias -> sembrado).
os.environ['SKIP_STARTUP_INIT'] = '1'

import psycopg2.extras
import psycopg2.extensions
import main  # reutiliza Conn, create_schema, seed_admin_and_demo y DATABASE_URL

SQLITE_PATH = Path(__file__).resolve().parent / 'data' / 'odontocare_respire.sqlite3'

# Orden respetando dependencias por FK lógicas (users antes que el resto;
# documents antes que doc_chunks).
TABLE_ORDER = ['users', 'threads', 'messages', 'breathing', 'recovery', 'documents', 'doc_chunks']

# Columnas a copiar por tabla. doc_chunks excluye `tsv` (columna generada en Postgres).
COPY_COLUMNS = {
    'users': ['id', 'nombre', 'correo', 'password_hash', 'role', 'created_at'],
    'threads': ['id', 'user_id', 'title', 'created_at', 'updated_at'],
    'messages': ['id', 'thread_id', 'user_id', 'user_message', 'bot_response', 'stress_level',
                 'stress_score', 'topic_key', 'topic_label', 'reframe', 'out_domain', 'model_used', 'created_at'],
    'breathing': ['id', 'user_id', 'thread_id', 'stress_level', 'completed', 'created_at'],
    'recovery': ['id', 'user_id', 'thread_id', 'status', 'created_at'],
    'documents': ['id', 'filename', 'path', 'sha256', 'total_pages', 'status', 'created_at'],
    'doc_chunks': ['id', 'doc_id', 'filename', 'page', 'chunk_index', 'text', 'norm_text', 'created_at'],
}


def copy_table(sq, raw_cur, table):
    cols = COPY_COLUMNS[table]
    collist = ', '.join(cols)
    rows = sq.execute(f'SELECT {collist} FROM {table}').fetchall()
    if not rows:
        print(f'  {table:11s}: 0 filas (vacía)')
        return 0
    values = [tuple(r) for r in rows]
    psycopg2.extras.execute_values(
        raw_cur,
        f'INSERT INTO {table} ({collist}) VALUES %s ON CONFLICT DO NOTHING',
        values,
        page_size=500,
    )
    print(f'  {table:11s}: {len(values)} filas insertadas')
    return len(values)


def fix_sequence(raw_cur, table):
    raw_cur.execute(f'SELECT COALESCE(MAX(id), 0) FROM {table}')
    maxid = raw_cur.fetchone()[0]
    if maxid > 0:
        raw_cur.execute("SELECT setval(pg_get_serial_sequence(%s, 'id'), %s, true)", (table, maxid))
    else:
        raw_cur.execute("SELECT setval(pg_get_serial_sequence(%s, 'id'), 1, false)", (table,))
    print(f'  secuencia {table:11s} -> {maxid}')


def main_migrate():
    if not SQLITE_PATH.exists():
        raise SystemExit(f'No se encontró la base SQLite: {SQLITE_PATH}')

    sq = sqlite3.connect(SQLITE_PATH)
    sq.row_factory = sqlite3.Row

    c = main.Conn()           # envoltura psycopg2 (RealDictCursor)
    pg = c._c                 # conexión psycopg2 cruda para execute_values
    # Cursor de tuplas (no RealDict) para fetchone()[0] en conteos y setval.
    raw_cur = pg.cursor(cursor_factory=psycopg2.extensions.cursor)

    print('== 1. Creando esquema en PostgreSQL (idempotente) ==')
    main.create_schema(c)
    pg.commit()

    print('== 2. Copiando datos (conservando id originales) ==')
    for table in TABLE_ORDER:
        copy_table(sq, raw_cur, table)
    pg.commit()

    print('== 3. Ajustando secuencias (setval) ==')
    for table in TABLE_ORDER:
        fix_sequence(raw_cur, table)
    pg.commit()

    print('== 4. Sembrando/actualizando administrador y demo ==')
    main.seed_admin_and_demo(c)
    pg.commit()

    print('== 5. Conteos finales en PostgreSQL ==')
    for table in ['users', 'documents', 'doc_chunks', 'threads', 'messages', 'breathing', 'recovery']:
        raw_cur.execute(f'SELECT COUNT(*) FROM {table}')
        print(f'  {table:11s}: {raw_cur.fetchone()[0]}')

    raw_cur.close()
    pg.close()
    sq.close()
    print('\nMigración completada.')


if __name__ == '__main__':
    main_migrate()
