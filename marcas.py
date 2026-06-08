# -*- coding: utf-8 -*-
"""
marcas.py — Motor de conteúdo multi-marca (Instagram + Facebook)
Grupo DL / 4kitem

Diferente da Rádio (que coleta notícia por RSS), aqui o conteúdo é PRÓPRIO da
marca: serviços, produtos e dicas — conteúdo "evergreen" que rotaciona por dia.

Cada marca tem:
  - tema (cores, nome, contato, site)
  - banco de conteúdo (lista de tópicos: serviço ou dica)
  - tokens Meta próprios (env por marca)
  - voz própria na legenda

Postar de verdade precisa, no ambiente, dos tokens da marca, ex. Despachante:
  DESP_PAGE_TOKEN, DESP_IG_USER_ID, DESP_PAGE_ID

USO local (dry-run, só gera as imagens):
  python marcas.py despachante
USO real (posta):
  python marcas.py despachante --post
"""
import argparse
import glob
import os
import re
import textwrap
from datetime import datetime

import gen_instagram as gi
import distribuidor as dist

W, H = 1080, 1350
OUT_BASE = "instagram_posts"
PUBLIC_IMG_DIR = os.path.join("static", "social")


# ----------------------------------------------------------------- bancos de conteúdo
# Conteúdo 100% legítimo: a DL AJUDA o cliente — nunca se passa por Detran/governo.
DESPACHANTE_CONTEUDO = [
    {"cat": "DICA DE LEI",
     "titulo": "Comprou ou vendeu um veículo? Você tem 30 dias",
     "bullets": ["A lei dá 30 dias pra fazer a transferência após a compra.",
                 "Quem vende deve comunicar a venda pra não levar multa do comprador.",
                 "A gente cuida de tudo isso pra você, sem dor de cabeça."]},
    {"cat": "SERVIÇO",
     "titulo": "Tomou multa? Dá pra recorrer",
     "bullets": ["Muita multa tem erro e pode ser cancelada com recurso.",
                 "A DL Defesas analisa seu caso e monta a defesa.",
                 "Você não perde pontos à toa."]},
    {"cat": "DICA DE LEI",
     "titulo": "Comunicação de venda (ATPV-e): por que é tão importante",
     "bullets": ["Sem comunicar a venda, as multas do novo dono caem no SEU nome.",
                 "O ATPV-e é o documento digital que oficializa a venda.",
                 "A gente emite e comunica pra te proteger."]},
    {"cat": "SERVIÇO",
     "titulo": "CNH suspensa ou ameaçada? Não rode sem orientação",
     "bullets": ["Dirigir com a CNH suspensa é infração gravíssima.",
                 "A DL Defesas atua na suspensão e na cassação.",
                 "Chama a gente antes de tomar qualquer decisão."]},
    {"cat": "DICA DE LEI",
     "titulo": "Quantos pontos você pode ter na CNH?",
     "bullets": ["O limite varia conforme as infrações gravíssimas no período.",
                 "Passou do limite, a CNH pode ser suspensa.",
                 "A gente acompanha sua pontuação e te orienta."]},
    {"cat": "SERVIÇO",
     "titulo": "Proteção Veicular a partir de R$ 90/mês",
     "bullets": ["Cobertura para roubo, furto e colisão.",
                 "Assistência 24 horas quando você mais precisa.",
                 "DL Proteção Veicular — tranquilidade pra rodar."]},
    {"cat": "SERVIÇO",
     "titulo": "Renovação de CNH e cursos sem fila",
     "bullets": ["Renovação de todas as categorias (A a E).",
                 "Cursos obrigatórios e especializações (MOPP, mototáxi, escolar).",
                 "A DL CNH resolve do começo ao fim."]},
    {"cat": "DICA DE LEI",
     "titulo": "Você é PCD? Pode ter isenção de impostos no carro",
     "bullets": ["Pessoas com deficiência têm direito a isenções na compra do veículo.",
                 "A papelada é chata, mas a gente cuida de tudo.",
                 "DL Assessoria — você economiza de verdade."]},
    {"cat": "SERVIÇO",
     "titulo": "Quer abrir seu MEI ou regularizar o nome?",
     "bullets": ["Abertura de MEI e regularização de empresa.",
                 "Recuperação de crédito e questões de score.",
                 "DL Assessoria resolve a burocracia por você."]},
    {"cat": "SERVIÇO",
     "titulo": "Licenciamento atrasado? Resolve com a gente",
     "bullets": ["Licenciamento, débitos, histórico e consulta de leilão.",
                 "Tudo certinho pra você não ser parado na blitz.",
                 "Despachante Lessmann — rápido e sem complicação."]},
]


