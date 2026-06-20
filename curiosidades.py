# -*- coding: utf-8 -*-
"""
curiosidades.py — "VOCÊ SABIA?" das cidades do Vale (conteúdo 100% NOSSO).

Motor de conteúdo próprio pros DIAS FRACOS de notícia: carrossel de curiosidade sobre
Jaraguá do Sul, Schroeder, Corupá, Joinville e Guaramirim. Orgulho local = compartilhamento.
Fato livre + nosso texto + nossa imagem (arsenal static/bg) = 100% legal e on-brand.

Segue o padrão da Enquete: o scheduler GERA o carrossel (1-2x/semana) e o dono revisa + posta
em /admin/curiosidade. Não auto-posta (conteúdo novo merece olho humano antes de escalar).

IMPORTANTE: o banco abaixo é curado com fatos CONHECIDOS e conservadores (sem número/data
arriscado). Antes de aumentar o volume, confira cada fato. Reusa gen_instagram (zero dependência nova).

Uso:
  python curiosidades.py            # gera o carrossel do dia (preview)
  curiosidades.run()                # idem (scheduler)
"""
import glob
import os
import random
import re
import sqlite3
import unicodedata
from datetime import datetime

from PIL import Image, ImageDraw

import gen_instagram as gi

DB_PATH = os.environ.get("DB_PATH", "radio_sc.db")
OUT_BASE = os.path.join("static", "curiosidades")
BG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "bg")

# Banco curado: cidade -> lista de itens. Cada item = (gancho_curto, [fato1, fato2, fato3]).
# Fatos conservadores e conhecidos. CONFIRA antes de escalar; evite número/data sem certeza.
CURIOSIDADES = {
    "Joinville": [
        ("Joinville é gigante (e cheia de apelidos)", [
            "É a MAIOR cidade de Santa Catarina em população.",
            "Ganhou o apelido de Cidade das Flores — e também das Bicicletas.",
            "Abriga a única escola do Teatro Bolshoi fora da Rússia.",
        ]),
        ("A cidade que dança", [
            "Sedia o Festival de Dança de Joinville, um dos maiores do mundo.",
            "O nome é uma homenagem ao Príncipe de Joinville, da França.",
            "A herança alemã marca a arquitetura e a cultura local.",
        ]),
    ],
    "Jaraguá do Sul": [
        ("O peso industrial do Vale", [
            "É a casa da WEG, multinacional de motores elétricos nascida aqui.",
            "A indústria forte faz dela uma das cidades mais ricas de SC.",
            "A colonização alemã e italiana marca a cultura local.",
        ]),
        ("Tradição e natureza", [
            "A Schützenfest celebra a tradição dos atiradores (herança alemã).",
            "O Morro da Boa Vista é cartão-postal e ponto de aventura.",
            "O nome 'Jaraguá' tem origem tupi-guarani.",
        ]),
    ],
    "Schroeder": [
        ("Pequena, alemã e trabalhadora", [
            "Tem forte herança da colonização alemã.",
            "Fica no Vale do Itapocu, vizinha de Jaraguá do Sul.",
            "Apesar de pequena, tem indústria e comércio ativos.",
        ]),
        ("Raízes que seguem vivas", [
            "O nome vem de um sobrenome alemão ligado à colonização.",
            "As tradições germânicas seguem presentes no dia a dia.",
            "Está no coração do Norte catarinense.",
        ]),
    ],
    "Corupá": [
        ("A capital das cachoeiras", [
            "É conhecida pela Rota das Cachoeiras, com dezenas de quedas d'água.",
            "Reúne uma das maiores concentrações de cachoeiras do Sul.",
            "É cercada de Mata Atlântica preservada.",
        ]),
        ("Terra da banana", [
            "É uma grande produtora de banana de Santa Catarina.",
            "Guarda forte tradição ferroviária na sua história.",
            "Mistura colonização alemã com belezas naturais.",
        ]),
    ],
    "Guaramirim": [
        ("O corredor do Vale", [
            "Fica às margens da BR-280, um corredor logístico importante.",
            "Virou polo industrial e de distribuição no Norte de SC.",
            "A localização estratégica atrai empresas e empregos.",
        ]),
        ("Raízes do nome", [
            "O nome 'Guaramirim' tem origem tupi.",
            "A colonização alemã marca a cultura e a culinária.",
            "Faz parte da região do Vale do Itapocu.",
        ]),
    ],
}

_HASHTAGS = {
    "Joinville": "#joinville #joinvillesc",
    "Jaraguá do Sul": "#jaraguadosul #jaragua",
    "Schroeder": "#schroeder #schroedersc",
    "Corupá": "#corupa #corupasc",
    "Guaramirim": "#guaramirim",
}


