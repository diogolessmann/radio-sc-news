# -*- coding: utf-8 -*-
"""
agenda.py — AGENDA DO VALE (Rádio SC News).
"O que rola no Vale" — festa de igreja, evento de escola, show, feira, missa, jogo.
Conteúdo ÚTIL (a galera salva e marca amigo) e PATROCINÁVEL ("Agenda apresentada por X").
Ninguém no Vale tem isso de forma organizada — é diferencial puro.

Fluxo: dono cadastra eventos em /admin/agenda → toda semana o motor monta o carrossel
"Agenda do Vale" com os próximos eventos e posta. Reusa gen_instagram + distribuidor.

Tabela: eventos(id, titulo, data_evento[YYYY-MM-DD], hora, local, cidade, active, created_at)
"""
import os
import sqlite3
from datetime import datetime

from PIL import Image, ImageDraw

import gen_instagram as gi
import distribuidor as dist

DB_PATH = os.environ.get("DB_PATH", "radio_sc.db")
_DIAS = ["SEG", "TER", "QUA", "QUI", "SEX", "SÁB", "DOM"]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_table(conn=None):
    own = conn is None
    conn = conn or get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            data_evento TEXT,
            hora TEXT,
            local TEXT,
            cidade TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)
    conn.commit()
    if own:
        conn.close()


def add_evento(titulo, data_evento, hora="", local="", cidade=""):
    conn = get_db()
    ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO eventos (titulo, data_evento, hora, local, cidade, active, created_at) "
        "VALUES (?, ?, ?, ?, ?, 1, ?)",
        (titulo.strip(), (data_evento or "").strip(), (hora or "").strip(),
         (local or "").strip(), (cidade or "").strip(),
         datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    eid = cur.lastrowid
    conn.close()
    return eid


def list_eventos():
    conn = get_db()
    ensure_table(conn)
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM eventos ORDER BY data_evento, hora").fetchall()]
    conn.close()
    return rows


def remove_evento(eid):
    conn = get_db()
    ensure_table(conn)
    conn.execute("DELETE FROM eventos WHERE id=?", (int(eid),))
    conn.commit()
    conn.close()


def eventos_proximos(dias=10):
    """Eventos ativos de hoje até hoje+dias, em ordem de data. Limpa os já passados."""
    conn = get_db()
    ensure_table(conn)
    hoje = datetime.now().strftime("%Y-%m-%d")
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM eventos WHERE active=1 AND data_evento >= ? AND data_evento <= "
        "date('now', ?) ORDER BY data_evento, hora", (hoje, f"+{dias} days")).fetchall()]
    conn.close()
    return rows


def _fmt_data(data_evento, hora=""):
    """'2026-06-20','19h' -> 'SEX 20/06 · 19h'. Tolera data vazia/ruim."""
    try:
        dt = datetime.strptime((data_evento or "")[:10], "%Y-%m-%d")
        base = f"{_DIAS[dt.weekday()]} {dt.strftime('%d/%m')}"
    except Exception:
        base = (data_evento or "").strip()
    h = (hora or "").strip()
    return f"{base} · {h}" if (base and h) else (base or h)


