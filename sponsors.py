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


# ---------------------------------------------------------------- PUBLIPOST (produto premium)
def slide_publipost(sponsor, outdir):
    """Card dedicado do parceiro (1 imagem) — o post pago. Logo (se tiver) + nome + @ + telefone."""
    import gen_instagram as gi
    from PIL import Image, ImageDraw
    W, H = gi.W, gi.H
    canvas = Image.new("RGB", (W, H), gi.BG)
    d = ImageDraw.Draw(canvas)
    gi.brand_header(d)

    # selo dourado no topo
    selo = "PARCEIRO DO VALE"
    fs = gi.font(38)
    sw = d.textlength(selo, font=fs)
    py = 250
    d.rounded_rectangle([(W - sw) // 2 - 28, py - 12, (W + sw) // 2 + 28, py + 58],
                        radius=28, fill=gi.GOLD)
    d.text(((W - sw) // 2, py), selo, font=fs, fill=gi.BLACK)

    # logo centralizado (se houver)
    logo = fetch_logo(sponsor.get("logo_url"), max_side=420)
    y = 380
    if logo:
        canvas.paste(logo, ((W - logo.width) // 2, y), logo)
        y += logo.height + 40
    else:
        y += 60

    # nome do parceiro (grande)
    nome = (sponsor.get("name") or "").upper()
    fn = gi.font(76, impact=True)
    for ln in gi.wrap(d, nome, fn, W - 140):
        w = d.textlength(ln, font=fn)
        d.text(((W - w) // 2, y), ln, font=fn, fill=gi.WHITE, stroke_width=3, stroke_fill=gi.BLACK)
        y += int(fn.size * 1.05)

    # contato: @instagram + telefone
    y += 24
    insta = (sponsor.get("instagram") or "").strip()
    fone = (sponsor.get("phone") or "").strip()
    fi = gi.font(46)
    if insta:
        w = d.textlength(insta, font=fi)
        d.text(((W - w) // 2, y), insta, font=fi, fill=gi.GOLD)
        y += 70
    if fone:
        txt = f"Contato: {fone}"
        w = d.textlength(txt, font=fi)
        d.text(((W - w) // 2, y), txt, font=fi, fill=gi.WHITE)
        y += 70

    # rodapé de posicionamento
    rod = "Quem apoia a informação do Vale"
    fr = gi.font(34, bold=False)
    w = d.textlength(rod, font=fr)
    d.text(((W - w) // 2, H - 150), rod, font=fr, fill=gi.MUTED)
    gi.footer_site(d)

    path = os.path.join(outdir, "publipost.png")
    canvas.save(path, quality=92)
    return path


def publipost_caption(sponsor):
    nome = sponsor.get("name") or "nosso parceiro"
    insta = (sponsor.get("instagram") or "").strip()
    fone = (sponsor.get("phone") or "").strip()
    linhas = [f"💙 PARCEIRO DO VALE: {nome}",
              "Quem mantém a informação do Norte de SC de pé é o comércio da nossa região. 🙌", ""]
    if insta:
        linhas.append(f"📲 Segue lá: {insta}")
    if fone:
        linhas.append(f"📱 Contato: {fone}")
    linhas += ["", "Prestigie quem é daqui. 💚", "",
               "Sua marca aqui também? Chama a gente no direct.", "",
               "#publi #comercio #vale #valedoitapocu #apoieocomerciolocal #radioscnews #nortedesc"]
    return "\n".join(linhas)


def run_publipost(post=False, sponsor=None):
    """Gera (e opcionalmente posta) o publipost do parceiro da semana. None se não há parceiro."""
    sponsor = sponsor or sponsor_of_the_week()
    if not sponsor:
        return {"ok": False, "motivo": "sem parceiro ativo"}
    day = datetime.now().strftime("%Y-%m-%d")
    outdir = os.path.join("instagram_posts", day + "_publipost")
    os.makedirs(outdir, exist_ok=True)
    img = slide_publipost(sponsor, outdir)
    cap = publipost_caption(sponsor)
    with open(os.path.join(outdir, "legenda.txt"), "w", encoding="utf-8") as f:
        f.write(cap)
    if post:
        import distribuidor as dist
        res = dist.publish_single(f"publi_{sponsor['id']}", img, cap)
        # RELATÓRIO DE RESULTADO: guarda o id do post no IG — é o que permite puxar o alcance
        # depois e mandar "teu post alcançou X mil" pro cliente (renovação = provar resultado).
        try:
            mid = ((res or {}).get("instagram") or {}).get("id")
            if mid:
                import sqlite3
                _c = sqlite3.connect(os.environ.get("DB_PATH", "radio_sc.db"), timeout=10)
                _c.execute("""CREATE TABLE IF NOT EXISTS sponsor_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, sponsor_id INTEGER, sponsor_name TEXT,
                    ig_media_id TEXT, posted_at TEXT)""")
                _c.execute("INSERT INTO sponsor_posts (sponsor_id, sponsor_name, ig_media_id, posted_at)"
                           " VALUES (?,?,?,?)",
                           (sponsor["id"], sponsor.get("name"), str(mid),
                            datetime.now().isoformat(timespec="seconds")))
                _c.commit()
                _c.close()
        except Exception:
            pass
    return {"ok": True, "sponsor": sponsor["name"], "img": img, "outdir": outdir, "postado": bool(post)}


def sponsor_of_the_week(conn=None):
    """Parceiro da semana: rotaciona entre os ativos pela semana do ano. None se não houver."""
    ativos = active_sponsors(conn)
    if not ativos:
        return None
    idx = datetime.now().isocalendar()[1] % len(ativos)
    return ativos[idx]