def _norm(s):
    t = unicodedata.normalize("NFKD", (s or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")


def _db():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def _ensure(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS curiosidades_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, cidade TEXT, idx INTEGER,
        gancho TEXT, pasta TEXT, created_at TEXT)""")
    conn.commit()


def _city_bg(cidade):
    """Imagem do arsenal da cidade (rotaciona variações). None se não houver."""
    slug = "cidade_" + _norm(cidade)
    cands = []
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        cands += glob.glob(os.path.join(BG_DIR, slug + ext))
        cands += glob.glob(os.path.join(BG_DIR, slug + "-*" + ext))
    return random.choice(cands) if cands else None


# ----------------------------------------------------------------- slides
def _capa(cidade, gancho, bg_path, outdir, n):
    if bg_path:
        canvas = Image.open(bg_path).convert("RGB").resize((gi.W, gi.H))
        canvas = Image.blend(canvas, Image.new("RGB", (gi.W, gi.H), gi.BLACK), 0.58)
    else:
        canvas = Image.new("RGB", (gi.W, gi.H), gi.BG)
    d = ImageDraw.Draw(canvas)
    gi.brand_header(d)

    # selo "VOCÊ SABIA?" dourado
    fs = gi.font(58, impact=True)
    seal = "VOCÊ SABIA?"
    sw = d.textlength(seal, font=fs)
    d.rounded_rectangle([(gi.W - sw) // 2 - 38, 470, (gi.W + sw) // 2 + 38, 556], radius=44, fill=gi.GOLD)
    d.text(((gi.W - sw) // 2, 484), seal, font=fs, fill=gi.BLACK)

    # cidade GRANDE
    fc = gi.font(104, impact=True)
    cw = d.textlength(cidade.upper(), font=fc)
    if cw > gi.W - 90:
        fc = gi.font(80, impact=True); cw = d.textlength(cidade.upper(), font=fc)
    d.text(((gi.W - cw) // 2, 600), cidade.upper(), font=fc, fill=gi.WHITE,
           stroke_width=3, stroke_fill=gi.BLACK)

    # gancho (wrap)
    fg = gi.font(44, bold=False)
    lines = gi.wrap(d, gancho, fg, gi.W - 150)
    y = 760
    for ln in lines[:3]:
        w = d.textlength(ln, font=fg)
        d.text(((gi.W - w) // 2, y), ln, font=fg, fill=gi.MUTED, stroke_width=1, stroke_fill=gi.BLACK)
        y += int(fg.size * 1.3)

    # "ARRASTA ->"
    fa = gi.font(38, impact=True)
    arr = "ARRASTA  ->"
    aw = d.textlength(arr, font=fa)
    d.rounded_rectangle([(gi.W - aw) // 2 - 28, 1230, (gi.W + aw) // 2 + 28, 1300], radius=20, fill=gi.RED)
    d.text(((gi.W - aw) // 2, 1244), arr, font=fa, fill=gi.WHITE)

    path = os.path.join(outdir, f"slide_{n}.png")
    canvas.save(path, quality=92)
    return path


def _fato(fato, idx, total, outdir, n):
    canvas = Image.new("RGB", (gi.W, gi.H), gi.BG)
    d = ImageDraw.Draw(canvas)
    gi.brand_header(d)

    # badge FATO idx
    gi.pill(d, 56, 150, f"  FATO {idx}  ", gi.font(40, impact=True), gi.RED, gi.WHITE)

    fb = gi.font(64, impact=True)
    lines = gi.wrap(d, fato, fb, gi.W - 130)
    for _sz in (56, 50, 46):
        if len(lines) <= 6:
            break
        fb = gi.font(_sz, impact=True); lines = gi.wrap(d, fato, fb, gi.W - 130)
    line_h = int(fb.size * 1.34)
    block_h = len(lines) * line_h
    y0 = max(300, (gi.H - block_h) // 2 - 30)
    d.rounded_rectangle([56, y0 - 6, 66, y0 + block_h], radius=5, fill=gi.GOLD)
    gi.draw_lines(d, lines, fb, 92, y0, gi.WHITE, line_h, stroke=2, stroke_fill=gi.BLACK)

    d.text((gi.W - 120, 64), f"{idx}/{total}", font=gi.font(30), fill=gi.MUTED)
    gi.footer_site(d)

    path = os.path.join(outdir, f"slide_{n}.png")
    canvas.save(path, quality=92)
    return path


def _cta(cidade, outdir, n):
    canvas = Image.new("RGB", (gi.W, gi.H), gi.BG)
    d = ImageDraw.Draw(canvas)
    gi.brand_header(d)
    cy = gi.H // 2 - 210

    seal = "SABIA DISSO?"
    fs = gi.font(40, impact=True)
    sw = d.textlength(seal, font=fs)
    d.rounded_rectangle([(gi.W - sw) // 2 - 32, cy - 84, (gi.W + sw) // 2 + 32, cy - 8], radius=34, fill=gi.GOLD)
    d.text(((gi.W - sw) // 2, cy - 72), seal, font=fs, fill=gi.BLACK)

    big = ["MARCA QUEM", "É DE", cidade.upper()]
    fbig = gi.font(86, impact=True)
    if d.textlength(cidade.upper(), font=fbig) > gi.W - 80:
        fbig = gi.font(64, impact=True)
    y = cy + 30
    for ln in big:
        f = fbig
        w = d.textlength(ln, font=f)
        d.text(((gi.W - w) // 2, y), ln, font=f, fill=gi.WHITE, stroke_width=2, stroke_fill=gi.BLACK)
        y += int(fbig.size * 1.06)

    y += 56
    mark = "COMENTA 👇 E COMPARTILHA"
    fm = gi.font(38)
    w = d.textlength(mark, font=fm)
    d.rounded_rectangle([(gi.W - w) // 2 - 34, y - 14, (gi.W + w) // 2 + 34, y + 62], radius=20, fill=gi.RED)
    d.text(((gi.W - w) // 2, y), mark, font=fm, fill=gi.WHITE)

    y += 120
    handle = "@radioscnews"
    fh = gi.font(52)
    w = d.textlength(handle, font=fh)
    d.text(((gi.W - w) // 2, y), handle, font=fh, fill=gi.GOLD)

    path = os.path.join(outdir, f"slide_{n}.png")
    canvas.save(path, quality=92)
    return path


# ----------------------------------------------------------------- escolha + run
def escolher(conn):
    """Escolhe (cidade, idx) menos repetido recentemente, pra rotacionar todas as cidades."""
    flat = [(cid, i, item[0], item[1])
            for cid, itens in CURIOSIDADES.items() for i, item in enumerate(itens)]
    try:
        usados = [f"{r['cidade']}|{r['idx']}" for r in conn.execute(
            "SELECT cidade, idx FROM curiosidades_log ORDER BY id DESC LIMIT ?", (len(flat),))]
    except Exception:
        usados = []
    novos = [x for x in flat if f"{x[0]}|{x[1]}" not in usados]
    return random.choice(novos or flat)


def _legenda(cidade, gancho, fatos):
    tags = f"{_HASHTAGS.get(cidade, '')} #radioscnews #norteSC #valedoitapocu #vocesabia"
    corpo = "\n".join(f"• {f}" for f in fatos)
    return (f"VOCÊ SABIA? 👀 {gancho} — {cidade}\n\n{corpo}\n\n"
            f"Marca quem é de {cidade} e compartilha esse orgulho! 💚\n"
            f"Segue @radioscnews pra mais do Vale.\n\n{tags.strip()}")


def run(post=False):
    """Gera o carrossel de curiosidade do dia (preview). post=True fica pra quando o dono liberar."""
    conn = _db()
    _ensure(conn)
    cidade, idx, gancho, fatos = escolher(conn)

    dia = datetime.now().strftime("%Y-%m-%d")
    outdir = os.path.join(OUT_BASE, dia, f"{_norm(cidade)}_{idx}")
    os.makedirs(outdir, exist_ok=True)

    slides = [_capa(cidade, gancho, _city_bg(cidade), outdir, 1)]
    for i, fato in enumerate(fatos, 1):
        slides.append(_fato(fato, i, len(fatos), outdir, len(slides) + 1))
    slides.append(_cta(cidade, outdir, len(slides) + 1))

    legenda = _legenda(cidade, gancho, fatos)
    with open(os.path.join(outdir, "legenda.txt"), "w", encoding="utf-8") as f:
        f.write(legenda)

    conn.execute(
        "INSERT INTO curiosidades_log (cidade, idx, gancho, pasta, created_at) VALUES (?,?,?,?,?)",
        (cidade, idx, gancho, outdir, datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
    return {"cidade": cidade, "gancho": gancho, "slides": slides,
            "pasta": outdir, "legenda": legenda, "postado": False}


def ultima():
    conn = _db()
    _ensure(conn)
    r = conn.execute("SELECT * FROM curiosidades_log ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return dict(r) if r else None


if __name__ == "__main__":
    out = run()
    print(f"Curiosidade gerada: {out['cidade']} — {out['gancho']}")
    print(f"{len(out['slides'])} slides em {out['pasta']}")