# 4kitem — sistemas/apps que facilitam o dia a dia de pequenos negocios.
# SlotZap (rifa/sorteio) fica de FORA: a Meta bane rifa e pode derrubar a conta.
KITEM_CONTEUDO = [
    {"cat": "AGENDAMENTO", "titulo": "AgendaJá — sua agenda no automático",
     "bullets": ["Página de agendamento com link próprio",
                 "Cliente marca pelo celular, sem baixar app",
                 "Sem horário duplo — você só atende"]},
    {"cat": "DELIVERY", "titulo": "MandaJá — delivery SEM comissão",
     "bullets": ["Sua loja online pronta em minutos",
                 "PIX direto, sem intermediário levando %",
                 "Pedido chega no seu WhatsApp na hora"]},
    {"cat": "WHATSAPP", "titulo": "MandaZap — marketing no WhatsApp com anti-ban",
     "bullets": ["Importe sua lista (CSV ou PDF)",
                 "Mensagem personalizada com o nome do cliente",
                 "Disparo em massa com anti-ban inteligente"]},
    {"cat": "TRÂNSITO", "titulo": "AlertaJá — CNH e veículo de olho pra você",
     "bullets": ["Pontos, vencimento e categoria da CNH",
                 "IPVA, licenciamento e multas do veículo",
                 "Relatório todo mês no seu WhatsApp"]},
    {"cat": "BAR & PUB", "titulo": "PubShow — a jukebox digital do seu bar",
     "bullets": ["Cliente pede música pelo celular",
                 "Paga via PIX e toca na hora",
                 "Sua TV exibe videoclipes e seus avisos"]},
    {"cat": "SALA DE ESPERA", "titulo": "SalaTV — a TV certa pro seu ambiente",
     "bullets": ["Conteúdo curado e seguro (clínica, salão, kids)",
                 "Sem anúncios do YouTube atrapalhando",
                 "Exiba seus próprios avisos na tela"]},
    {"cat": "PET", "titulo": "VetZap — triagem do seu pet 24 horas",
     "bullets": ["Saiba se é urgência em 3 minutos",
                 "Classifica: Estável, Atenção ou Urgente",
                 "Cartão digital de vacinas do pet"]},
    {"cat": "PRODUTIVIDADE", "titulo": "Baú — cofre das suas senhas na nuvem",
     "bullets": ["Guarde sites, logins e dicas de senha",
                 "Nunca mais perca senha ao formatar o PC",
                 "Acesse de qualquer dispositivo"]},
    {"cat": "DESPACHANTE", "titulo": "Amigo Despachante — sua loja organizada",
     "bullets": ["Ordens de serviço em quadro Kanban",
                 "Controle de licenciamento por final de placa",
                 "IA que ajuda no dia a dia"]},
    {"cat": "DEFESA DE MULTAS", "titulo": "DefesaPro — defesa de multas sem retrabalho",
     "bullets": ["Motor de petições baseado no CTB",
                 "OCR: preenche o processo por foto ou PDF",
                 "Controle de prazos e honorários"]},
]


