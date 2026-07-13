# -*- coding: utf-8 -*-
"""
enquete.py — "Enquete do Vale" diária pro Story (engajamento em cima da NOTÍCIA).

Modelo (igual o dono faz): pega uma notícia boa de debate, monta o Story com a CAPA da notícia
(mesma cascata de imagem do feed) e o dono cola o sticker nativo "VOCÊ CONCORDA? Sim/Não".

O Instagram NÃO deixa bot colar o sticker (trava da Meta) → semi-automático: o motor faz a arte
pronta (1x/dia, scheduler) + o dono posta e cola a enquete (10s) via /admin/enquete.
Fallback: se não houver notícia boa, usa uma pergunta leve do banco local.
"""
import os
import re
import random
import sqlite3
from datetime import datetime

import gen_instagram as gi

DB_PATH = os.environ.get("DB_PATH", "radio_sc.db")
OUT_DIR = os.path.join("static", "enquete")
SW, SH = 1080, 1920  # Story 9:16

# Notícia "de debate" (rende opinião / "você concorda?"): multa, lei, decisão, aumento...
_DEBATE = re.compile(
    r"multa|lei\b|proib|aprov|aument|reduz|taxa|decis|pol[êe]mic|veta|obrigat|deveria|cobran|"
    r"reajust|fecha|libera|restri|sal[áa]rio|imposto|tarifa|projeto|propost", re.IGNORECASE)

# Banco de reserva (pergunta leve/local) — só se não houver notícia boa.
_BANCO = [
    ("Fim de semana no Vale: praia ou cachoeira?", "Praia", "Cachoeira"),
    ("Frio do Vale pede o quê?", "Cobertor", "Lareira"),
    ("Churrasco de domingo: picanha ou linguiça?", "Picanha", "Linguiça"),
    ("Chimarrão no frio: amargo ou doce?", "Amargo", "Doce"),
    ("Padaria do bairro: sonho ou cuca?", "Sonho", "Cuca"),
    ("Café do dia: com ou sem açúcar?", "Com", "Sem"),
]


