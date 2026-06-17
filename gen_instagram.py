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
from PIL import Image, ImageDraw, ImageFont

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
WHATS = (37, 211, 102)   # verde do WhatsApp (CTA do Canal — audiência própria)
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
# Playbook 2026: 3-5 hashtags hiperlocais > enxurrada genérica. As de CIDADE (CITY_TAGS) são o
# ouro; aqui só região + marca (cortado #noticias/#sc genéricos, que não geram descoberta local).
BASE_TAGS = ["#nortedesc", "#radioscnews", "#santacatarina"]

# Foto ilustrativa do banco livre (Pexels) SÓ entra onde a imagem genérica COMBINA com o tema
# (bola no esporte, céu no clima). Nas outras categorias, foto aleatória vira "gringa sem nexo"
# (já saiu favela na notícia da Ana Castela, viatura dos EUA em acidente, igreja de MG em SC...)
# → melhor o CARD DE MARCA. Configurável via env IMG_LIVRE_CATS (csv); "none"/vazio = nunca Pexels.
_ILUSTRA_CATS = set(
    c.strip().lower() for c in os.environ.get("IMG_LIVRE_CATS", "esporte,clima").split(",")
    if c.strip() and c.strip().lower() != "none"
)

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


def brand_card_bg():
    """Fundo do CARD DE MARCA (quando não há foto PRÓPRIA relevante): gradiente sóbrio
    escuro→vinho leve, pra não ficar chapado. É 100% nosso (legal) e on-brand — melhor que
    jogar uma foto ilustrativa sem nexo."""
    grad = Image.new("RGB", (1, H))
    top, bot = (14, 15, 20), (38, 18, 22)   # toque leve do vermelho de marca embaixo
    for y in range(H):
        t = y / H
        grad.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    return grad.resize((W, H))


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
def slide_cover_foto_faixa(news, img_path, outdir, manchete=None, credito=None):
    """Capa LAYOUT FOTO+FAIXA: foto REAL do local em cima (mantém o '© Google' visível, exigência
    da licença do Maps), faixa de marca embaixo com pills + manchete. Usada quando a imagem vem do
    Street View / mapa do Google — o texto NÃO pode ir por cima do logo deles."""
    BAND_TOP = 900
    canvas = Image.new("RGB", (W, H), BG)
    # foto no topo (0..BAND_TOP): cobre a largura e fica ALINHADA EMBAIXO (preserva a base da
    # imagem, onde fica a atribuição do Google — nunca cortar nem tampar).
    try:
        im = Image.open(img_path).convert("RGB")
        scale = max(W / im.width, BAND_TOP / im.height)
        im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
        left = (im.width - W) // 2
        top = im.height - BAND_TOP          # bottom-align
        im = im.crop((left, top, left + W, top + BAND_TOP))
        canvas.paste(im, (0, 0))
    except Exception:
        pass
    d = ImageDraw.Draw(canvas)

    # leve sombra no topo da foto p/ o brand header ler bem
    shade = Image.new("L", (1, 170))
    for y in range(170):
        shade.putpixel((0, y), int(175 * (1 - y / 170)))
    sh = shade.resize((W, 170))
    top_region = canvas.crop((0, 0, W, 170))
    canvas.paste(Image.composite(Image.new("RGB", (W, 170), BLACK), top_region, sh), (0, 0))
    d = ImageDraw.Draw(canvas)

    brand_header(d)

    # FAIXA de marca embaixo (sólida) + filete vermelho no topo dela
    d.rectangle([0, BAND_TOP, W, H], fill=BG)
    d.rectangle([0, BAND_TOP, W, BAND_TOP + 6], fill=RED)

    city = news["city"] or "Santa Catarina"
    cat = CAT_LABEL.get((news["category"] or "geral"), (news["category"] or "GERAL").upper())
    py = BAND_TOP + 34
    xend = pill(d, 56, py, city.upper(), font(30), RED, WHITE)
    pill(d, xend + 14, py, cat, font(30), GOLD, BLACK)

    # manchete (TikTok mode) — fonte adaptativa p/ caber na faixa
    title = re.sub(r"\s+", " ", (manchete or news["title"])).strip().rstrip(".")
    fh = font(56, impact=True)
    lines = wrap(d, title.upper(), fh, W - 112)
    for _sz in (50, 46, 42):
        if len(lines) <= 4:
            break
        fh = font(_sz, impact=True)
        lines = wrap(d, title.upper(), fh, W - 112)
    line_h = int(fh.size * 1.06)
    draw_lines(d, lines[:4], fh, 56, py + 78, WHITE, line_h)

    # ARRASTA + crédito honesto da fonte da imagem
    d.text((56, H - 68), "ARRASTA PARA O LADO  ->", font=font(30), fill=GOLD)
    cr = credito or "Imagem: Google"
    fc = font(24, bold=False)
    cw = d.textlength(cr, font=fc)
    d.text((W - 56 - cw, H - 62), cr, font=fc, fill=MUTED)

    path = os.path.join(outdir, "slide_1.png")
    canvas.save(path, quality=92)
    return path