BRANDS = {
    "despachante": {
        "nome": "Despachante Lessmann",
        "brand_tag": "DESPACHANTE LESSMANN",
        "tagline": "Trânsito descomplicado em Schroeder e região",
        "site": "dldespachante.com.br",
        "whats": "(47) 99716-2967",
        "instagram": "@despachantelessmann",
        # tema (azul confiança + dourado)
        "bg": (11, 31, 51), "card": (18, 42, 66), "accent": (242, 183, 5),
        "accent2": (46, 134, 222), "white": (245, 247, 250), "muted": (160, 175, 190),
        # tokens (env)
        "env": {"token": "DESP_PAGE_TOKEN", "ig": "DESP_IG_USER_ID", "page": "DESP_PAGE_ID"},
        "conteudo": DESPACHANTE_CONTEUDO,
        "hashtags": ["#despachante", "#schroeder", "#jaraguadosul", "#guaramirim",
                     "#transito", "#detran", "#cnh", "#multas", "#veiculos", "#dllessmann"],
        "voz": ("Você é o social media do Despachante Lessmann (Schroeder/SC). Fale como "
                "um especialista amigo que DESCOMPLICA o trânsito: claro, confiável e "
                "acolhedor. NUNCA se passe por Detran/governo — a DL AJUDA o cliente. "
                "Sem juridiquês, sem sensacionalismo."),
    },

    "dl_mobilidade": {
        "nome": "DL Mobilidade",
        "brand_tag": "DL MOBILIDADE",
        "tagline": "Scooters elétricas NXT em Schroeder e região",
        "site": "dldespachante.com.br",
        "whats": "(47) 99716-2967",
        "instagram": "",   # preenche quando o IG estiver pronto
        # tema laranja/preto (energia + scooter)
        "bg": (15, 17, 22), "card": (26, 29, 38), "accent": (255, 120, 20),
        "accent2": (245, 197, 24), "white": (245, 247, 250), "muted": (170, 178, 188),
        "env": {"token": "DL_PAGE_TOKEN", "ig": "DL_IG_USER_ID", "page": "DL_PAGE_ID"},
        "hashtags": ["#scootereletrica", "#nxt", "#mobilidadeeletrica", "#schroeder",
                     "#jaraguadosul", "#guaramirim", "#dlmobilidade", "#semcnh",
                     "#scooter", "#viacredi"],
        "photo_based": True,   # usa FOTOS REAIS (assets/dl_scooters) com oferta por cima
        "ig_only": True,       # só Instagram (não posta no Facebook)
    },

    "4kitem": {
        "nome": "4kitem",
        "brand_tag": "4KITEM",
        "tagline": "Sistemas que facilitam o seu negócio",
        "site": "4kitem.com.br",
        "whats": "(47) 99960-6998",
        "instagram": "",   # preenche quando o IG estiver pronto
        # tema tech (indigo + ciano)
        "bg": (13, 14, 26), "card": (24, 26, 44), "accent": (108, 99, 255),
        "accent2": (0, 210, 200), "white": (245, 247, 250), "muted": (165, 170, 190),
        "env": {"token": "KITEM_PAGE_TOKEN", "ig": "KITEM_IG_USER_ID", "page": "KITEM_PAGE_ID"},
        "conteudo": KITEM_CONTEUDO,
        "cta_seal": "TESTE GRÁTIS",
        "cta_big": ["COMECE", "HOJE MESMO"],
        "hashtags": ["#4kitem", "#sistema", "#app", "#pequenonegocio", "#empreendedor",
                     "#automatizacao", "#whatsappbusiness", "#agendamento", "#delivery",
                     "#santacatarina"],
        "voz": ("Você é o social media do 4kitem, empresa de sistemas/apps que facilitam o "
                "dia a dia de pequenos negócios. Tom: moderno, direto e simples, SEM "
                "tecniquês. Foque no BENEFÍCIO pro dono do negócio: economiza tempo, vende "
                "mais, menos dor de cabeça. Convide pra testar grátis."),
        "ig_only": True,       # só Instagram (não posta no Facebook)
    },
}