# ---------------------------------------------------------------- arte
def _cover(outdir, n_eventos):
    W, H = gi.W, gi.H
    canvas = Image.new("RGB", (W, H), gi.BG)
    d = ImageDraw.Draw(canvas)
    gi.brand_header(d)

    # título grande
    big = ["AGENDA", "DO VALE"]
    fb = gi.font(118, impact=True)
    lh = int(fb.size * 1.0)
    y = H // 2 - lh
    for ln in big:
        w = d.textlength(ln, font=fb)
        d.text(((W - w) // 2, y), ln, font=fb, fill=gi.WHITE, stroke_width=3, stroke_fill=gi.BLACK)
        y += lh

    # selo dourado
    sel = "O QUE ROLA NO NORTE DE SC"
    fs = gi.font(38)
    sw = d.textlength(sel, font=fs)
    py = y + 30
    d.rounded_rectangle([(W - sw) // 2 - 28, py - 10, (W + sw) // 2 + 28, py + 58],
                        radius=28, fill=gi.GOLD)
    d.text(((W - sw) // 2, py), sel, font=fs, fill=gi.BLACK)

    d.text((56, H - 110), "ARRASTA PARA VER  ->", font=gi.font(34), fill=gi.GOLD)
    path = os.path.join(outdir, "slide_1.png")
    canvas.save(path, quality=92)
    return path


def _lista(eventos, outdir, n):
    """Slide com até 3 eventos."""
    W, H = gi.W, gi.H
    canvas = Image.new("RGB", (W, H), gi.BG)
    d = ImageDraw.Draw(canvas)
    gi.brand_header(d)

    fcab = gi.font(40)
    d.text((56, 150), "AGENDA DA SEMANA", font=fcab, fill=gi.MUTED)

    y = 250
    fdata = gi.font(40, impact=True)
    ftit = gi.font(50, bold=True)
    floc = gi.font(34, bold=False)
    for ev in eventos:
        # barra vermelha
        d.rounded_rectangle([56, y + 4, 66, y + 150], radius=5, fill=gi.RED)
        d.text((92, y), _fmt_data(ev["data_evento"], ev["hora"]).upper(), font=fdata, fill=gi.GOLD)
        ty = y + 52
        for ln in gi.wrap(d, ev["titulo"], ftit, W - 150)[:2]:
            d.text((92, ty), ln, font=ftit, fill=gi.WHITE)
            ty += int(ftit.size * 1.05)
        loc = " · ".join(x for x in (ev.get("cidade"), ev.get("local")) if x)
        if loc:
            d.text((92, ty + 4), loc, font=floc, fill=gi.MUTED)
            ty += 48
        y = max(ty + 50, y + 230)

    gi.footer_site(d)
    path = os.path.join(outdir, f"slide_{n}.png")
    canvas.save(path, quality=92)
    return path


def caption(eventos):
    linhas = ["📅 AGENDA DO VALE — o que rola no Norte de SC essa semana:", ""]
    for ev in eventos[:10]:
        loc = f" — {ev['cidade']}" if ev.get("cidade") else ""
        linhas.append(f"• {_fmt_data(ev['data_evento'], ev['hora'])} · {ev['titulo']}{loc}")
    linhas += ["", "🔖 Salva e 🔁 marca quem vai com você!",
               "➕ Segue @radiosc.news pra não perder a agenda do Vale.", "",
               "📩 Tem evento na sua cidade? Manda no direct que a gente divulga.", "",
               "#agenda #eventos #vale #valedoitapocu #nortedesc #jaraguadosul "
               "#schroeder #guaramirim #joinville #radioscnews"]
    return "\n".join(linhas)


def run(post=False, dias=10):
    """Monta (e opcionalmente posta) o carrossel da Agenda. Pula se não há eventos próximos."""
    eventos = eventos_proximos(dias)
    if not eventos:
        return {"ok": False, "motivo": "sem eventos próximos cadastrados"}

    day = datetime.now().strftime("%Y-%m-%d")
    outdir = os.path.join("instagram_posts", day + "_agenda")
    os.makedirs(outdir, exist_ok=True)

    imgs = [_cover(outdir, len(eventos))]
    n = 2
    for i in range(0, len(eventos), 3):       # 3 eventos por slide
        imgs.append(_lista(eventos[i:i + 3], outdir, n))
        n += 1
    imgs.append(gi.slide_cta({"city": None}, outdir, n))   # CTA engajamento

    cap = caption(eventos)
    with open(os.path.join(outdir, "legenda.txt"), "w", encoding="utf-8") as f:
        f.write(cap)

    if post:
        dist.publish_images("agenda", imgs, cap)
    return {"ok": True, "n_eventos": len(eventos), "imgs": imgs, "outdir": outdir,
            "postado": bool(post)}


if __name__ == "__main__":
    print(run(post=False))