def slide_cover(news, outdir, manchete=None):
    # 🛡️ ANTI-PROCESSO: por padrão NÃO usa foto de TERCEIRO (nem a og:image da fonte, nem foto de
    # outro portal). O FATO é livre; a FOTO deles não é. Só foto PRÓPRIA (admin), stock regional
    # (própria), arte de IA ou card de marca. Desliga com ANTI_STRIKE=0 (por sua conta e risco).
    anti = os.environ.get("ANTI_STRIKE", "1").strip() != "0"
    bg = cover_image(None if anti else news["image_url"], news["admin_image"])
    foto_credito = None
    ilustrativa = False
    if not bg and not anti:
        # fotobusca (foto de OUTRO portal, com crédito) — só FORA do modo anti-strike
        try:
            import fotobusca
            try:
                _nid = news["id"]
            except Exception:
                _nid = 0
            _url, _src = fotobusca.achar_foto(news["title"], _nid)
            if _url:
                bg = cover_image(_url, None)
                if bg:
                    foto_credito = _src
        except Exception:
            pass
    if not bg:
        # 2) STOCK REGIONAL: foto do banco próprio por cidade (Jaraguá/Schroeder/...).
        #    Fallback bonito e 100% legal (foto do dono) — cara do Vale, sem card preto.
        try:
            import stockfoto
            # foto PRÓPRIA: landmark por assunto (prefeitura/hospital/BR-280...) -> foto da cidade
            _sp = stockfoto.achar_landmark(news) or stockfoto.achar_stock(news["city"])
            if _sp:
                _si = Image.open(_sp).convert("RGB")
                _sc = max(W / _si.width, H / _si.height)
                _si = _si.resize((int(_si.width * _sc), int(_si.height * _sc)))
                bg = _si.crop(((_si.width - W) // 2, (_si.height - H) // 2,
                               (_si.width - W) // 2 + W, (_si.height - H) // 2 + H))
        except Exception:
            pass
    if not bg:
        # 2.4) GEO: foto REAL do local (Street View) ou mapa do Google. Layout FOTO+FAIXA (a
        #      atribuição do Google fica visível; texto não vai por cima) → retorna direto aqui.
        try:
            import streetview
            _gp, _tipo = streetview.buscar(news, outdir)
            if _gp:
                _cr = "Imagem: Google Street View" if _tipo == "streetview" else "Mapa: Google"
                return slide_cover_foto_faixa(news, _gp, outdir, manchete=manchete, credito=_cr)
        except Exception:
            pass

    _cat = (news["category"] or "").strip().lower()
    if not bg and _cat in _ILUSTRA_CATS:
        # 2.5) IMAGEM LIVRE (Pexels): FOTO REAL ilustrativa SÓ nas categorias onde a imagem
        #      genérica combina (esporte/clima). Fora disso, card de marca > foto sem nexo.
        try:
            import imagemlivre
            try:
                _nid = news["id"]
            except Exception:
                _nid = 0
            _il = imagemlivre.buscar(news["category"], news["title"], seed=_nid)
            if _il:
                bg = cover_image(_il, None)
                if bg:
                    ilustrativa = True
        except Exception:
            pass
    if not bg:
        # 3) Fallback IA (Nano Banana: seletivo, capado). Off por padrão (NANOBANANA_ON).
        try:
            import nanobanana
            _nb = nanobanana.gerar_capa(news["title"], news["category"], news["city"], outdir)
            if _nb:
                bg = Image.open(_nb).convert("RGB")
        except Exception:
            pass
    if bg:
        canvas = gradient_overlay(bg)
    else:
        canvas = brand_card_bg()   # card de marca (gradiente sóbrio) — melhor que foto errada
    d = ImageDraw.Draw(canvas)

    brand_header(d)

    # tags cidade + categoria (parte de baixo, acima da manchete)
    city = news["city"] or "Santa Catarina"
    cat = CAT_LABEL.get((news["category"] or "geral"), (news["category"] or "GERAL").upper())

    # manchete — TIKTOK MODE: a notícia em 2 linhas que se basta (nosso texto), não o título cru
    title = re.sub(r"\s+", " ", (manchete or news["title"])).strip().rstrip(".")
    fh = font(70, impact=True)
    lines = wrap(d, title.upper(), fh, W - 112)
    # adaptativo: a notícia-flash pode ser longa — diminui a fonte pra caber bonito (máx ~4 linhas)
    for _sz in (62, 56, 50):
        if len(lines) <= 4:
            break
        fh = font(_sz, impact=True)
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

    # crédito da foto emprestada de outro portal (atribuição)
    if foto_credito:
        ftxt = f"Foto: {foto_credito}"
        fc = font(26, bold=False)
        cw = d.textlength(ftxt, font=fc)
        d.text((W - 56 - cw, H - 104), ftxt, font=fc, fill=MUTED)
    # honestidade: foto ilustrativa (banco livre, não é a cena real)
    elif ilustrativa:
        ftxt = "Foto ilustrativa"
        fc = font(26, bold=False)
        cw = d.textlength(ftxt, font=fc)
        d.text((W - 56 - cw, H - 104), ftxt, font=fc, fill=MUTED)

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
    """Slide final de ENGAJAMENTO (2026: saves/shares/comments > likes).
    Pede a interação que o algoritmo premia, em vez de 'vá ao site'."""
    canvas = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(canvas)
    brand_header(d)

    city = news["city"] if (news["city"] and news["city"] in NORTE_SC) else None
    cy = H // 2 - 200

    # selo topo
    seal = "GOSTOU? AJUDA A ESPALHAR:"
    fs = font(36)
    sw = d.textlength(seal, font=fs)
    d.rounded_rectangle([(W - sw) // 2 - 32, cy - 84, (W + sw) // 2 + 32, cy - 16],
                        radius=34, fill=GOLD)
    d.text(((W - sw) // 2, cy - 74), seal, font=fs, fill=BLACK)

    # as 3 ações que o algoritmo recompensa
    big = ["SALVA", "COMENTA", "COMPARTILHA"]
    fbig = font(92, impact=True)
    y = cy + 30
    for ln in big:
        w = d.textlength(ln, font=fbig)
        d.text(((W - w) // 2, y), ln, font=fbig, fill=WHITE, stroke_width=2, stroke_fill=BLACK)
        y += int(fbig.size * 1.06)

    # marca um amigo (puxa comentário + alcance)
    y += 64
    mark = f"MARCA UM AMIGO DE {city.upper()}" if city else "MARCA UM AMIGO DO VALE"
    fm = font(40)
    w = d.textlength(mark, font=fm)
    d.rounded_rectangle([(W - w) // 2 - 36, y - 14, (W + w) // 2 + 36, y + 64],
                        radius=20, fill=RED)
    d.text(((W - w) // 2, y), mark, font=fm, fill=WHITE)

    # handle + CTA do Canal do WhatsApp (audiência própria — destino nº1)
    y += 120
    handle = "@radioscnews"
    fh = font(50)
    w = d.textlength(handle, font=fh)
    d.text(((W - w) // 2, y), handle, font=fh, fill=GOLD)

    # pill verde do Canal do WhatsApp
    y += 92
    zap = "NO CANAL DO WHATSAPP VOCÊ RECEBE 1º"
    fz = font(33)
    zw = d.textlength(zap, font=fz)
    d.rounded_rectangle([(W - zw) // 2 - 30, y - 12, (W + zw) // 2 + 30, y + 58],
                        radius=20, fill=WHATS)
    d.text(((W - zw) // 2, y), zap, font=fz, fill=BLACK)
    link = "link na bio"
    fl = font(28, bold=False)
    w = d.textlength(link, font=fl)
    d.text(((W - w) // 2, y + 74), link, font=fl, fill=MUTED)

    footer_site(d)
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