# ----------------------------------------------------------------- DL Mobilidade (foto + oferta)
DL_PHOTOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "dl_scooters")

# Angulos que rotacionam por dia (a foto tambem rotaciona).
DL_ANGLES = [
    {"badge": "EXCLUSIVO · SÓ A DL TEM", "h1": "ATÉ 48x", "h2": "pela Viacredi",
     "sub": "Scooters NXT a partir de R$ 4.990"},
    {"badge": "SEM BUROCRACIA · CONTRAN 996", "h1": "SEM CNH,", "h2": "SEM EMPLACAMENTO",
     "sub": "Liberdade pra rodar sem dor de cabeça"},
    {"badge": "ECONOMIA DE VERDADE", "h1": "ZERO", "h2": "GASOLINA",
     "sub": "Recarrega na tomada · economiza todo mês"},
    {"badge": "VÁRIOS MODELOS NXT", "h1": "A PARTIR DE", "h2": "R$ 4.990",
     "sub": "Do urbano ao premium — tem o seu aqui"},
]

# Bullets do slide (SEM emoji — a fonte do slide nao renderiza emoji).
DL_BENEFITS = [
    "Scooters elétricas NXT — vários modelos",
    "Sem CNH e sem emplacamento (CONTRAN 996)",
    "Autonomia de 50 a 140 km por carga",
    "Até 24x no cartão ou 48x pela Viacredi",
    "Zero gasolina — economia de verdade",
    "Respaldo do Grupo DL",
]


def _dl_photo_card(angle, photo_path, t, outdir, n=1):
    """Slide de oferta: foto real do scooter + gradiente + oferta por cima."""
    from PIL import Image, ImageDraw
    ph = Image.open(photo_path).convert("RGB")
    r = max(W / ph.width, H / ph.height)
    ph = ph.resize((int(ph.width * r), int(ph.height * r)))
    l = (ph.width - W) // 2
    tp = (ph.height - H) // 2
    ph = ph.crop((l, tp, l + W, tp + H))
    # gradiente escuro de baixo p/ cima (leitura do texto)
    grad = Image.new("L", (1, H), 0)
    for y in range(H):
        grad.putpixel((0, y), int(238 * max(0, (y - H * 0.36) / (H * 0.64))))
    ph = Image.composite(Image.new("RGB", (W, H), (8, 10, 16)), ph, grad.resize((W, H)))
    d = ImageDraw.Draw(ph)
    OR, GO, WH = t["accent"], t["accent2"], t["white"]
    gi.pill(d, 56, 56, t["brand_tag"], _font(40), OR, WH)
    gi.pill(d, 56, H - 560, angle["badge"], _font(34), GO, (10, 10, 10))
    d.text((50, H - 500), angle["h1"], font=_font(140, impact=True), fill=WH,
           stroke_width=3, stroke_fill=(0, 0, 0))
    d.text((56, H - 350), angle["h2"], font=_font(62, impact=True), fill=OR)
    d.text((56, H - 262), angle["sub"], font=_font(38), fill=WH)
    d.text((56, H - 200), "Sem CNH · Sem emplacamento · até 32 km/h",
           font=_font(34, bold=False), fill=(195, 200, 210))
    wtxt = f"WhatsApp {t['whats']}"
    fw = _font(40)
    tw = d.textlength(wtxt, font=fw)
    d.rounded_rectangle([56, H - 135, 56 + tw + 60, H - 65], radius=18, fill=(37, 211, 102))
    d.text((86, H - 125), wtxt, font=fw, fill=(5, 50, 30))
    d.text((56, H - 44), "*Financiamento sujeito a análise de crédito.",
           font=_font(26, bold=False), fill=(150, 155, 165))
    p = os.path.join(outdir, f"slide_{n}.png")
    ph.save(p, quality=90)
    return p


