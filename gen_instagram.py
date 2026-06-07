# -*- coding: utf-8 -*-
"""
gen_instagram.py — Gerador automatico de carrosseis para o Instagram
Radio SC News

Le as noticias TOP do dia no radio_sc.db e gera, para cada noticia:
  instagram_posts/AAAA-MM-DD/<id>/slide_1.png ... slide_N.png
  instagram_posts/AAAA-MM-DD/<id>/legenda.txt

Slides gerados por noticia:
  1) CAPA   -> imagem de fundo + cidade + manchete + "ARRASTA ->"
  2..k) RESUMO -> texto da noticia quebrado em paginas
  ultimo) CTA -> chamada para ler/ouvir no site

Uso:
  venv\\Scripts\\python.exe gen_instagram.py                 # 5 noticias do dia
  venv\\Scripts\\python.exe gen_instagram.py --limit 8       # 8 noticias
  venv\\Scripts\\python.exe gen_instagram.py --id 290        # so a noticia 290
  venv\\Scripts\\python.exe gen_instagram.py --all-cities    # inclui Brasil/SC geral
"""
import argparse
import os
import re
import sqlite3
import textwrap
from datetime import datetime
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ---------------------------------------------------------------- config
DB_PATH = os.environ.get("DB_PATH", "radio_sc.db")
OUT_BASE = "instagram_posts"
SITE = "radioscnews.com.br"
BRAND = "RADIO SC NEWS"

W, H = 1080, 1350  # formato retrato (4:5) — melhor alcance no feed

# Paleta (tema escuro do portal + vermelho de marca)
BG = (17, 18, 24)
CARD = (24, 26, 34)
RED = (231, 76, 60)
GOLD = (245, 197, 24)
WHITE = (245, 245, 247)
MUTED = (168, 170, 180)
BLACK = (0, 0, 0)

NORTE_SC = {"Schroeder", "Joinville", "Jaragua do Sul", "Jaraguá do Sul",
            "Guaramirim", "Corupa", "Corupá", "Norte de SC"}

FONTS = os.environ.get("FONTS_DIR", "C:/Windows/Fonts" if os.name == "nt" else "")

# Pasta de fontes EMPACOTADAS no projeto (caminho absoluto, nao depende do cwd do Railway).
# DejaVu Sans tem acentuacao completa (Ã, Ó, ç, etc.) e e livre para redistribuir.
_BUNDLED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

