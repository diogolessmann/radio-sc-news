# -*- coding: utf-8 -*-
"""
bom_dia.py — Produto-bandeira diario "Bom dia, Vale" — Radio SC News

A ancora do habito: todo dia de manha, um carrossel + uma mensagem de WhatsApp com
  - TEMPO das cidades do Vale (Schroeder, Jaragua, Guaramirim)
  - AS 3 DE HOJE (top 3 manchetes do Norte de SC)
  - VOCE SABIA (curiosidade da regiao, rotativa)
  - convite de comunidade ("manda pra gente")

Reaproveita o visual/marca do gen_instagram.py.

USO:
  venv\\Scripts\\python.exe bom_dia.py            # gera carrossel + whatsapp.txt
  venv\\Scripts\\python.exe bom_dia.py --print    # so mostra a mensagem de WhatsApp

Sem OPENWEATHER_API_KEY: o bloco de tempo e omitido com elegancia (resto sai normal).
"""
import argparse
import os
import sqlite3
import sys
from datetime import datetime

from PIL import Image, ImageDraw

import gen_instagram as gi

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DB_PATH = os.environ.get("DB_PATH", "radio_sc.db")
SITE = gi.SITE
W, H = gi.W, gi.H
BG, RED, GOLD, WHITE, MUTED, BLACK = gi.BG, gi.RED, gi.GOLD, gi.WHITE, gi.MUTED, gi.BLACK
WA_LINE = os.environ.get("WA_COMMUNITY", "(47) 99999-9999")  # numero p/ receber flagrantes

OUT_BASE = "instagram_posts"

# ------ data em PT-BR (sem depender de locale do SO) ------
_DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
         "sexta-feira", "sábado", "domingo"]
_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
          "agosto", "setembro", "outubro", "novembro", "dezembro"]


def data_extenso(dt=None):
    dt = dt or datetime.now()
    return f"{_DIAS[dt.weekday()]}, {dt.day} de {_MESES[dt.month - 1]}"


# ------ curiosidades rotativas do Vale (giram por dia do ano) ------
CURIOSIDADES = [
    "Schroeder nasceu da colonizacao alema e seu nome homenageia um dos primeiros imigrantes da regiao.",
    "Jaragua do Sul e um dos maiores polos industriais de Santa Catarina, sede da multinacional WEG.",
    "O Vale do Itapocu leva o nome do rio Itapocu, que corta varias cidades da regiao.",
    "Guaramirim e conhecida como a 'Cidade Porta de Entrada do Vale do Itapocu'.",
    "Corupa abriga a Rota das Cachoeiras, com dezenas de quedas d'agua em meio a Mata Atlantica.",
    "A regiao Norte de SC tem forte tradicao germanica, visivel na arquitetura, na culinaria e nas festas.",
    "O Morro do Boa Vista, em Jaragua, e um dos cartoes-postais da regiao e ponto de voo livre.",
]


def curiosidade_do_dia(dt=None):
    dt = dt or datetime.now()
    return CURIOSIDADES[dt.timetuple().tm_yday % len(CURIOSIDADES)]


# ------ dados ------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def top_headlines(conn, n=3):
    rows = conn.execute(
        "SELECT * FROM news WHERE active=1 "
        "ORDER BY priority DESC, datetime(published_at) DESC LIMIT 200"
    ).fetchall()
    local = [r for r in rows if r["city"] in gi.NORTE_SC]
    pool = local if len(local) >= n else (local + [r for r in rows if r not in local])
    return pool[:n]


def get_weather_vale():
    """Tempo das 3 cidades do Vale. Lista vazia se nao houver chave/erro."""
    try:
        from weather import fetch_all_weather
        alvo = {"Schroeder", "Jaraguá do Sul", "Guaramirim"}
        return [w for w in fetch_all_weather() if w["city"] in alvo]
    except Exception:
        return []


# ------ slides ------
def _canvas():
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