def _dl_beneficios(t, outdir, n=2):
    img, d = _canvas(t)
    _brand_header(d, t)
    gi.pill(d, 56, 200, "POR QUE NA DL?", _font(50, impact=True), t["accent"], t["white"])
    y = 360
    fb = _font(44, bold=False)
    for b in DL_BENEFITS:
        d.ellipse([56, y + 12, 78, y + 34], fill=t["accent2"])
        lines = gi.wrap(d, b, fb, W - 180)
        gi.draw_lines(d, lines, fb, 100, y, t["white"], int(fb.size * 1.32))
        y += max(108, len(lines) * int(fb.size * 1.32) + 34)
    _footer(d, t)
    p = os.path.join(outdir, f"slide_{n}.png")
    img.save(p, quality=92)
    return p


def _dl_cta(t, photo_path, outdir, n=3):
    """CTA com foto de fundo + chamada pro WhatsApp."""
    from PIL import Image, ImageDraw
    ph = Image.open(photo_path).convert("RGB")
    r = max(W / ph.width, H / ph.height)
    ph = ph.resize((int(ph.width * r), int(ph.height * r)))
    l = (ph.width - W) // 2
    tp = (ph.height - H) // 2
    ph = ph.crop((l, tp, l + W, tp + H))
    dark = Image.new("RGB", (W, H), (8, 10, 16))
    ph = Image.blend(ph, dark, 0.62)
    d = ImageDraw.Draw(ph)
    OR, WH = t["accent"], t["white"]
    gi.pill(d, 56, 56, t["brand_tag"], _font(40), OR, WH)
    cy = H // 2 - 160
    for i, ln in enumerate(["VEM CONHECER", "SUA NOVA SCOOTER"]):
        f = _font(78, impact=True)
        w = d.textlength(ln, font=f)
        d.text(((W - w) // 2, cy + i * 90), ln, font=f, fill=WH, stroke_width=2, stroke_fill=(0, 0, 0))
    wtxt = t["whats"]
    fw = _font(56)
    w = d.textlength(wtxt, font=fw)
    d.rounded_rectangle([(W - w) // 2 - 50, cy + 240, (W + w) // 2 + 50, cy + 340],
                        radius=22, fill=(37, 211, 102))
    d.text(((W - w) // 2, cy + 260), wtxt, font=fw, fill=(5, 50, 30))
    fl = _font(40, bold=False)
    loc = "Schroeder/SC  ·  " + t["site"]
    w2 = d.textlength(loc, font=fl)
    d.text(((W - w2) // 2, cy + 370), loc, font=fl, fill=(210, 215, 225))
    p = os.path.join(outdir, f"slide_{n}.png")
    ph.save(p, quality=90)
    return p


def _dl_caption(t, angle):
    ig = f"Siga {t['instagram']}\n" if t.get("instagram") else ""
    return (
        "🛴⚡ Scooters elétricas NXT na DL Mobilidade!\n\n"
        "✅ Sem CNH e sem emplacamento (CONTRAN 996)\n"
        "✅ Autonomia de 50 a 140 km por carga\n"
        "✅ Zero gasolina — economia de verdade\n"
        "💳 Até 24x no cartão ou 48x pela VIACREDI — exclusivo da DL!\n"
        "🛡️ Respaldo do Grupo DL\n\n"
        "📍 Schroeder/SC · a partir de R$ 4.990\n"
        f"📲 Faça sua simulação no WhatsApp: {t['whats']}\n"
        f"🌐 {t['site']}\n"
        f"{ig}\n"
        "*Financiamento sujeito a análise de crédito (com juros).\n\n"
        + " ".join(t["hashtags"])
    )


def generate_dl(brand_key, outdir=None):
    t = BRANDS[brand_key]
    yday = datetime.now().timetuple().tm_yday
    angle = DL_ANGLES[yday % len(DL_ANGLES)]
    photos = sorted(glob.glob(os.path.join(DL_PHOTOS_DIR, "*.jpg")))
    if not photos:
        raise RuntimeError("Sem fotos em assets/dl_scooters.")
    ph1 = photos[yday % len(photos)]
    ph2 = photos[(yday + 7) % len(photos)]   # foto diferente no CTA
    if outdir is None:
        outdir = os.path.join(OUT_BASE, datetime.now().strftime("%Y-%m-%d") + f"_{brand_key}")
    os.makedirs(outdir, exist_ok=True)
    paths = [_dl_photo_card(angle, ph1, t, outdir, 1),
             _dl_beneficios(t, outdir, 2),
             _dl_cta(t, ph2, outdir, 3)]
    caption = _dl_caption(t, angle)
    with open(os.path.join(outdir, "legenda.txt"), "w", encoding="utf-8") as f:
        f.write(caption)
    return paths, caption, {"titulo": f"{angle['h1']} {angle['h2']}"}


# ----------------------------------------------------------------- desenho
def _font(size, bold=True, impact=False):
    return gi.font(size, bold=bold, impact=impact)


def _canvas(t):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), t["bg"])
    return img, ImageDraw.Draw(img)


def _brand_header(d, t):
    txt = t["brand_tag"]
    f = _font(34)
    w = d.textlength(txt, font=f)
    d.rounded_rectangle([56, 60, 56 + w + 70, 60 + 64], radius=32, fill=t["accent2"])
    d.ellipse([56 + 26, 60 + 26, 56 + 38, 60 + 38], fill=t["white"])
    d.text((56 + 52, 60 + 14), txt, font=f, fill=t["white"])


def _footer(d, t):
    f = _font(36)
    txt = f"📲 {t['whats']}   ·   {t['site']}"
    # sem emoji na fonte do slide
    txt = f"{t['whats']}   ·   {t['site']}"
    w = d.textlength(txt, font=f)
    d.text(((W - w) // 2, H - 90), txt, font=f, fill=t["muted"])


def slide_capa(t, item, outdir, n=1):
    img, d = _canvas(t)
    _brand_header(d, t)
    # badge categoria
    fb = _font(34)
    badge = item["cat"]
    bw = d.textlength(badge, font=fb)
    gi.pill(d, 56, 200, badge, fb, t["accent"], (10, 10, 10))
    # titulo grande
    ft = _font(82, impact=True)
    lines = gi.wrap(d, item["titulo"], ft, W - 120)[:5]
    y = 320
    for ln in lines:
        d.text((56, y), ln, font=ft, fill=t["white"], stroke_width=2, stroke_fill=(0, 0, 0))
        y += int(ft.size * 1.02)
    # faixa inferior
    d.text((56, H - 150), "ARRASTA PARA O LADO  ->", font=_font(34), fill=t["accent"])
    p = os.path.join(outdir, f"slide_{n}.png")
    img.save(p, quality=92)
    return p


def slide_conteudo(t, item, outdir, n=2):
    img, d = _canvas(t)
    _brand_header(d, t)
    ft = _font(50, impact=True)
    gi.pill(d, 56, 200, "COMO FUNCIONA", ft, t["accent2"], t["white"])
    y = 360
    fb = _font(46, bold=False)
    for b in item["bullets"]:
        # marcador
        d.ellipse([56, y + 12, 56 + 22, y + 34], fill=t["accent"])
        lines = gi.wrap(d, b, fb, W - 180)
        gi.draw_lines(d, lines, fb, 100, y, t["white"], int(fb.size * 1.32))
        y += max(120, len(lines) * int(fb.size * 1.32) + 40)
    _footer(d, t)
    p = os.path.join(outdir, f"slide_{n}.png")
    img.save(p, quality=92)
    return p


def slide_cta(t, outdir, n=3):
    img, d = _canvas(t)
    _brand_header(d, t)
    cy = H // 2 - 180
    fs = _font(44)
    seal = t.get("cta_seal", "FALA COM A GENTE")
    sw = d.textlength(seal, font=fs)
    gi.pill(d, (W - sw) // 2 - 30, cy, seal, fs, t["accent"], (10, 10, 10))
    big = t.get("cta_big", ["RESOLVEMOS", "PRA VOCÊ"])
    fbig = _font(92, impact=True)
    y = cy + 110
    for ln in big:
        w = d.textlength(ln, font=fbig)
        d.text(((W - w) // 2, y), ln, font=fbig, fill=t["white"])
        y += int(fbig.size * 1.03)
    # caixa whats
    fw = _font(54)
    wtxt = t["whats"]
    w = d.textlength(wtxt, font=fw)
    d.rounded_rectangle([(W - w) // 2 - 50, y + 50, (W + w) // 2 + 50, y + 150],
                        radius=22, fill=(37, 211, 102))
    d.text(((W - w) // 2, y + 70), wtxt, font=fw, fill=(5, 50, 30))
    fsite = _font(40, bold=False)
    w2 = d.textlength(t["site"], font=fsite)
    d.text(((W - w2) // 2, y + 180), t["site"], font=fsite, fill=t["muted"])
    p = os.path.join(outdir, f"slide_{n}.png")
    img.save(p, quality=92)
    return p


# ----------------------------------------------------------------- legenda
def build_caption(t, item):
    base = f"{item['titulo']}\n\n"
    base += "\n".join(f"✅ {b}" for b in item["bullets"])
    base += (f"\n\n📲 Fala com a gente no WhatsApp: {t['whats']}"
             f"\n🌐 {t['site']}\n\n")
    if t.get("instagram"):
        base += f"Siga {t['instagram']}\n\n"
    base += " ".join(t["hashtags"])
    return base


def groq_caption(t, item):
    """Reescreve a legenda na voz da marca (Groq, se houver chave). Fallback: base."""
    if not dist.GROQ_API_KEY:
        return build_caption(t, item)
    import requests, json
    bullets = " | ".join(item["bullets"])
    prompt = (
        f"{t['voz']}\n\n"
        "Escreva uma legenda de Instagram (português BR) sobre o tema abaixo. "
        "Regras: 1ª linha é um gancho curto (no máx 1 emoji). Depois 3-4 linhas curtas. "
        "Termine convidando a falar no WhatsApp. NÃO invente serviços além dos listados. "
        "NÃO use hashtags (eu adiciono depois).\n\n"
        f"TEMA: {item['titulo']}\nPONTOS: {bullets}"
    )
    try:
        r = requests.post(
            dist.GROQ_URL,
            headers={"Authorization": f"Bearer {dist.GROQ_API_KEY}",
                     "Content-Type": "application/json"},
            json={"model": dist.GROQ_MODEL,
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.5, "max_tokens": 300},
            timeout=30,
        )
        r.raise_for_status()
        txt = r.json()["choices"][0]["message"]["content"].strip().strip('"')
        return f"{txt}\n\n📲 WhatsApp: {t['whats']}  ·  🌐 {t['site']}\n\n" + " ".join(t["hashtags"])
    except Exception:
        return build_caption(t, item)


# ----------------------------------------------------------------- seleção do dia
def topic_of_the_day(t):
    banco = t["conteudo"]
    idx = datetime.now().timetuple().tm_yday % len(banco)
    return banco[idx]


# ----------------------------------------------------------------- postagem Meta (por marca)
def _brand_tokens(t):
    e = t["env"]
    return (dist._env(e["token"]), dist._env(e["ig"]), dist._env(e["page"]))


def publish_brand(t, prefix, image_paths, caption):
    """Posta carrossel no IG (+ foto no FB, exceto marcas ig_only) usando os TOKENS DA MARCA."""
    token, ig_id, page_id = _brand_tokens(t)
    ig_only = t.get("ig_only", False)
    # IG-only ainda precisa de token + ig_id (o token é da Página vinculada, exigência do Meta),
    # mas NÃO precisa de page_id pois não publicamos nada no feed do Facebook.
    falta = not (token and ig_id) if ig_only else not (token and ig_id and page_id)
    if falta:
        raise RuntimeError(f"Tokens Meta da marca ausentes ({t['env']}).")
    from PIL import Image
    os.makedirs(PUBLIC_IMG_DIR, exist_ok=True)
    GRAPH = dist.GRAPH
    base = dist.PUBLIC_BASE_URL
    public_urls = []
    for i, p in enumerate(image_paths, 1):
        fname = f"{prefix}_s{i}.jpg"
        Image.open(p).convert("RGB").save(os.path.join(PUBLIC_IMG_DIR, fname), "JPEG", quality=90)
        public_urls.append(f"{base}/static/social/{fname}")

    # Instagram carrossel
    children = []
    for u in public_urls:
        res = dist._graph_post(f"{GRAPH}/{ig_id}/media",
                               {"image_url": u, "is_carousel_item": "true", "access_token": token})
        children.append(res["id"])
    cont = dist._graph_post(f"{GRAPH}/{ig_id}/media",
                            {"media_type": "CAROUSEL", "children": ",".join(children),
                             "caption": caption, "access_token": token})["id"]
    import time
    time.sleep(3)
    ig = dist._graph_post(f"{GRAPH}/{ig_id}/media_publish",
                          {"creation_id": cont, "access_token": token})
    # Facebook foto (pulado nas marcas ig_only — DL Mobilidade e 4kitem)
    fb = None
    if not ig_only:
        fb = dist._graph_post(f"{GRAPH}/{page_id}/photos",
                              {"caption": caption, "url": public_urls[0], "access_token": token})
    # Story automatico (capa em 9:16) — desligavel com SOCIAL_STORY=0
    story = None
    if dist._env("SOCIAL_STORY", "1") == "1":
        try:
            story_jpg = os.path.join(PUBLIC_IMG_DIR, f"{prefix}_story.jpg")
            dist._story_image(image_paths[0], story_jpg)
            story_url = f"{base}/static/social/{prefix}_story.jpg"
            sc = dist._graph_post(f"{GRAPH}/{ig_id}/media",
                                  {"media_type": "STORIES", "image_url": story_url,
                                   "access_token": token})["id"]
            time.sleep(2)
            story = dist._graph_post(f"{GRAPH}/{ig_id}/media_publish",
                                     {"creation_id": sc, "access_token": token})
        except Exception as e:
            print(f"   ! Story da marca falhou (segue): {e}")
    return {"instagram": ig, "facebook": fb, "story": story}


# ----------------------------------------------------------------- run
def generate(brand_key, outdir=None, item=None):
    t = BRANDS[brand_key]
    if t.get("photo_based"):
        return generate_dl(brand_key, outdir)
    item = item or topic_of_the_day(t)
    if outdir is None:
        day = datetime.now().strftime("%Y-%m-%d")
        outdir = os.path.join(OUT_BASE, f"{day}_{brand_key}")
    os.makedirs(outdir, exist_ok=True)
    paths = [slide_capa(t, item, outdir, 1),
             slide_conteudo(t, item, outdir, 2),
             slide_cta(t, outdir, 3)]
    caption = groq_caption(t, item)
    with open(os.path.join(outdir, "legenda.txt"), "w", encoding="utf-8") as f:
        f.write(caption)
    return paths, caption, item


def run(brand_key, post=False):
    t = BRANDS[brand_key]
    paths, caption, item = generate(brand_key)
    print(f"[{brand_key}] tópico: {item['titulo']} | {len(paths)} slides")
    if post:
        day = datetime.now().strftime("%Y%m%d")
        r = publish_brand(t, f"{brand_key}_{day}", paths, caption)
        print(f"[{brand_key}] publicado: {r}")
    return paths, caption


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("brand", help="chave da marca (ex: despachante)")
    ap.add_argument("--post", action="store_true")
    args = ap.parse_args()
    if args.brand not in BRANDS:
        print(f"Marca '{args.brand}' nao existe. Disponiveis: {list(BRANDS)}")
        return
    run(args.brand, post=args.post)


if __name__ == "__main__":
    main()
