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


# Emoji/símbolos que o PIL (DejaVu) NÃO renderiza viram quadradinho (tofu) na imagem.
# A IA às vezes mete emoji na manchete -> tofu em TODA capa. Tiramos do texto DESENHADO
# (a legenda do Instagram, que é texto de verdade, mantém os emojis).
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF"   # emoticons, pictogramas, transporte, suplementar
    "\U00002600-\U000027BF"    # símbolos diversos + dingbats
    "\U00002B00-\U00002BFF"    # estrelas/setas diversas
    "\U0001F1E6-\U0001F1FF"    # bandeiras
    "\U00002190-\U000021FF"    # setas unicode (usamos -> em ascii)
    "\U00002300-\U000023FF"    # técnicos (⏰⌛ etc.)
    "\U0000FE00-\U0000FE0F"    # seletores de variação
    "\U0000200D\U000020E3\U00002122\U00002139]+", flags=re.UNICODE)


def _semoji(s):
    """Tira emoji/símbolos não-renderáveis do TEXTO DA IMAGEM (vira quadradinho no PIL)."""
    if not s:
        return s
    return re.sub(r"\s{2,}", " ", _EMOJI.sub("", s)).strip()


def wrap(draw, text, fnt, max_w):
    """Quebra texto em linhas que cabem em max_w pixels. Tira emoji (PIL não renderiza -> tofu)."""
    words = _semoji(text).split()
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
    text = _semoji(text)
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
def _cidade_real(news):
    """A cidade que MANDA no selo/CTA: a citada no TÍTULO (mais confiável que o campo city, que
    às vezes vem errado — notícia de Jaraguá marcada como Schroeder) > o campo city > genérico."""
    try:
        import genericbg
        c = genericbg.cidade_no_titulo(news["title"] or "")
        if c:
            return c
    except Exception:
        pass
    return news["city"] or "Santa Catarina"


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

    city = _cidade_real(news)
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


# 🚨 FOTO SENSÍVEL: matéria policial/violenta NUNCA pode usar foto de TERCEIRO — rosto de VÍTIMA
# ou de PRESO = direito de imagem + presunção de inocência (preso ≠ condenado; se for absolvido,
# processo na certa). Mesmo com ANTI_STRIKE=0, essas caem no arsenal NEUTRO (policial/incendio/
# acidente). Regex generosa DE PROPÓSITO: falso-positivo só troca a foto por um fundo nosso (ganho
# zero de risco), enquanto deixar um rosto vazar é grave.
_FOTO_SENSIVEL = re.compile(
    r"pol[ií]ci|\bprend|preso|pres[ao]s?\b|pris[ãa]o|detid|apreend|flagrante|delegacia|"
    r"homic[ií]d|assassin|\bmatou|\bmort|[óo]bito|v[ií]tima|cad[áa]ver|\bcorpo\b|"
    r"esfaquead|esfaque|balead|\btiro|tiroteio|estupr|abus|feminic[ií]d|latroc[ií]n|assalt|"
    r"\broub|\bfurt|\barma\b|muni[çc]|acidente|colis[ãa]o|atropel|afogad|suic[ií]d|inc[êe]ndio|"
    r"facada|espanc|agress|\bbriga|tr[áa]fico|traficant|\bdrog|overdose|sequestr|c[áa]rcere|"
    r"\bresgat|bombeir|socorr|\bferid|\bqueda|desmoron|soterr|carboniz|naufrag|"
    r"condenad|julgament|\bacusad|denunciad|indiciad|linchad|degolad|decapit|chacina|"
    r"execu[çc]|emboscad|ref[ée]m|penitenci|pres[íi]dio|carcereir|estelionat|golpe do pix|"
    r"menor infrator|ato infracional|fac[çc][ãa]o|\bPCC\b|ossada|restos mortais|cova rasa|"
    r"encontrad[oa]s?\s+(?:mort|sem vida)|\bsem vida\b|espancament|"
    r"avi[ãa]o.{0,25}(?:cai|despenc|tombou|acident)|aeronave|helic[óo]ptero|acidente a[ée]reo|"
    r"\bcapotou\b|queda de avi",
    re.IGNORECASE)