# Fallback de fontes para Linux/Railway (que nao tem as fontes do Windows).
# Ordem: fonte empacotada (sempre presente) -> dejavu do sistema -> nada.
_FONT_FALLBACK = {
    "regular": [os.path.join(_BUNDLED, "DejaVuSans.ttf"),
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    "bold":    [os.path.join(_BUNDLED, "DejaVuSans-Bold.ttf"),
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    # Impact nao existe no Linux: usa DejaVu Bold empacotada (com acentos).
    "impact":  [os.path.join(_BUNDLED, "DejaVuSans-Bold.ttf"),
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
}


def _first_existing(paths):
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None

CITY_TAGS = {
    "Joinville":      ["#joinville", "#joinvillesc", "#noticiasjoinville"],
    "Jaragua do Sul": ["#jaraguadosul", "#jaraguadosulsc", "#jaragua"],
    "Jaraguá do Sul": ["#jaraguadosul", "#jaraguadosulsc", "#jaragua"],
    "Guaramirim":     ["#guaramirim", "#guaramirimsc"],
    "Schroeder":      ["#schroeder", "#schroedersc"],
    "Corupa":         ["#corupa"],
    "Corupá":         ["#corupa"],
}
CAT_TAGS = {
    "policial": ["#policia", "#seguranca"],
    "politica": ["#politica"],
    "saude":    ["#saude"],
    "esporte":  ["#esporte", "#futebol"],
    "economia": ["#economia", "#emprego"],
    "clima":    ["#tempo", "#clima"],
    "cultura":  ["#eventos", "#cultura"],
}
BASE_TAGS = ["#santacatarina", "#nortedesc", "#noticias", "#radioscnews", "#sc"]

CAT_LABEL = {
    "policial": "POLICIAL", "politica": "POLITICA", "saude": "SAUDE",
    "esporte": "ESPORTE", "economia": "ECONOMIA", "clima": "CLIMA",
    "cultura": "CULTURA", "local": "LOCAL", "geral": "GERAL",
}


# ---------------------------------------------------------------- helpers
def font(size, bold=True, impact=False):
    kind = "impact" if impact else ("bold" if bold else "regular")
    win_name = {"impact": "impact.ttf", "bold": "arialbd.ttf", "regular": "arial.ttf"}[kind]
    candidates = []
    if FONTS:
        candidates.append(os.path.join(FONTS, win_name))
    candidates += _FONT_FALLBACK[kind]
    path = _first_existing(candidates)
    try:
        if path:
            return ImageFont.truetype(path, size)
    except Exception:
        pass
    # ultimo recurso: nunca quebra a geracao de imagem
    try:
        return ImageFont.load_default(size)
    except Exception:
        return ImageFont.load_default()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def wrap(draw, text, fnt, max_w):
    """Quebra texto em linhas que cabem em max_w pixels."""
    words = text.split()
    lines, cur = [], ""
    for wd in words:
        test = (cur + " " + wd).strip()
        if draw.textlength(test, font=fnt) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def draw_lines(draw, lines, fnt, x, y, fill, line_h, stroke=0, stroke_fill=BLACK):
    for ln in lines:
        draw.text((x, y), ln, font=fnt, fill=fill,
                  stroke_width=stroke, stroke_fill=stroke_fill)
        y += line_h
    return y


def pill(draw, x, y, text, fnt, bg, fg, pad_x=26, pad_y=14):
    w = draw.textlength(text, font=fnt)
    asc, desc = fnt.getmetrics()
    th = asc + desc
    draw.rounded_rectangle([x, y, x + w + pad_x * 2, y + th + pad_y * 2],
                           radius=(th + pad_y * 2) // 2, fill=bg)
    draw.text((x + pad_x, y + pad_y), text, font=fnt, fill=fg)
    return x + w + pad_x * 2  # x final do pill


def cover_image(image_url, admin_image):
    """Carrega imagem de fundo cobrindo 1080x1350; None se nao houver."""
    src = None
    if admin_image:
        local = admin_image.lstrip("/")
        for cand in (local, os.path.join("static", local), os.path.join("uploads", os.path.basename(local))):
            if os.path.exists(cand):
                src = cand
                break
    img = None
    try:
        if src:
            img = Image.open(src).convert("RGB")
        elif image_url:
            r = requests.get(image_url, timeout=15,
                             headers={"User-Agent": "Mozilla/5.0 (RadioSCBot/1.0)"})
            r.raise_for_status()
            img = Image.open(BytesIO(r.content)).convert("RGB")
    except Exception as e:
        print(f"   ! imagem indisponivel ({e})")
        return None
    if img is None:
        return None
    # cover crop para 1080x1350
    tw, th = W, H
    iw, ih = img.size
    scale = max(tw / iw, th / ih)
    img = img.resize((int(iw * scale), int(ih * scale)), Image.LANCZOS)
    iw, ih = img.size
    img = img.crop(((iw - tw) // 2, (ih - th) // 2,
                    (iw - tw) // 2 + tw, (ih - th) // 2 + th))
    return img


def gradient_overlay(img, top=0.35, bottom=0.92):
    """Escurece a imagem (mais embaixo) para o texto ficar legivel."""
    grad = Image.new("L", (1, H))
    for y in range(H):
        t = y / H
        a = top + (bottom - top) * (t ** 1.5)
        grad.putpixel((0, y), int(255 * a))
    alpha = grad.resize((W, H))
    black = Image.new("RGB", (W, H), BLACK)
    return Image.composite(black, img, alpha)


def brand_header(draw, y=56):
    x = pill(draw, 56, y, "  " + BRAND + "  ", font(34), RED, WHITE)
    draw.ellipse([56 + 16, y + 22, 56 + 16 + 18, y + 22 + 18], fill=WHITE)
    return x


def footer_site(draw):
    f = font(30)
    txt = SITE
    w = draw.textlength(txt, font=f)
    draw.text(((W - w) // 2, H - 70), txt, font=f, fill=MUTED)


# ---------------------------------------------------------------- slides
def slide_cover(news, outdir):
    bg = cover_image(news["image_url"], news["admin_image"])
    if bg:
        canvas = gradient_overlay(bg)
    else:
        canvas = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(canvas)

    brand_header(d)

    # tags cidade + categoria (parte de baixo, acima da manchete)
    city = news["city"] or "Santa Catarina"
    cat = CAT_LABEL.get((news["category"] or "geral"), (news["category"] or "GERAL").upper())

    # manchete
    title = re.sub(r"\s+", " ", news["title"]).strip().rstrip(".")
    fh = font(70, impact=True)
    lines = wrap(d, title.upper(), fh, W - 112)
    line_h = int(fh.size * 1.05)
    block_h = len(lines) * line_h
    y0 = H - 230 - block_h

    # pills acima do titulo
    py = y0 - 80
    xend = pill(d, 56, py, city.upper(), font(32), RED, WHITE)
    pill(d, xend + 16, py, cat, font(32), GOLD, BLACK)

    draw_lines(d, lines, fh, 56, y0, WHITE, line_h, stroke=3, stroke_fill=BLACK)

    # hint arrastar
    d.text((56, H - 110), "ARRASTA PARA O LADO  ->", font=font(34), fill=GOLD)

    path = os.path.join(outdir, "slide_1.png")
    canvas.save(path, quality=92)
    return path


def slide_text(text, idx, total_body, outdir, n):
    canvas = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(canvas)
    brand_header(d)

    fb = font(46, bold=False)
    lines = wrap(d, text, fb, W - 130)
    line_h = int(fb.size * 1.42)
    block_h = len(lines) * line_h
    y0 = max(220, (H - block_h) // 2 - 40)

    # barra vermelha lateral
    d.rounded_rectangle([56, y0 - 6, 66, y0 + block_h], radius=5, fill=RED)
    draw_lines(d, lines, fb, 92, y0, WHITE, line_h)

    if total_body > 1:
        d.text((W - 120, 64), f"{idx}/{total_body}", font=font(30), fill=MUTED)
    footer_site(d)

    path = os.path.join(outdir, f"slide_{n}.png")
    canvas.save(path, quality=92)
    return path


def slide_cta(news, outdir, n):
    canvas = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(canvas)
    brand_header(d)

    cy = H // 2 - 140

    # selo audio
    seal = "OUÇA ESTA NOTÍCIA"
    fs = font(40)
    sw = d.textlength(seal, font=fs)
    d.rounded_rectangle([(W - sw) // 2 - 34, cy - 90, (W + sw) // 2 + 34, cy - 20],
                        radius=35, fill=GOLD)
    d.text(((W - sw) // 2, cy - 78), seal, font=fs, fill=BLACK)

    big = ["LEIA E OUÇA", "A NOTÍCIA", "COMPLETA"]
    fbig = font(86, impact=True)
    y = cy + 20
    for ln in big:
        w = d.textlength(ln, font=fbig)
        d.text(((W - w) // 2, y), ln, font=fbig, fill=WHITE)
        y += int(fbig.size * 1.04)

    y += 40
    site_f = font(52)
    w = d.textlength(SITE, font=site_f)
    d.rounded_rectangle([(W - w) // 2 - 40, y - 16, (W + w) // 2 + 40, y + 74],
                        radius=20, fill=RED)
    d.text(((W - w) // 2, y), SITE, font=site_f, fill=WHITE)

    link = "LINK NA BIO"
    lf = font(38)
    w = d.textlength(link, font=lf)
    d.text(((W - w) // 2, y + 130), link, font=lf, fill=GOLD)

    path = os.path.join(outdir, f"slide_{n}.png")
    canvas.save(path, quality=92)
    return path


# ---------------------------------------------------------------- legenda
def make_caption(news):
    title = re.sub(r"\s+", " ", news["title"]).strip()
    city = news["city"] or "Santa Catarina"
    tags = []
    tags += CITY_TAGS.get(city, [])
    tags += CAT_TAGS.get(news["category"] or "", [])
    tags += BASE_TAGS
    # dedup preservando ordem
    seen, uniq = set(), []
    for t in tags:
        if t not in seen:
            seen.add(t)
            uniq.append(t)

    body = (
        f"{title}\n\n"
        f"📍 {city}\n\n"
        f"👉 Leia a matéria completa e OUÇA a notícia em áudio no nosso site:\n"
        f"🔗 {SITE} (link na bio)\n\n"
        f"Siga @radioscnews e fique por dentro de tudo que acontece no Norte de SC.\n\n"
        f"Fonte: {news['source']}\n\n"
        + " ".join(uniq)
    )
    return body


# ---------------------------------------------------------------- selecao
def pick_news(conn, limit, only_id, all_cities):
    if only_id:
        rows = conn.execute("SELECT * FROM news WHERE id=?", (only_id,)).fetchall()
        return rows

    rows = conn.execute(
        "SELECT * FROM news WHERE active=1 "
        "ORDER BY priority DESC, datetime(published_at) DESC LIMIT 200"
    ).fetchall()

    if not all_cities:
        local = [r for r in rows if (r["city"] in NORTE_SC)]
        rest = [r for r in rows if r not in local]
        rows = local + rest

    return rows[:limit]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=5, help="quantas noticias gerar")
    ap.add_argument("--id", type=int, default=None, help="gerar so esta noticia")
    ap.add_argument("--all-cities", action="store_true", help="inclui Brasil/SC geral")
    ap.add_argument("--max-body", type=int, default=2, help="max slides de resumo")
    args = ap.parse_args()

    conn = get_db()
    news_list = pick_news(conn, args.limit, args.id, args.all_cities)
    if not news_list:
        print("Nenhuma noticia encontrada.")
        return

    day = datetime.now().strftime("%Y-%m-%d")
    base = os.path.join(OUT_BASE, day)
    os.makedirs(base, exist_ok=True)

    print(f"Gerando {len(news_list)} carrosseis em {base}\n")
    for news in news_list:
        outdir = os.path.join(base, str(news["id"]))
        os.makedirs(outdir, exist_ok=True)
        print(f"-> [{news['id']}] {news['city']} | {news['title'][:55]}")

        paths = [slide_cover(news, outdir)]

        # resumo dividido em paginas
        summary = re.sub(r"\s+", " ", (news["summary"] or "")).strip()
        n = 2
        if summary:
            # ~320 chars por slide
            chunks = textwrap.wrap(summary, 320, break_long_words=False)[: args.max_body]
            for i, ch in enumerate(chunks, 1):
                paths.append(slide_text(ch, i, len(chunks), outdir, n))
                n += 1

        paths.append(slide_cta(news, outdir, n))

        with open(os.path.join(outdir, "legenda.txt"), "w", encoding="utf-8") as f:
            f.write(make_caption(news))

        print(f"   {len(paths)} slides + legenda.txt")

    conn.close()
    print(f"\nPronto! Abra a pasta: {os.path.abspath(base)}")


if __name__ == "__main__":
    main()
