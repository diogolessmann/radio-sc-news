# -*- coding: utf-8 -*-
"""
sponsors.py — Selo Patrocinador do "Bom dia, Vale"
Rádio SC News

Comércio local paga um valor fixo mensal e aparece TODO dia no rodapé do
carrossel "Bom dia, Vale" + uma linha na legenda. Se houver vários
patrocinadores ativos, eles ROTACIONAM por dia (cada um tem seu destaque).

Tabela: sponsors(id, name, logo_url, active, created_at)

Gestão simples por URL (protegida por token de admin) — ver rotas em app.py:
  /api/sponsor/list?token=SENHA
  /api/sponsor/add?token=SENHA&name=Padaria%20X&logo=https://.../logo.png
  /api/sponsor/remove?token=SENHA&id=3
  /api/sponsor/toggle?token=SENHA&id=3&active=0
"""
import os
import re
import sqlite3
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "radio_sc.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_table(conn=None):
    own = conn is None
    conn = conn or get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sponsors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            logo_url TEXT,
            phone TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)
    # migracao: adiciona colunas novas se a tabela ja existia sem elas
    cols = [r[1] for r in conn.execute("PRAGMA table_info(sponsors)")]
    if "phone" not in cols:
        conn.execute("ALTER TABLE sponsors ADD COLUMN phone TEXT")
    if "instagram" not in cols:
        conn.execute("ALTER TABLE sponsors ADD COLUMN instagram TEXT")
    conn.commit()
    if own:
        conn.close()


def _norm_ig(handle):
    """Normaliza o @ do Instagram: tira url/@ e devolve '@usuario' (ou '')."""
    h = (handle or "").strip()
    if not h:
        return ""
    h = re.sub(r"https?://(www\.)?instagram\.com/", "", h, flags=re.I)
    h = h.strip("/@ ").split("/")[0].split("?")[0]
    return f"@{h}" if h else ""


def add_sponsor(name, logo_url="", phone="", instagram=""):
    conn = get_db()
    ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO sponsors (name, logo_url, phone, instagram, active, created_at) "
        "VALUES (?, ?, ?, ?, 1, ?)",
        (name.strip(), (logo_url or "").strip(), (phone or "").strip(),
         _norm_ig(instagram), datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid


def list_sponsors():
    conn = get_db()
    ensure_table(conn)
    rows = [dict(r) for r in conn.execute(
        "SELECT id, name, logo_url, phone, instagram, active, created_at FROM sponsors ORDER BY id"
    ).fetchall()]
    conn.close()
    return rows


def remove_sponsor(sid):
    conn = get_db()
    ensure_table(conn)
    conn.execute("DELETE FROM sponsors WHERE id=?", (int(sid),))
    conn.commit()
    conn.close()


def set_active(sid, active):
    conn = get_db()
    ensure_table(conn)
    conn.execute("UPDATE sponsors SET active=? WHERE id=?", (1 if int(active) else 0, int(sid)))
    conn.commit()
    conn.close()


def active_sponsors(conn=None):
    own = conn is None
    conn = conn or get_db()
    ensure_table(conn)
    rows = conn.execute(
        "SELECT id, name, logo_url, phone, instagram FROM sponsors WHERE active=1 ORDER BY id"
    ).fetchall()
    out = [dict(r) for r in rows]
    if own:
        conn.close()
    return out


def sponsor_of_the_day(conn=None):
    """Patrocinador do dia: rotaciona entre os ativos pelo dia do ano. None se nao houver."""
    ativos = active_sponsors(conn)
    if not ativos:
        return None
    idx = datetime.now().timetuple().tm_yday % len(ativos)
    return ativos[idx]


def fetch_logo(url, max_side=180):
    """Baixa o logo do patrocinador e devolve um PIL.Image (RGBA) ou None."""
    if not url:
        return None
    try:
        import requests
        from io import BytesIO
        from PIL import Image
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        im = Image.open(BytesIO(r.content)).convert("RGBA")
        im.thumbnail((max_side, max_side))
        return im
    except Exception:
        return None