def _foto_sensivel(news):
    """True se a matéria é sensível (crime/violência/vítima/tragédia). Nesses casos NUNCA usamos
    foto de terceiro (mesmo com ANTI_STRIKE=0): cai no arsenal neutro. Lê TÍTULO **E CORPO** — o
    crime pode estar só no texto (título limpo furava a trava). Protege imagem + presunção de inoc."""
    try:
        cat = (news["category"] or "").lower()
    except (KeyError, IndexError, TypeError):
        cat = ""
    if cat in ("policial", "policia", "polícia", "poli", "seguranca", "segurança"):
        return True
    blob = ""
    for k in ("title_own", "title", "resumo_own", "summary", "materia_own"):
        try:
            v = news[k]
            if v:
                blob += " " + v
        except (KeyError, IndexError, TypeError):
            pass
    return bool(_FOTO_SENSIVEL.search(blob))


# ✅ ALLOWLIST DE FOTO: com ANTI_STRIKE=1 (bloqueia foto de terceiro em TUDO por padrão), estas
# categorias SEGURAS podem usar a foto real da fonte (esporte/cidade/clima/economia) — visual bem
# melhor, risco baixo. Sensível (policial/crime/acidente) NUNCA entra: é barrado ANTES por
# _foto_sensivel. Editável via env FOTO_LIBERADA_CATS.
_FOTO_LIBERADA_CATS = [c.strip().lower() for c in
                       os.environ.get("FOTO_LIBERADA_CATS",
                                      "esporte,clima,economia,geral,turismo").split(",") if c.strip()]


def _foto_liberada(news):
    """Categoria SEGURA onde a foto real da fonte pode passar mesmo com ANTI_STRIKE=1.
    Sensível NUNCA chega aqui (checado antes). Fora da lista → segue bloqueado (arsenal)."""
    try:
        cat = (news["category"] or "").lower()
    except (KeyError, IndexError, TypeError):
        cat = ""
    return cat in _FOTO_LIBERADA_CATS