def _db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _ensure(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS enquetes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, pergunta TEXT, opcao_a TEXT,
        opcao_b TEXT, contexto TEXT, image_path TEXT, created_at TEXT)""")
    cols = [r[1] for r in conn.execute("PRAGMA table_info(enquetes)")]
    if "contexto" not in cols:
        conn.execute("ALTER TABLE enquetes ADD COLUMN contexto TEXT")
    conn.commit()


# ---------------------------------------------------------------- modo NOTÍCIA (principal)
def escolher_noticia(conn):
    """Notícia boa pra enquete: recente, local/SC, NÃO sensível (morte/tragédia não combina com
    'você concorda?'), de preferência de DEBATE. None se não achar."""
    try:
        rows = conn.execute(
            "SELECT * FROM news WHERE active=1 AND title IS NOT NULL AND title!='' "
            "ORDER BY datetime(published_at) DESC LIMIT 50").fetchall()
    except Exception:
        return None
    try:
        import distribuidor
        seguros = [r for r in rows if not distribuidor.sensitive_reason(r)]
    except Exception:
        seguros = list(rows)
    if not seguros:
        return None
    local = [r for r in seguros if r["city"] in gi.NORTE_SC] or seguros
    debate = [r for r in local if _DEBATE.search(f"{r['title']} {r['summary'] or ''}")]
    pool = debate or local
    return random.choice(pool[:12])


def gerar_story_noticia(news, outdir=OUT_DIR):
    """Story 9:16 com a CAPA da notícia em cima (reusa toda a cascata de imagem + manchete) e
    espaço livre embaixo pro sticker 'Você concorda? Sim/Não'."""
    from PIL import Image, ImageDraw
    os.makedirs(outdir, exist_ok=True)
    tmp = os.path.join(outdir, "_cover")
    os.makedirs(tmp, exist_ok=True)
    try:
        import distribuidor
        flash = distribuidor.flash_manchete(news)
    except Exception:
        flash = None
    cover_path = gi.slide_cover(news, tmp, manchete=flash)        # 1080x1350, com a cascata toda
    cov = Image.open(cover_path).convert("RGB")
    if cov.size != (gi.W, gi.H):
        cov = cov.resize((gi.W, gi.H))
    cov = cov.crop((0, 0, gi.W, 1235))     # tira a faixa "ARRASTA PARA O LADO" (é Story, não carrossel)

    grad = Image.new("RGB", (1, SH))
    top, bot = (16, 17, 23), (40, 17, 22)
    for y in range(SH):
        t = y / SH
        grad.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    canvas = grad.resize((SW, SH))
    canvas.paste(cov, (0, 90))                                   # capa no topo (90..1325)
    d = ImageDraw.Draw(canvas)

    # dica discreta acima do espaço do sticker (que fica ~1430..1730)
    fh = gi.font(40)
    hint = "VOTA AÍ EMBAIXO"
    w = d.textlength(hint, font=fh)
    d.text(((SW - w) // 2, 1380), hint, font=fh, fill=gi.MUTED)

    # rodapé
    fm = gi.font(44, impact=True)
    foot = "E MARCA UM AMIGO DO VALE"
    w = d.textlength(foot, font=fm)
    d.rounded_rectangle([(SW - w) // 2 - 36, 1780, (SW + w) // 2 + 36, 1780 + 80], radius=22, fill=gi.RED)
    d.text(((SW - w) // 2, 1797), foot, font=fm, fill=gi.WHITE)

    path = os.path.join(outdir, "enquete.png")
    canvas.save(path, quality=92)
    return path


# ---------------------------------------------------------------- modo BANCO (fallback)
def gerar_story_pergunta(pergunta, outdir=OUT_DIR):
    """Story de pergunta leve (fallback) — fundo de marca + pergunta + espaço pro sticker."""
    from PIL import Image, ImageDraw
    os.makedirs(outdir, exist_ok=True)
    grad = Image.new("RGB", (1, SH))
    top, bot = (16, 17, 23), (46, 18, 24)
    for y in range(SH):
        t = y / SH
        grad.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    canvas = grad.resize((SW, SH))
    d = ImageDraw.Draw(canvas)
    gi.pill(d, 60, 96, "  " + gi.BRAND + "  ", gi.font(40), gi.RED, gi.WHITE)
    d.ellipse([60 + 18, 96 + 24, 60 + 18 + 22, 96 + 24 + 22], fill=gi.WHITE)
    fe = gi.font(54, impact=True)
    txt = "ENQUETE DO DIA"
    w = d.textlength(txt, font=fe)
    d.rounded_rectangle([(SW - w) // 2 - 36, 360, (SW + w) // 2 + 36, 444], radius=42, fill=gi.GOLD)
    d.text(((SW - w) // 2, 374), txt, font=fe, fill=gi.BLACK)
    fq = gi.font(84, impact=True)
    lines = gi.wrap(d, pergunta.upper(), fq, SW - 150)
    for _sz in (76, 68, 60, 54):
        if len(lines) <= 4:
            break
        fq = gi.font(_sz, impact=True)
        lines = gi.wrap(d, pergunta.upper(), fq, SW - 150)
    lh = int(fq.size * 1.1)
    y0 = 560
    for ln in lines[:5]:
        w = d.textlength(ln, font=fq)
        d.text(((SW - w) // 2, y0), ln, font=fq, fill=gi.WHITE, stroke_width=2, stroke_fill=gi.BLACK)
        y0 += lh
    fh = gi.font(42)
    hint = "VOTA AQUI EMBAIXO"
    w = d.textlength(hint, font=fh)
    d.text(((SW - w) // 2, 1120), hint, font=fh, fill=gi.MUTED)
    fm = gi.font(46, impact=True)
    foot = "E MARCA UM AMIGO DO VALE"
    w = d.textlength(foot, font=fm)
    d.rounded_rectangle([(SW - w) // 2 - 40, 1648, (SW + w) // 2 + 40, 1734], radius=24, fill=gi.RED)
    d.text(((SW - w) // 2, 1664), foot, font=fm, fill=gi.WHITE)
    path = os.path.join(outdir, "enquete.png")
    canvas.save(path, quality=92)
    return path


# ---------------------------------------------------------------- ENQUETE NO FEED (comment-poll)
def gerar_card_feed(pergunta, a="Sim", b="Não", outdir=OUT_DIR):
    """Card 1080x1350 pro FEED — enquete por COMENTÁRIO (auto-postável pela página, sem app).
    Pergunta + opções numeradas + 'comenta 1 ou 2'. Comentário puxa MUITO alcance no algoritmo."""
    from PIL import Image, ImageDraw
    os.makedirs(outdir, exist_ok=True)
    W, H = gi.W, gi.H
    canvas = Image.new("RGB", (W, H), gi.BG)
    d = ImageDraw.Draw(canvas)
    gi.brand_header(d)

    fs = gi.font(44, impact=True)
    seal = "ENQUETE DO VALE"
    sw = d.textlength(seal, font=fs)
    d.rounded_rectangle([(W - sw) // 2 - 30, 150, (W + sw) // 2 + 30, 220], radius=34, fill=gi.GOLD)
    d.text(((W - sw) // 2, 162), seal, font=fs, fill=gi.BLACK)

    fq = gi.font(74, impact=True)
    lines = gi.wrap(d, pergunta.upper(), fq, W - 130)
    for _sz in (64, 56, 50, 44):
        if len(lines) <= 4:
            break
        fq = gi.font(_sz, impact=True); lines = gi.wrap(d, pergunta.upper(), fq, W - 130)
    lh = int(fq.size * 1.12)
    y = 320
    for ln in lines[:5]:
        w = d.textlength(ln, font=fq)
        d.text(((W - w) // 2, y), ln, font=fq, fill=gi.WHITE, stroke_width=2, stroke_fill=gi.BLACK)
        y += lh

    y = max(y + 40, 740)
    for num, opt in (("1", a), ("2", b)):
        d.rounded_rectangle([90, y, W - 90, y + 110], radius=18, fill=gi.CARD)
        d.ellipse([122, y + 25, 182, y + 85], fill=gi.GOLD)
        fn = gi.font(46, impact=True); nw = d.textlength(num, font=fn)
        d.text((152 - nw / 2, y + 30), num, font=fn, fill=gi.BLACK)
        d.text((212, y + 28), opt[:24], font=gi.font(48, impact=True), fill=gi.WHITE)
        y += 138

    fc = gi.font(46, impact=True)
    cta = "COMENTA 1 OU 2 EMBAIXO"
    w = d.textlength(cta, font=fc)
    d.rounded_rectangle([(W - w) // 2 - 30, y + 30, (W + w) // 2 + 30, y + 110], radius=22, fill=gi.RED)
    d.text(((W - w) // 2, y + 46), cta, font=fc, fill=gi.WHITE)

    fh = gi.font(40)
    handle = "@radiosc.news"
    w = d.textlength(handle, font=fh)
    d.text(((W - w) // 2, H - 86), handle, font=fh, fill=gi.GOLD)

    path = os.path.join(outdir, "enquete_feed.png")
    canvas.save(path, quality=92)
    return path


def postar_feed(pergunta, a="Sim", b="Não"):
    """Gera o card de feed e POSTA no Instagram (feed) + Facebook. Voto por comentário. Exige tokens
    Meta. Ação manual do dono (botão). Devolve {ok, image, erro}."""
    import distribuidor as dist
    img = gerar_card_feed(pergunta, a, b)
    cap = (f"🗳️ ENQUETE DO VALE\n\n{pergunta}\n\n"
           f"1️⃣ {a}\n2️⃣ {b}\n\n"
           f"Comenta 1 ou 2 aqui embaixo 👇 e marca um amigo do Vale pra votar também!\n"
           f"Segue @radiosc.news pra mais do Vale.\n\n"
           f"#radioscnews #norteSC #valedoitapocu #enquete")
    try:
        dist.publish_single("enquete_feed", img, cap)
        return {"ok": True, "image": img}
    except Exception as e:
        return {"ok": False, "erro": str(e), "image": img}


# ---------------------------------------------------------------- entrada
def run(pergunta=None, a=None, b=None, contexto=None):
    """Gera a enquete. COM pergunta = a CUSTOMIZADA do dono (card limpo da pergunta). SEM pergunta
    = automático (notícia + 'Você concorda? Sim/Não'; fallback = banco de perguntas leves)."""
    conn = _db()
    _ensure(conn)
    pergunta = (pergunta or "").strip()
    if pergunta:                                   # CUSTOMIZADA (o dono escolheu a pergunta)
        a = (a or "Sim").strip() or "Sim"
        b = (b or "Não").strip() or "Não"
        contexto = (contexto or "").strip()
        img = gerar_story_pergunta(pergunta)
    else:                                          # AUTOMÁTICO
        news = escolher_noticia(conn)
        if news is not None:
            img = gerar_story_noticia(news)
            pergunta, a, b, contexto = "Você concorda?", "Sim", "Não", news["title"]
        else:
            pergunta, a, b = random.choice(_BANCO)
            img = gerar_story_pergunta(pergunta)
            contexto = ""
    conn.execute(
        "INSERT INTO enquetes (data, pergunta, opcao_a, opcao_b, contexto, image_path, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (datetime.now().strftime("%Y-%m-%d"), pergunta, a, b, contexto, img,
         datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
    return {"pergunta": pergunta, "a": a, "b": b, "contexto": contexto, "image": img}


def ultima():
    conn = _db()
    _ensure(conn)
    r = conn.execute("SELECT * FROM enquetes ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return dict(r) if r else None
