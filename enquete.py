# -*- coding: utf-8 -*-
"""
enquete.py — "Enquete do Vale" diária pro Story do Instagram (engajamento/participação).

O Instagram NÃO deixa bot colar o sticker de enquete (trava da Meta — só no app, na mão).
Então o motor faz 90%: escolhe a pergunta + 2 opções e gera a IMAGEM do Story pronta (9:16,
com espaço pro sticker). O dono posta (10s) e cola a enquete nativa com as 2 opções.

1x/dia (scheduler) + painel /admin/enquete (imagem pra baixar + opções pra copiar + gerar nova).
"""
import os
import re
import sqlite3
from datetime import datetime

import gen_instagram as gi

DB_PATH = os.environ.get("DB_PATH", "radio_sc.db")
OUT_DIR = os.path.join("static", "enquete")
SW, SH = 1080, 1920  # Story 9:16

# Banco de reserva (local, leve, participação) — usado se a IA estiver off. Rotaciona pelo dia.
_BANCO = [
    ("Café da manhã de domingo: pão com manteiga ou cuca?", "Pão", "Cuca"),
    ("Fim de semana no Vale: praia ou cachoeira?", "Praia", "Cachoeira"),
    ("Frio do Vale pede o quê?", "Cobertor", "Lareira"),
    ("Churrasco de domingo: picanha ou linguiça?", "Picanha", "Linguiça"),
    ("Festa junina: quentão ou pinhão?", "Quentão", "Pinhão"),
    ("Chimarrão no frio: amargo ou doce?", "Amargo", "Doce"),
    ("Padaria do bairro: sonho ou cuca?", "Sonho", "Cuca"),
    ("Melhor lugar pra relaxar: praça ou shopping?", "Praça", "Shopping"),
    ("Pôr do sol mais bonito é em qual cidade?", "Jaraguá", "Schroeder"),
    ("Trânsito na BR-280: melhorou ou piorou?", "Melhorou", "Piorou"),
    ("Sextou no Vale: balada ou sofá?", "Balada", "Sofá"),
    ("Inverno chegando: já tá no agasalho?", "Já tô", "Aguento"),
    ("Café do dia: com ou sem açúcar?", "Com", "Sem"),
    ("Domingo é dia de: dormir até tarde ou caminhada?", "Dormir", "Caminhada"),
]


def _db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _ensure(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS enquetes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, pergunta TEXT,
        opcao_a TEXT, opcao_b TEXT, image_path TEXT, created_at TEXT)""")
    conn.commit()


def pergunta_do_dia():
    """(pergunta, A, B). Tenta IA p/ variar todo dia; senão usa o banco rotativo."""
    prompt = (
        "Voce e editor da Radio SC News (Norte de SC: Jaragua do Sul, Schroeder, Guaramirim, "
        "Joinville). Crie UMA enquete curta e divertida pro Story do Instagram que faca o publico "
        "do Vale querer VOTAR (participacao). Tema leve do cotidiano/local (comida, frio, fim de "
        "semana, rotina, cidade) - NADA de politica partidaria nem tragedia. 2 opcoes curtas e "
        "opostas. Responda EXATAMENTE neste formato:\n"
        "PERGUNTA: <max 10 palavras>\nA: <max 3 palavras>\nB: <max 3 palavras>")
    try:
        import cerebro
        txt = cerebro.completar(prompt) or ""
        mp = re.search(r"(?i)pergunta:\s*(.+)", txt)
        ma = re.search(r"(?im)^\s*A[:)\-]\s*(.+)", txt)
        mb = re.search(r"(?im)^\s*B[:)\-]\s*(.+)", txt)
        if mp and ma and mb:
            p = re.sub(r"\s+", " ", mp.group(1)).strip().strip('"')[:90]
            a = re.sub(r"\s+", " ", ma.group(1)).strip().strip('"')[:18]
            b = re.sub(r"\s+", " ", mb.group(1)).strip().strip('"')[:18]
            if p and a and b:
                return p, a, b
    except Exception:
        pass
    return _BANCO[datetime.now().timetuple().tm_yday % len(_BANCO)]


def gerar_story(pergunta, opcao_a, opcao_b, outdir=OUT_DIR):
    """Imagem 9:16 do Story, pronta pro dono colar o sticker de enquete no meio."""
    from PIL import Image, ImageDraw
    os.makedirs(outdir, exist_ok=True)
    # fundo gradiente de marca (escuro -> vinho leve)
    grad = Image.new("RGB", (1, SH))
    top, bot = (16, 17, 23), (46, 18, 24)
    for y in range(SH):
        t = y / SH
        grad.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    canvas = grad.resize((SW, SH))
    d = ImageDraw.Draw(canvas)

    # brand header
    gi.pill(d, 60, 96, "  " + gi.BRAND + "  ", gi.font(40), gi.RED, gi.WHITE)
    d.ellipse([60 + 18, 96 + 24, 60 + 18 + 22, 96 + 24 + 22], fill=gi.WHITE)

    # selo ENQUETE DO DIA
    fe = gi.font(54, impact=True)
    txt = "ENQUETE DO DIA"
    w = d.textlength(txt, font=fe)
    d.rounded_rectangle([(SW - w) // 2 - 36, 360, (SW + w) // 2 + 36, 360 + 84], radius=42, fill=gi.GOLD)
    d.text(((SW - w) // 2, 374), txt, font=fe, fill=gi.BLACK)

    # pergunta (grande, centralizada, adaptativa)
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

    # hint de onde vai o sticker (área central livre ~1150-1480)
    fh = gi.font(42)
    hint = "VOTA AQUI EMBAIXO"
    w = d.textlength(hint, font=fh)
    d.text(((SW - w) // 2, 1120), hint, font=fh, fill=gi.MUTED)

    # rodapé: chamada de marcação + handle
    fm = gi.font(46, impact=True)
    foot = "E MARCA UM AMIGO DO VALE"
    w = d.textlength(foot, font=fm)
    d.rounded_rectangle([(SW - w) // 2 - 40, 1648, (SW + w) // 2 + 40, 1648 + 86], radius=24, fill=gi.RED)
    d.text(((SW - w) // 2, 1664), foot, font=fm, fill=gi.WHITE)
    fh2 = gi.font(48)
    h = "@radioscnews"
    w = d.textlength(h, font=fh2)
    d.text(((SW - w) // 2, 1772), h, font=fh2, fill=gi.GOLD)

    path = os.path.join(outdir, "enquete.png")
    canvas.save(path, quality=92)
    return path


def run():
    """Gera a enquete do dia (pergunta + opções + imagem) e salva. NÃO posta (sticker é manual)."""
    p, a, b = pergunta_do_dia()
    img = gerar_story(p, a, b)
    conn = _db()
    _ensure(conn)
    conn.execute(
        "INSERT INTO enquetes (data, pergunta, opcao_a, opcao_b, image_path, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (datetime.now().strftime("%Y-%m-%d"), p, a, b, img,
         datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
    return {"pergunta": p, "a": a, "b": b, "image": img}


def ultima():
    """Última enquete gerada (pro painel admin), ou None."""
    conn = _db()
    _ensure(conn)
    r = conn.execute("SELECT * FROM enquetes ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return dict(r) if r else None