def slide_capa(outdir, n=1):
    img, d = _canvas()
    gi.brand_header(d)
    # sol
    d.ellipse([W // 2 - 70, 300, W // 2 + 70, 440], fill=GOLD)
    big = ["BOM DIA,", "VALE!"]
    fbig = gi.font(150, impact=True)
    y = 520
    for ln in big:
        w = d.textlength(ln, font=fbig)
        d.text(((W - w) // 2, y), ln, font=fbig, fill=WHITE, stroke_width=3, stroke_fill=BLACK)
        y += int(fbig.size * 1.0)
    # data
    fd = gi.font(44)
    data = data_extenso()
    w = d.textlength(data, font=fd)
    gi.pill(d, (W - w) // 2 - 30, y + 30, data, fd, RED, WHITE)
    # tagline
    ft = gi.font(40, bold=False)
    tag = "O resumo da manha no Norte de SC"
    w = d.textlength(tag, font=ft)
    d.text(((W - w) // 2, y + 150), tag, font=ft, fill=MUTED)
    d.text((56, H - 110), "ARRASTA PARA O LADO  ->", font=gi.font(34), fill=GOLD)
    p = os.path.join(outdir, f"slide_{n}.png")
    img.save(p, quality=92)
    return p


def slide_titulo(d, titulo, emoji=""):
    # Emoji nao renderiza na fonte Impact (vira quadradinho) -> so texto na imagem.
    ft = gi.font(58, impact=True)
    gi.pill(d, 56, 150, titulo, ft, RED, WHITE)


def slide_tempo(weather, outdir, n):
    img, d = _canvas()
    gi.brand_header(d)
    slide_titulo(d, "O TEMPO HOJE")
    y = 330
    if weather:
        for w in weather:
            linha = f"{w['icon']}  {w['city']}"
            d.text((70, y), linha, font=gi.font(54), fill=WHITE)
            temp = f"{w['temp']}°C"
            tw = d.textlength(temp, font=gi.font(60, impact=True))
            d.text((W - 70 - tw, y - 4), temp, font=gi.font(60, impact=True), fill=GOLD)
            desc = (w["description"] or "").capitalize()
            d.text((70, y + 72), desc, font=gi.font(38, bold=False), fill=MUTED)
            y += 180
    else:
        d.text((70, y), "Confira o tempo atualizado", font=gi.font(50), fill=WHITE)
        d.text((70, y + 70), f"no site: {SITE}", font=gi.font(44, bold=False), fill=MUTED)
    gi.footer_site(d)
    p = os.path.join(outdir, f"slide_{n}.png")
    img.save(p, quality=92)
    return p


def slide_manchetes(headlines, outdir, n):
    img, d = _canvas()
    gi.brand_header(d)
    slide_titulo(d, "AS 3 DE HOJE", "📰")
    y = 320
    for i, h in enumerate(headlines, 1):
        num = f"{i}"
        d.ellipse([56, y, 56 + 64, y + 64], fill=RED)
        nw = d.textlength(num, font=gi.font(40, impact=True))
        d.text((56 + (64 - nw) / 2, y + 8), num, font=gi.font(40, impact=True), fill=WHITE)
        titulo = " ".join((h["title"] or "").split())
        lines = gi.wrap(d, titulo, gi.font(42), W - 200)[:3]
        gi.draw_lines(d, lines, gi.font(42), 150, y, WHITE, int(42 * 1.3))
        y += max(150, len(lines) * int(42 * 1.3) + 50)
    gi.footer_site(d)
    p = os.path.join(outdir, f"slide_{n}.png")
    img.save(p, quality=92)
    return p


def slide_curiosidade(texto, outdir, n):
    img, d = _canvas()
    gi.brand_header(d)
    slide_titulo(d, "VOCÊ SABIA?", "💡")
    fb = gi.font(50, bold=False)
    lines = gi.wrap(d, texto, fb, W - 130)
    line_h = int(fb.size * 1.42)
    y0 = max(320, (H - len(lines) * line_h) // 2 - 40)
    d.rounded_rectangle([56, y0 - 6, 66, y0 + len(lines) * line_h], radius=5, fill=GOLD)
    gi.draw_lines(d, lines, fb, 92, y0, WHITE, line_h)
    gi.footer_site(d)
    p = os.path.join(outdir, f"slide_{n}.png")
    img.save(p, quality=92)
    return p


def slide_cta(outdir, n):
    img, d = _canvas()
    gi.brand_header(d)
    cy = H // 2 - 160
    seal = "VIU ALGO NA CIDADE?"
    fs = gi.font(44)
    sw = d.textlength(seal, font=fs)
    gi.pill(d, (W - sw) // 2 - 30, cy - 90, seal, fs, GOLD, BLACK)
    big = ["MANDA PRA", "GENTE!"]
    fbig = gi.font(96, impact=True)
    y = cy + 20
    for ln in big:
        w = d.textlength(ln, font=fbig)
        d.text(((W - w) // 2, y), ln, font=fbig, fill=WHITE)
        y += int(fbig.size * 1.04)
    sub = "Foto, flagrante ou novidade no WhatsApp"
    fsub = gi.font(38, bold=False)
    w = d.textlength(sub, font=fsub)
    d.text(((W - w) // 2, y + 20), sub, font=fsub, fill=MUTED)
    site_f = gi.font(50)
    w = d.textlength(SITE, font=site_f)
    d.rounded_rectangle([(W - w) // 2 - 40, y + 110, (W + w) // 2 + 40, y + 200],
                        radius=20, fill=RED)
    d.text(((W - w) // 2, y + 126), SITE, font=site_f, fill=WHITE)
    p = os.path.join(outdir, f"slide_{n}.png")
    img.save(p, quality=92)
    return p


# ------ WhatsApp ------
def whatsapp_bomdia(weather, headlines, curiosidade):
    linhas = [f"☀️ *BOM DIA, VALE!* — {data_extenso()}", ""]
    if weather:
        linhas.append("🌡️ *Tempo agora:*")
        for w in weather:
            linhas.append(f"{w['icon']} {w['city']}: {w['temp']}°C, {w['description']}")
        linhas.append("")
    linhas.append("📰 *As 3 de hoje:*")
    for i, h in enumerate(headlines, 1):
        linhas.append(f"{i}. {' '.join((h['title'] or '').split())}")
    linhas += ["", f"💡 *Você sabia?* {curiosidade}", ""]
    linhas += ["👀 Viu algo na cidade? *Manda pra gente!*",
               f"👉 Tudo no site: {SITE}"]
    return "\n".join(linhas)


# ------ legenda Instagram (a partir do texto do WhatsApp) ------
BASE_TAGS = "#bomdia #nortedesc #valedoitapocu #schroeder #jaraguadosul #guaramirim #radioscnews #santacatarina"


def ig_caption(zap):
    corpo = zap.replace("*", "")  # IG nao usa *negrito*
    return f"{corpo}\n\n{BASE_TAGS}"


# ------ geracao + execucao ------
def generate(outdir=None):
    """Gera os 5 slides + textos. Retorna (paths, zap, ig)."""
    conn = get_db()
    headlines = top_headlines(conn, 3)
    weather = get_weather_vale()
    curiosidade = curiosidade_do_dia()
    conn.close()
    if not headlines:
        raise RuntimeError("Sem manchetes no banco — rode o scraper antes.")

    if outdir is None:
        day = datetime.now().strftime("%Y-%m-%d")
        outdir = os.path.join(OUT_BASE, day + "_bomdia")
    os.makedirs(outdir, exist_ok=True)

    paths = [
        slide_capa(outdir, 1),
        slide_tempo(weather, outdir, 2),
        slide_manchetes(headlines, outdir, 3),
        slide_curiosidade(curiosidade, outdir, 4),
        slide_cta(outdir, 5),
    ]
    zap = whatsapp_bomdia(weather, headlines, curiosidade)
    with open(os.path.join(outdir, "whatsapp.txt"), "w", encoding="utf-8") as f:
        f.write(zap)
    return paths, zap, ig_caption(zap), weather


def run(post=False):
    """Ponto de entrada do scheduler. Gera o Bom dia Vale e (se post) publica IG+FB."""
    paths, zap, cap, weather = generate()
    print(f"[bom_dia] {len(paths)} slides | tempo: {'OK' if weather else 'sem chave'}")
    if post:
        from distribuidor import publish_images
        day = datetime.now().strftime("%Y%m%d")
        publish_images(f"bomdia_{day}", paths, cap)
        print("[bom_dia] publicado no IG + FB.")
    return paths, zap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true", help="so mostra a msg de WhatsApp")
    ap.add_argument("--post", action="store_true", help="publica no IG+FB (precisa tokens Meta)")
    args = ap.parse_args()

    if args.print:
        _, zap, _, _ = generate()
        print(zap)
        return

    paths, zap = run(post=args.post)
    print(f"\nBom dia Vale pronto: {len(paths)} slides.")
    print("\n----- WHATSAPP -----")
    print(zap)


if __name__ == "__main__":
    main()