def slide_cover(news, outdir, manchete=None):
    # 🛡️ ANTI-PROCESSO: por padrão NÃO usa foto de TERCEIRO (nem a og:image da fonte, nem foto de
    # outro portal). O FATO é livre; a FOTO deles não é. Só foto PRÓPRIA (admin), stock regional
    # (própria), arte de IA ou card de marca. Desliga com ANTI_STRIKE=0 (por sua conta e risco).
    anti = os.environ.get("ANTI_STRIKE", "1").strip() != "0"
    # 🚨 TRAVA DURA: policial/violência força o modo neutro, mesmo com ANTI_STRIKE=0 (rosto de
    # vítima/preso NUNCA sai). Foto do dono (admin) continua valendo — é escolha editorial dele.
    if _foto_sensivel(news):
        anti = True
    # ✅ ALLOWLIST: categoria segura (esporte/cidade/clima/economia) libera a foto real da fonte
    # mesmo com ANTI_STRIKE=1. Só chega aqui se NÃO for sensível (o if acima barra o perigoso).
    elif anti and _foto_liberada(news):
        anti = False
    bg = cover_image(None if anti else news["image_url"], news["admin_image"])
    # 👁️ VISÃO IA (camada anti-Chapecó): o motor é CEGO — casa nome de arquivo com palavra do
    # título e nunca vê o pixel. Aqui uma IA barata (Gemini Flash) OLHA a foto REAL da fonte:
    # se tiver rosto/corpo/sangue/criança (o que o regex de TEXTO não pega), NÃO usa — cai pro
    # Street View/arsenal (imagem NOSSA, segura). Fixes da revisão independente:
    #   • foto do ADMIN (escolha humana deliberada) NÃO passa pela visão — humano manda;
    #   • fail-CLOSED nas categorias LARGAS (VISAO_FAILCLOSED_CATS, default 'geral'): se a visão
    #     FALHOU (erro/quota), a foto da fonte é descartada por cautela — 'geral' era exatamente
    #     o balde do incidente de Chapecó e a visão é a única rede de pixel nele;
    #   • visão desligada DE PROPÓSITO ('off') respeita o dono: comporta como antes (fail-open).
    if bg is not None and not news["admin_image"]:
        try:
            import visao_imagem
            _v = visao_imagem.avaliar(bg)
            if _v == "perigosa":
                print("   👁️ VISÃO IA barrou a foto da fonte — usando imagem NOSSA")
                bg = None
            elif _v == "erro":
                _fc = {c.strip().lower() for c in
                       os.environ.get("VISAO_FAILCLOSED_CATS", "geral").split(",") if c.strip()}
                if (news["category"] or "").strip().lower() in _fc:
                    print("   👁️ VISÃO IA falhou — foto da fonte descartada por CAUTELA (categoria larga)")
                    bg = None
        except Exception:
            pass
    foto_credito = None
    ilustrativa = False
    arte_ia = False
    # foto REAL da matéria (quando ANTI_STRIKE=0): credita a fonte na capa (atribuição). Fontes
    # litigiosas (OCP/Schroeder) já vêm SEM image_url do coletor, então nunca caem aqui.
    if bg and not anti and not news["admin_image"] and news["image_url"]:
        try:
            foto_credito = news["source"] or None
        except Exception:
            foto_credito = None
    # A) STREET VIEW de LUGAR ESPECÍFICO (prefeitura/câmara/hospital/BR-280) — foto REAL do prédio,
    #    layout foto+faixa. Só roda quando o título cita o lugar; senão cai no arsenal. SEM mapa.
    if not bg:
        try:
            import streetview
            _gp, _tipo = streetview.buscar(news, outdir)
            if _gp:
                return slide_cover_foto_faixa(news, _gp, outdir, manchete=manchete,
                                              credito="Imagem: Google Street View")
        except Exception:
            pass
    # 🎨 CURADOR — o Editor de Fotografia IA (ideia do dono, 13/jul): LÊ a notícia + o catálogo
    # do acervo e DECIDE (usar slug / gerar sob medida / card), com a visão CONFERINDO a escolha.
    # FAIL-SAFE: qualquer falha -> o fluxo regex de sempre decide (zero regressão). Sensível nunca gera.
    _pula_arsenal = False
    if not bg:
        _dec = None
        try:
            import curador
            if curador.ativo():
                _dec = curador.escolher(news, sensivel=_foto_sensivel(news))
        except Exception:
            _dec = None
        if _dec:
            try:
                import genericbg
                import nanobanana
                try:
                    _seed = int(news["id"])
                except Exception:
                    _seed = 0
                _nb = None
                if _dec["acao"] == "usar" and _dec["slug"]:
                    _p = genericbg._file(_dec["slug"], _seed)
                    if _p and curador.combina(_p, news):
                        _bi = Image.open(_p).convert("RGB")
                        _sc = max(W / _bi.width, H / _bi.height)
                        _bi = _bi.resize((int(_bi.width * _sc), int(_bi.height * _sc)))
                        bg = _bi.crop(((_bi.width - W) // 2, (_bi.height - H) // 2,
                                       (_bi.width - W) // 2 + W, (_bi.height - H) // 2 + H))
                        ilustrativa = True
                    elif not _foto_sensivel(news):
                        # a escolhida não convenceu a visão -> gera sob medida no lugar
                        _nb = nanobanana.gerar_capa(news["title"], news["category"], news["city"],
                                                    outdir, sensivel=False,
                                                    cena=_dec.get("cena"), slug_forcado=_dec.get("slug"))
                elif _dec["acao"] == "gerar":
                    _nb = nanobanana.gerar_capa(news["title"], news["category"], news["city"],
                                                outdir, sensivel=_foto_sensivel(news),
                                                cena=_dec.get("cena"), slug_forcado=_dec.get("slug"))
                elif _dec["acao"] == "card":
                    # o curador olhou o catálogo e nada serve: card de marca > imagem sem nexo
                    _pula_arsenal = True
                if _nb:
                    bg = Image.open(_nb).convert("RGB")
                    arte_ia = True
            except Exception:
                pass
    # B) ARSENAL ESPECÍFICO: a NOSSA imagem (situação/cidade/categoria) — arsenal fixo + acervo IA.
    #    permitir_generico=False: para no específico; o genérico vira fallback FINAL (depois da IA),
    #    pra a IA poder preencher o buraco com imagem sob medida (e salvá-la no acervo p/ reuso).
    #    (FALLBACK do curador: só roda se o curador falhou/off — e nunca quando ele mandou "card".)
    if not bg and not _pula_arsenal:
        try:
            import genericbg
            _bp = genericbg.buscar(news, permitir_generico=False)
            if _bp:
                _bi = Image.open(_bp).convert("RGB")
                _sc = max(W / _bi.width, H / _bi.height)
                _bi = _bi.resize((int(_bi.width * _sc), int(_bi.height * _sc)))
                bg = _bi.crop(((_bi.width - W) // 2, (_bi.height - H) // 2,
                               (_bi.width - W) // 2 + W, (_bi.height - H) // 2 + H))
                ilustrativa = True
        except Exception:
            pass
    if not bg and not anti and os.environ.get("FOTOBUSCA_ON", "0") == "1":
        # 🔒 fotobusca DESLIGADO por padrão (FOTOBUSCA_ON=1 p/ religar): puxa a foto que OUTRO
        # portal publicou p/ o mesmo fato — pode ter rosto de pessoa privada (mesmo risco do
        # incidente de 06/jul). Fica off até haver acordo de imagem com a fonte.
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
    if not bg and not _pula_arsenal:
        # 3) IA SOB MEDIDA (Nano Banana) — AGORA ANTES do banco genérico (fix 13/jul: o Pexels
        #    servia foto de GAMER pra futebol; imagem gerada do TEMA certo > stock sem nexo).
        #    Gera 1x, salva no acervo por situação e reusa de graça. Off por padrão (NANOBANANA_ON).
        #    Guarda-corpo: sensível NUNCA gera (não simula cena).
        try:
            import nanobanana
            _nb = nanobanana.gerar_capa(news["title"], news["category"], news["city"], outdir,
                                        sensivel=_foto_sensivel(news))
            if _nb:
                bg = Image.open(_nb).convert("RGB")
                arte_ia = True
        except Exception:
            pass
    _cat = (news["category"] or "").strip().lower()
    if not bg and not _pula_arsenal and _cat in _ILUSTRA_CATS:
        # 3.5) IMAGEM LIVRE (Pexels) — fallback DEPOIS da IA (só quando IA off/cap estourado):
        #      foto real ilustrativa só nas categorias onde a genérica combina (esporte/clima).
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
    if not bg and not _pula_arsenal:
        # B2) GENÉRICO do arsenal (fallback FINAL antes do card): imagem ilustrativa do Vale.
        #     Só chega aqui se a IA estava OFF/falhou — senão a IA teria preenchido sob medida.
        try:
            import genericbg
            _bp = genericbg.buscar(news, permitir_generico=True)
            if _bp:
                _bi = Image.open(_bp).convert("RGB")
                _sc = max(W / _bi.width, H / _bi.height)
                _bi = _bi.resize((int(_bi.width * _sc), int(_bi.height * _sc)))
                bg = _bi.crop(((_bi.width - W) // 2, (_bi.height - H) // 2,
                               (_bi.width - W) // 2 + W, (_bi.height - H) // 2 + H))
                ilustrativa = True
        except Exception:
            pass
    if bg:
        canvas = gradient_overlay(bg)
    else:
        canvas = brand_card_bg()   # card de marca (gradiente sóbrio) — melhor que foto errada
    d = ImageDraw.Draw(canvas)

    brand_header(d)

    # tags cidade + categoria (parte de baixo, acima da manchete)
    city = _cidade_real(news)
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
    # honestidade: imagem GERADA por IA (não é foto real do fato)
    elif arte_ia:
        ftxt = "Arte IA"
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

    _rc = _cidade_real(news)
    city = _rc if _rc in NORTE_SC else None
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
    handle = "@radiosc.news"
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
    city = _cidade_real(news)
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
        f"👉 Mais notícias do Vale no nosso site:\n"
        f"🔗 {SITE} (link na bio)\n\n"
        f"Siga @radiosc.news e fique por dentro de tudo que acontece no Norte de SC.\n\n"
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
