# -*- coding: utf-8 -*-
"""
comunidade.py — Engine de COMUNIDADE (Rádio SC News).
Fura o teto da notícia-commodity: a audiência vira o conteúdo. Franquias recorrentes com
NOME + DIA fixo (conteúdo de hora marcada que vicia) que puxam COMENTÁRIO (engajamento = ouro
do algoritmo) com custo de produção ~zero (banco de perguntas curado, rotaciona por semana).

Reusa gen_instagram (arte) + distribuidor (postagem/legenda). Posta como mini-carrossel de 2
slides (pergunta + CTA de engajamento) p/ usar a infra de carrossel que já existe.

Franquia ativa: "DIZ AÍ, VALE" (pergunta da semana). Adicionar outras é só pôr em FRANQUIAS.
"""
import os
from datetime import datetime

from PIL import Image, ImageDraw

import gen_instagram as gi
import distribuidor as dist

FRANQUIAS = {
    "diz_ai_vale": {
        "selo": "DIZ AÍ, VALE",
        "prompts": [
            "Qual o MELHOR lugar pra comer no Vale do Itapocu?",
            "Que obra a sua cidade mais precisa AGORA?",
            "Qual o ponto mais bonito do Norte de SC?",
            "Onde tem o melhor café da manhã da região?",
            "Que evento NÃO PODE faltar no calendário do Vale?",
            "Qual a rua mais perigosa pra dirigir na sua cidade?",
            "Melhor padaria do Vale: qual é? Sem dó!",
            "O que você MAIS ama na sua cidade?",
            "Qual lugar do Vale todo turista tinha que conhecer?",
            "Que comércio antigo da sua cidade faz falta hoje?",
            "Qual a melhor praça pra levar as crianças?",
            "Time do coração aqui da região: qual?",
        ],
    },
}


def _card(selo, pergunta, outdir):
    """Card 1080x1350 da pergunta: selo + pergunta grande + 'RESPONDE AQUI EMBAIXO'."""
    W, H = gi.W, gi.H
    canvas = Image.new("RGB", (W, H), gi.BG)
    d = ImageDraw.Draw(canvas)
    gi.brand_header(d)

    fh = gi.font(72, impact=True)
    lines = gi.wrap(d, pergunta.upper(), fh, W - 130)
    lh = int(fh.size * 1.08)
    block = len(lines) * lh
    y0 = (H - block) // 2 - 20

    # selo (pill dourado) acima da pergunta
    fs = gi.font(40)
    sw = d.textlength(selo, font=fs)
    py = y0 - 130
    d.rounded_rectangle([(W - sw) // 2 - 30, py - 12, (W + sw) // 2 + 30, py + 62],
                        radius=30, fill=gi.GOLD)
    d.text(((W - sw) // 2, py), selo, font=fs, fill=gi.BLACK)

    # pergunta
    y = y0
    for ln in lines:
        w = d.textlength(ln, font=fh)
        d.text(((W - w) // 2, y), ln, font=fh, fill=gi.WHITE, stroke_width=3, stroke_fill=gi.BLACK)
        y += lh

    # chamada pro comentário (pill vermelho)
    cta = "RESPONDE AQUI EMBAIXO"
    fc = gi.font(46)
    w = d.textlength(cta, font=fc)
    yy = y0 + block + 64
    d.rounded_rectangle([(W - w) // 2 - 34, yy - 14, (W + w) // 2 + 34, yy + 68],
                        radius=22, fill=gi.RED)
    d.text(((W - w) // 2, yy), cta, font=fc, fill=gi.WHITE)

    gi.footer_site(d)
    path = os.path.join(outdir, "slide_1.png")
    canvas.save(path, quality=92)
    return path


def caption(selo, pergunta):
    canal = dist.WHATSAPP_CHANNEL
    bloco_canal = (f"🔔 E recebe a notícia do Vale ANTES no Canal do WhatsApp:\n"
                   f"👉 {canal}\n\n" if canal else "")
    tags = list(dict.fromkeys(["#vale", "#valedoitapocu"] + gi.BASE_TAGS))
    return (
        f"🗣️ {selo}: {pergunta}\n\n"
        f"💬 Responde aqui embaixo — a gente lê TODOS os comentários!\n"
        f"🔁 Marca alguém do Vale pra dar o palpite  ·  🔖 Salva pra votar depois\n"
        f"➕ Segue @radioscnews — o Norte de SC em 1 minuto\n\n"
        f"{bloco_canal}"
        + " ".join(tags)
    )


def run(post=False, franquia_key="diz_ai_vale"):
    """Gera (e opcionalmente posta) a franquia da semana. Mini-carrossel: pergunta + CTA."""
    fr = FRANQUIAS[franquia_key]
    prompts = fr["prompts"]
    idx = datetime.now().isocalendar()[1] % len(prompts)   # rotaciona por semana do ano
    pergunta = prompts[idx]
    selo = fr["selo"]

    day = datetime.now().strftime("%Y-%m-%d")
    outdir = os.path.join("instagram_posts", day + "_comunidade", franquia_key)
    os.makedirs(outdir, exist_ok=True)

    imgs = [_card(selo, pergunta, outdir),
            gi.slide_cta({"city": None}, outdir, 2)]   # slide 2 = engajamento + Canal
    cap = caption(selo, pergunta)
    with open(os.path.join(outdir, "legenda.txt"), "w", encoding="utf-8") as f:
        f.write(cap)

    if post:
        dist.publish_images(f"com_{franquia_key}", imgs, cap)
    return {"franquia": selo, "pergunta": pergunta, "imgs": imgs, "outdir": outdir,
            "postado": bool(post)}


if __name__ == "__main__":
    r = run(post=False)
    print(f"Franquia: {r['franquia']} | Pergunta: {r['pergunta']}")
    print(f"Slides em: {r['outdir']}")
