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
}


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
    seal = "FALA COM A GENTE"
    sw = d.textlength(seal, font=fs)
    gi.pill(d, (W - sw) // 2 - 30, cy, seal, fs, t["accent"], (10, 10, 10))
    big = ["RESOLVEMOS", "PRA VOCÊ"]
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
    """Posta carrossel no IG + foto no FB usando os TOKENS DA MARCA."""
    token, ig_id, page_id = _brand_tokens(t)
    if not (token and ig_id and page_id):
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
    # Facebook foto
    fb = dist._graph_post(f"{GRAPH}/{page_id}/photos",
                          {"caption": caption, "url": public_urls[0], "access_token": token})
    return {"instagram": ig, "facebook": fb}


# ----------------------------------------------------------------- run
def generate(brand_key, outdir=None, item=None):
    t = BRANDS[brand_key]
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
