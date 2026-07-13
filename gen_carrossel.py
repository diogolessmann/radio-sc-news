# -*- coding: utf-8 -*-
"""
gen_carrossel.py — Gerador de carrosseis TEMATICOS (editorial) para o Instagram
Radio SC News

Diferente do gen_instagram.py (que usa o banco de noticias), este monta
carrosseis curados por tema, com capa-gancho que para o dedo e foco em
SALVAR / COMPARTILHAR / COMENTAR.

Saida: instagram_posts/editorial/<slug>/slide_N.png + legenda.txt

Uso:
  venv\\Scripts\\python.exe gen_carrossel.py            # gera todos os decks
  venv\\Scripts\\python.exe gen_carrossel.py --deck vagas
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- estilo
W, H = 1080, 1350
BG = (17, 18, 24)
RED = (231, 76, 60)
GOLD = (245, 197, 24)
WHITE = (245, 245, 247)
MUTED = (168, 170, 180)
BLACK = (0, 0, 0)
SITE = "radioscnews.com.br"
BRAND = "RÁDIO SC NEWS"
TAGLINE = "CONECTANDO A REGIÃO"
FONTS = "C:/Windows/Fonts"


def font(size, bold=True, impact=False):
    if impact:
        return ImageFont.truetype(f"{FONTS}/impact.ttf", size)
    return ImageFont.truetype(f"{FONTS}/{'arialbd' if bold else 'arial'}.ttf", size)


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
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


def draw_block(draw, lines, fnt, x, y, fill, lh, stroke=0):
    for ln in lines:
        draw.text((x, y), ln, font=fnt, fill=fill,
                  stroke_width=stroke, stroke_fill=BLACK)
        y += lh
    return y


def pill(draw, x, y, text, fnt, bg, fg, pad_x=26, pad_y=14):
    w = draw.textlength(text, font=fnt)
    asc, desc = fnt.getmetrics()
    th = asc + desc
    draw.rounded_rectangle([x, y, x + w + pad_x * 2, y + th + pad_y * 2],
                           radius=(th + pad_y * 2) // 2, fill=bg)
    draw.text((x + pad_x, y + pad_y), text, font=fnt, fill=fg)
    return x + w + pad_x * 2


def header(draw):
    x = pill(draw, 56, 56, "  " + BRAND + "  ", font(32), RED, WHITE)
    draw.ellipse([56 + 15, 56 + 21, 56 + 15 + 17, 56 + 21 + 17], fill=WHITE)


def footer(draw, counter=None):
    f = font(26, bold=False)
    draw.text((56, H - 66), f"{BRAND}  •  {TAGLINE}", font=f, fill=MUTED)
    if counter:
        cf = font(28)
        w = draw.textlength(counter, font=cf)
        draw.text((W - 56 - w, H - 68), counter, font=cf, fill=MUTED)


def base_canvas():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 8], fill=RED)  # barra de marca no topo
    return img, d


# ---------------------------------------------------------------- slides
def slide_cover(deck, outdir):
    img, d = base_canvas()
    header(d)

    # subtitulo (kicker) em cima do gancho
    cities = "Schroeder  •  Guaramirim  •  Jaraguá do Sul  •  Joinville"
    cf = font(26, bold=False)
    cw = d.textlength(cities, font=cf)
    d.text(((W - cw) // 2, 150), cities, font=cf, fill=MUTED)

    # gancho grande
    fh = font(96, impact=True)
    lines = wrap(d, deck["hook"].upper(), fh, W - 120)
    lh = int(fh.size * 1.02)
    block = len(lines) * lh
    y0 = (H - block) // 2 - 40
    draw_block(d, lines, fh, 60, y0, WHITE, lh)

    # subtitulo dourado
    sub = deck.get("sub", "")
    if sub:
        sf = font(40)
        sl = wrap(d, sub, sf, W - 140)
        yy = y0 + block + 36
        for ln in sl:
            w = d.textlength(ln, font=sf)
            d.text(((W - w) // 2, yy), ln, font=sf, fill=GOLD)
            yy += int(sf.size * 1.25)

    # hint
    hint = "ARRASTE PARA O LADO  >"
    hf = font(34)
    w = d.textlength(hint, font=hf)
    d.text(((W - w) // 2, H - 130), hint, font=hf, fill=GOLD)

    footer(d, f"1/{deck['total']}")
    p = os.path.join(outdir, "slide_1.png")
    img.save(p, quality=92)
    return p


def slide_item(item, n, total, outdir, number=None):
    img, d = base_canvas()
    header(d)

    y = 260
    # numero grande (formato lista) opcional
    if number is not None:
        nf = font(150, impact=True)
        d.text((60, y - 40), str(number), font=nf, fill=GOLD)
        # cidade ao lado do numero
        nbw = d.textlength(str(number), font=nf)
        pill(d, 60 + nbw + 40, y + 20, item["city"].upper(), font(34), RED, WHITE)
        y += 190
    else:
        pill(d, 60, y, item["city"].upper(), font(34), RED, WHITE)
        y += 100

    # kicker dourado
    if item.get("kicker"):
        d.text((60, y), item["kicker"].upper(), font=font(30), fill=GOLD)
        y += 56

    # titulo
    tf = font(60, impact=True)
    tl = wrap(d, item["title"].upper(), tf, W - 120)
    y = draw_block(d, tl, tf, 60, y, WHITE, int(tf.size * 1.05))
    y += 30

    # corpo
    bf = font(42, bold=False)
    bl = wrap(d, item["body"], bf, W - 130)
    # barra lateral
    bh = len(bl) * int(bf.size * 1.42)
    d.rounded_rectangle([60, y, 70, y + bh], radius=5, fill=RED)
    draw_block(d, bl, bf, 96, y, WHITE, int(bf.size * 1.42))

    footer(d, f"{n}/{total}")
    p = os.path.join(outdir, f"slide_{n}.png")
    img.save(p, quality=92)
    return p


def slide_cta(deck, n, outdir):
    img, d = base_canvas()
    header(d)
    cy = H // 2 - 160

    big = wrap(d, deck["cta_title"].upper(), font(78, impact=True), W - 120)
    fbig = font(78, impact=True)
    y = cy
    for ln in big:
        w = d.textlength(ln, font=fbig)
        d.text(((W - w) // 2, y), ln, font=fbig, fill=WHITE)
        y += int(fbig.size * 1.05)

    y += 30
    lf = font(40, bold=False)
    for ln in wrap(d, deck["cta_line"], lf, W - 160):
        w = d.textlength(ln, font=lf)
        d.text(((W - w) // 2, y), ln, font=lf, fill=GOLD)
        y += int(lf.size * 1.3)

    y += 50
    sf = font(50)
    w = d.textlength(SITE, font=sf)
    d.rounded_rectangle([(W - w) // 2 - 40, y - 14, (W + w) // 2 + 40, y + 74],
                        radius=20, fill=RED)
    d.text(((W - w) // 2, y), SITE, font=sf, fill=WHITE)

    lk = "LINK NA BIO"
    kf = font(36)
    w = d.textlength(lk, font=kf)
    d.text(((W - w) // 2, y + 120), lk, font=kf, fill=GOLD)

    footer(d, f"{n}/{deck['total']}")
    p = os.path.join(outdir, f"slide_{n}.png")
    img.save(p, quality=92)
    return p


# ---------------------------------------------------------------- decks
DECKS = {
    "vagas": {
        "hook": "Estão contratando no Norte de SC",
        "sub": "Veja onde tem vaga essa semana — salva pra não perder",
        "numbered": False,
        "items": [
            {"city": "Joinville", "kicker": "Oportunidades",
             "title": "Indústria, TI e serviços",
             "body": "Vagas operacionais e técnicas em aberto na maior cidade do estado. Veja como se candidatar pelo Sine e pelos portais de emprego locais."},
            {"city": "Jaraguá do Sul", "kicker": "Contratando",
             "title": "Metalmecânico e têxtil aquecidos",
             "body": "Os setores mais fortes da cidade seguem com contratação ativa — há vagas com e sem experiência para quem quer começar."},
            {"city": "Guaramirim", "kicker": "Em alta",
             "title": "Logística no eixo da BR-280",
             "body": "Galpões e comércio puxam as contratações na cidade que mais cresce no eixo logístico do Norte catarinense."},
            {"city": "Schroeder", "kicker": "Vagas locais",
             "title": "Comércio e pequenas indústrias",
             "body": "Oportunidades abertas no comércio local e nas indústrias do município, sem precisar sair da cidade para trabalhar."},
        ],
        "cta_title": "A lista completa está no site",
        "cta_line": "Acesse a aba VAGAS no link da bio. Salva esse post e marca quem está procurando emprego!",
        "tags": ["#vagasdeemprego", "#empregojoinville", "#vagasjaraguadosul",
                 "#empregosc", "#guaramirim", "#schroeder", "#nortedesc",
                 "#santacatarina", "#radioscnews"],
    },
    "voce-sabia": {
        "hook": "4 coisas que todo morador daqui deveria saber",
        "sub": "A nº 3 quase ninguém sabe",
        "numbered": True,
        "items": [
            {"city": "Joinville", "kicker": "Você sabia?",
             "title": "A maior cidade de SC",
             "body": "Conhecida como a Capital da Dança e das Bicicletas, é o maior município de Santa Catarina em população."},
            {"city": "Jaraguá do Sul", "kicker": "Você sabia?",
             "title": "Potência industrial mundial",
             "body": "A cidade abriga uma das maiores indústrias eletromecânicas do planeta, exportando para dezenas de países."},
            {"city": "Guaramirim", "kicker": "Você sabia?",
             "title": "Hub logístico do estado",
             "body": "A posição estratégica na BR-280 transformou a cidade em um dos principais polos de logística de Santa Catarina."},
            {"city": "Schroeder", "kicker": "Você sabia?",
             "title": "Refúgio de natureza",
             "body": "Forte colonização germânica e turismo rural fazem da cidade um verdadeiro refúgio verde da região."},
        ],
        "cta_title": "Quantas você já sabia?",
        "cta_line": "Comenta aqui embaixo e marca um amigo da região! Mais curiosidades no site.",
        "tags": ["#vocesabia", "#curiosidades", "#joinville", "#jaraguadosul",
                 "#guaramirim", "#schroeder", "#nortedesc", "#santacatarina",
                 "#orgulhodaregiao", "#radioscnews"],
    },
    "historia-nomes": {
        "hook": "De onde vem o nome da sua cidade?",
        "sub": "A história por trás do Norte de SC",
        "numbered": False,
        "items": [
            {"city": "Joinville", "kicker": "Cidade dos Príncipes",
             "title": "Nasceu de um dote de casamento",
             "body": "O nome homenageia o Príncipe de Joinville, da França, casado com a Princesa Francisca, irmã de Dom Pedro II. A colônia surgiu ligada ao dote desse casamento, em 1851."},
            {"city": "Jaraguá do Sul", "kicker": "Origem tupi-guarani",
             "title": "O 'senhor do vale'",
             "body": "O nome Jaraguá tem raiz indígena, comumente associada à ideia de 'senhor do vale'. A cidade foi fundada em 1876 por Emílio Carlos Jourdan."},
            {"city": "Guaramirim", "kicker": "Origem tupi",
             "title": "A 'pequena ave guará'",
             "body": "Vem do tupi: 'guará' (uma ave) + 'mirim' (pequeno). Antes de receber esse nome, a região já foi conhecida como Bananal."},
            {"city": "Schroeder", "kicker": "Herança alemã",
             "title": "Uma homenagem germânica",
             "body": "O nome lembra Christian Mathias Schroeder, ligado à sociedade colonizadora de Hamburgo. A colonização alemã e polonesa marca a identidade da cidade até hoje."},
            {"city": "Corupá", "kicker": "Terra das cachoeiras",
             "title": "Já se chamou Hansa Humboldt",
             "body": "Fundada por imigrantes alemães, a cidade já teve o nome de Hansa Humboldt. Hoje é conhecida pela Rota das Cachoeiras, um dos maiores circuitos de quedas d'água do país."},
        ],
        "cta_title": "Você conhecia essas histórias?",
        "cta_line": "Comenta de qual cidade você é e marca alguém da região! Mais história e cultura no nosso site.",
        "tags": ["#historia", "#curiosidades", "#nortedesc", "#joinville",
                 "#jaraguadosul", "#guaramirim", "#schroeder", "#corupa",
                 "#santacatarina", "#orgulhodaregiao", "#radioscnews"],
    },
    "curiosidades-surpreendentes": {
        "hook": "5 curiosidades que vão te surpreender",
        "sub": "Você mora perto disso e talvez nem saiba",
        "numbered": True,
        "items": [
            {"city": "Joinville", "kicker": "Capital da Dança",
             "title": "Sede do maior festival de dança do mundo",
             "body": "O Festival de Dança de Joinville é reconhecido pelo Guinness como o maior do planeta. A cidade também abriga a única escola do Teatro Bolshoi fora da Rússia."},
            {"city": "Jaraguá do Sul", "kicker": "Potência mundial",
             "title": "Berço de uma gigante dos motores",
             "body": "Aqui nasceu, em 1961, a WEG — hoje uma das maiores fabricantes de motores elétricos do mundo, exportando para dezenas de países."},
            {"city": "Corupá", "kicker": "Paraíso natural",
             "title": "Uma rota com dezenas de cachoeiras",
             "body": "A Rota das Cachoeiras de Corupá reúne um dos maiores conjuntos de quedas d'água do país, atraindo turistas e aventureiros o ano todo."},
            {"city": "Guaramirim", "kicker": "Coração logístico",
             "title": "Um dos maiores polos logísticos de SC",
             "body": "A posição estratégica na BR-280 transformou a cidade em ponto-chave para galpões, indústrias e escoamento de cargas no estado."},
            {"city": "Schroeder", "kicker": "Refúgio verde",
             "title": "Natureza e tradição germânica",
             "body": "Com forte herança alemã e polonesa, a cidade virou um refúgio de turismo rural, trilhas e paisagens de serra no Norte catarinense."},
        ],
        "cta_title": "Quantas você já sabia?",
        "cta_line": "Comenta aqui embaixo e marca um amigo da região! Mais curiosidades no nosso site.",
        "tags": ["#curiosidades", "#vocesabia", "#nortedesc", "#joinville",
                 "#jaraguadosul", "#corupa", "#guaramirim", "#schroeder",
                 "#santacatarina", "#orgulhodaregiao", "#radioscnews"],
    },
    "sabores-da-regiao": {
        "hook": "5 comidas que só quem é daqui conhece",
        "sub": "Deu água na boca? Marca quem ama essas delícias",
        "numbered": True,
        "items": [
            {"city": "Cuca", "kicker": "Tradição alemã",
             "title": "O bolo que virou paixão regional",
             "body": "Massa fofa coberta com farofa doce, recheada de banana, goiabada ou nata. Herança germânica que está na mesa de todo mundo no café da tarde."},
            {"city": "Marreco recheado", "kicker": "Prato típico",
             "title": "A estrela das festas",
             "body": "Marreco assado recheado, acompanhado de repolho roxo e purê. Um dos pratos mais tradicionais da culinária alemã do Norte de SC."},
            {"city": "Eisbein", "kicker": "Sabor germânico",
             "title": "O joelho de porco alemão",
             "body": "Pernil suíno cozido e assado, servido com chucrute e batata. Presença garantida nas cervejarias e restaurantes típicos da região."},
            {"city": "Café colonial", "kicker": "Experiência local",
             "title": "Uma mesa farta de delícias",
             "body": "Cucas, pães caseiros, embutidos, geleias, queijos e bolos numa só refeição. Tradição que atrai turistas para o interior de Guaramirim e Schroeder."},
            {"city": "Marzipã", "kicker": "Doce de festa",
             "title": "A delicadeza das amêndoas",
             "body": "Doce fino à base de amêndoas, típico da cultura alemã, presente em datas especiais e nas confeitarias tradicionais da região."},
        ],
        "cta_title": "Qual é a sua favorita?",
        "cta_line": "Comenta o número aqui embaixo e marca quem ama essas delícias! Mais sobre a cultura da região no nosso site.",
        "tags": ["#comidatipica", "#gastronomia", "#cuca", "#culturalema",
                 "#nortedesc", "#joinville", "#jaraguadosul", "#guaramirim",
                 "#schroeder", "#santacatarina", "#radioscnews"],
    },
}


def make_caption(deck):
    return (
        f"{deck['hook'].upper()} 👇\n\n"
        f"📍 Schroeder • Guaramirim • Jaraguá do Sul • Joinville\n\n"
        f"{deck['cta_line']}\n\n"
        f"🔗 Tudo no site: {SITE} (link na bio)\n"
        f"Siga @radiosc.news e fique por dentro de tudo no Norte de SC.\n\n"
        + " ".join(deck["tags"])
    )


def build(slug, deck):
    deck["total"] = 1 + len(deck["items"]) + 1
    outdir = os.path.join("instagram_posts", "editorial", slug)
    os.makedirs(outdir, exist_ok=True)
    print(f"-> deck '{slug}' ({deck['total']} slides)")

    slide_cover(deck, outdir)
    n = 2
    for i, item in enumerate(deck["items"], 1):
        num = i if deck.get("numbered") else None
        slide_item(item, n, deck["total"], outdir, number=num)
        n += 1
    slide_cta(deck, n, outdir)

    with open(os.path.join(outdir, "legenda.txt"), "w", encoding="utf-8") as f:
        f.write(make_caption(deck))
    print(f"   OK -> {outdir}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deck", default=None, help="slug do deck (ex: vagas). Vazio = todos")
    args = ap.parse_args()
    decks = {args.deck: DECKS[args.deck]} if args.deck else DECKS
    for slug, deck in decks.items():
        build(slug, deck)
    print(f"\nPronto! -> {os.path.abspath(os.path.join('instagram_posts','editorial'))}")


if __name__ == "__main__":
    main()
