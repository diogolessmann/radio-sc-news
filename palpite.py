# -*- coding: utf-8 -*-
"""
palpite.py — "O PALPITE DO VALE" (gamificação / moeda social).
O loop do "EU FALEI": a galera crava o palpite (A ou B), volta pra ver se acertou, e os
VENCEDORES se gabam = 2 posts por palpite (vota + revela) + retorno + zoeira. Conteúdo de
hábito que vicia. Reusa gen_instagram + distribuidor (publish_single).
"""
import os
from datetime import datetime

from PIL import Image, ImageDraw

import gen_instagram as gi
import distribuidor as dist


def slide_palpite(time_a, time_b, evento, outdir):
    """Card 'QUEM LEVA?' (A vs B) — formato VS vertical, nomes de qualquer tamanho cabem."""
    W, H = gi.W, gi.H
    canvas = Image.new("RGB", (W, H), gi.BG)
    d = ImageDraw.Draw(canvas)
    gi.brand_header(d)

    # selo dourado
    selo = "PALPITE DO VALE"
    fs = gi.font(38)
    sw = d.textlength(selo, font=fs)
    d.rounded_rectangle([(W - sw) // 2 - 28, 200, (W + sw) // 2 + 28, 268], radius=28, fill=gi.GOLD)
    d.text(((W - sw) // 2, 210), selo, font=fs, fill=gi.BLACK)

    # QUEM LEVA?
    fq = gi.font(92, impact=True)
    q = "QUEM LEVA?"
    qw = d.textlength(q, font=fq)
    d.text(((W - qw) // 2, 320), q, font=fq, fill=gi.WHITE, stroke_width=3, stroke_fill=gi.BLACK)
    if evento:
        fe = gi.font(38)
        ew = d.textlength(evento.upper(), font=fe)
        d.text(((W - ew) // 2, 432), evento.upper(), font=fe, fill=gi.MUTED)

    # bloco VS vertical: A / TIME_A / X / B / TIME_B
    def _opcao(letra, nome, y, cor_letra):
        fl = gi.font(56, impact=True)
        lw = d.textlength(letra, font=fl)
        d.rounded_rectangle([(W - lw) // 2 - 26, y, (W + lw) // 2 + 26, y + 78], radius=18, fill=cor_letra)
        d.text(((W - lw) // 2, y + 6), letra, font=fl, fill=gi.BLACK)
        fn = gi.font(64, impact=True)
        yy = y + 96
        for ln in gi.wrap(d, nome.upper(), fn, W - 140):
            nw = d.textlength(ln, font=fn)
            d.text(((W - nw) // 2, yy), ln, font=fn, fill=gi.WHITE, stroke_width=2, stroke_fill=gi.BLACK)
            yy += int(fn.size * 1.02)
        return yy

    y = 560
    y = _opcao("A", time_a, y, gi.GOLD) + 14
    fx = gi.font(50, impact=True)
    xw = d.textlength("X", font=fx)
    d.text(((W - xw) // 2, y), "X", font=fx, fill=gi.RED)
    y += 80
    y = _opcao("B", time_b, y, gi.WHITE)

    # gancho de gamificação
    hall = "QUEM ACERTAR ENTRA NO HALL DA FAMA"
    fh = gi.font(34)
    hw = d.textlength(hall, font=fh)
    d.rounded_rectangle([(W - hw) // 2 - 24, H - 200, (W + hw) // 2 + 24, H - 138], radius=20, fill=gi.RED)
    d.text(((W - hw) // 2, H - 192), hall, font=fh, fill=gi.WHITE)
    vota = "VOTA A OU B NOS COMENTARIOS"
    fv = gi.font(36, impact=True)
    vw = d.textlength(vota, font=fv)
    d.text(((W - vw) // 2, H - 116), vota, font=fv, fill=gi.GOLD)

    gi.footer_site(d)
    path = os.path.join(outdir, "palpite.png")
    canvas.save(path, quality=95)
    return path


def caption(time_a, time_b, evento):
    return (
        f"🏆 PALPITE DO VALE — {evento}!\n\n"
        f"E aí, QUEM LEVA? Crava o teu palpite 👇\n"
        f"🅰️ {time_a}\n"
        f"🅱️ {time_b}\n\n"
        f"Comenta A ou B — quem ACERTAR a gente lembra, entra no Hall da Fama do Vale 😎\n"
        f"🔁 Marca aquele amigo que SEMPRE erra o palpite kkk\n\n"
        f"➕ Segue @radiosc.news pra ver o resultado depois!\n\n"
        f"#palpite #futebol #vale #valedoitapocu #nortedesc #radioscnews"
    )


def run(time_a, time_b, evento, post=False):
    day = datetime.now().strftime("%Y-%m-%d")
    outdir = os.path.join("instagram_posts", day + "_palpite")
    os.makedirs(outdir, exist_ok=True)
    img = slide_palpite(time_a, time_b, evento, outdir)
    cap = caption(time_a, time_b, evento)
    with open(os.path.join(outdir, "legenda.txt"), "w", encoding="utf-8") as f:
        f.write(cap)
    if post:
        dist.publish_single("palpite", img, cap)
    return {"img": img, "outdir": outdir, "postado": bool(post)}


if __name__ == "__main__":
    r = run("Portugal", "Colômbia", "Hoje, 21h")
    print("card:", r["img"])
