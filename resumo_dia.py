# -*- coding: utf-8 -*-
"""
resumo_dia.py — "O VALE EM 60 SEGUNDOS": Reels DIÁRIO de resumo (motor de ALCANCE + hábito).

As 3 principais notícias do dia num vídeo vertical de ~60s, com abertura e fecho de marca.
É o conteúdo de HÁBITO (mesma hora, todo dia) que vira a cara da marca no Instagram e converte
quem assiste em SEGUIDOR. Reaproveita TODO o motor do reels.py (narração edge-tts, legenda CapCut,
montagem moviepy, publicação Meta) — zero dependência nova.

É o ESQUELETO do "jornal do Vale" — no futuro vira vídeo rico (b-roll, cortes etc).

Travas (env): RESUMO_ON (liga o job diário, default 0) · RESUMO_POST (posta de verdade, default 0;
sem isso só GERA pra revisão em /admin/resumo). O render roda na Railway (moviepy), não local.

Uso:  python resumo_dia.py            # gera o vídeo do dia (preview, não posta)
      resumo_dia.run(post=False)      # idem (scheduler)
"""
import os
import re
from datetime import datetime

from PIL import Image, ImageDraw

import gen_instagram as gi
import distribuidor as dist
import reels as rl
import tts_engine

W, H = rl.REEL_W, rl.REEL_H   # 1080x1920 (9:16)


# ---------------------------------------------------------------- seleção das 3 do dia
def _selecionar(conn, n=3):
    """As n melhores notícias recentes, NÃO sensíveis, priorizando Norte de SC, sem fato repetido."""
    def _q(horas):
        return conn.execute(
            "SELECT * FROM news WHERE active=1 AND title IS NOT NULL AND title!='' "
            "AND created_at > datetime('now', ?) "
            "ORDER BY priority DESC, datetime(published_at) DESC LIMIT 60",
            (f"-{horas} hours",)).fetchall()
    rows = _q(36) or _q(96) or conn.execute(
        "SELECT * FROM news WHERE active=1 AND title IS NOT NULL AND title!='' "
        "ORDER BY datetime(published_at) DESC LIMIT 60").fetchall()

    seguras = [r for r in rows if not dist.sensitive_reason(r)]
    local = [r for r in seguras if r["city"] in gi.NORTE_SC]
    pool = (local + [r for r in seguras if r not in local])
    picked = []
    for r in pool:
        if len(picked) >= n:
            break
        if dist.duplicate_of(r, picked):
            continue
        picked.append(r)
    return picked


# ---------------------------------------------------------------- cards de marca (intro/fecho)
def _grad(top, bot):
    g = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / H
        g.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    return g.resize((W, H))


def _intro_card(dia, outdir):
    canvas = _grad((14, 15, 21), (44, 16, 22))
    d = ImageDraw.Draw(canvas)
    gi.pill(d, 70, 150, "  " + gi.BRAND + "  ", gi.font(44), gi.RED, gi.WHITE)
    fb = gi.font(120, impact=True)
    for i, ln in enumerate(["O VALE EM", "60 SEGUNDOS"]):
        w = d.textlength(ln, font=fb)
        col = gi.GOLD if i == 1 else gi.WHITE
        d.text(((W - w) // 2, 720 + i * 150), ln, font=fb, fill=col, stroke_width=3, stroke_fill=gi.BLACK)
    dias = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
    data = f"{dias[dia.weekday()]}, {dia.strftime('%d/%m')}"
    fd = gi.font(52)
    w = d.textlength(data, font=fd)
    d.text(((W - w) // 2, 1040), data, font=fd, fill=gi.MUTED)
    ft = gi.font(46, impact=True)
    tag = "AS 3 DE HOJE  ->"
    w = d.textlength(tag, font=ft)
    d.rounded_rectangle([(W - w) // 2 - 30, 1240, (W + w) // 2 + 30, 1320], radius=22, fill=gi.RED)
    d.text(((W - w) // 2, 1255), tag, font=ft, fill=gi.WHITE)
    p = os.path.join(outdir, "intro.jpg")
    canvas.convert("RGB").save(p, "JPEG", quality=90)
    return p


def _outro_card(outdir):
    canvas = _grad((14, 15, 21), (16, 30, 22))
    d = ImageDraw.Draw(canvas)
    gi.pill(d, 70, 150, "  " + gi.BRAND + "  ", gi.font(44), gi.RED, gi.WHITE)
    seal = "GOSTOU?"
    fs = gi.font(64, impact=True)
    w = d.textlength(seal, font=fs)
    d.rounded_rectangle([(W - w) // 2 - 36, 700, (W + w) // 2 + 36, 790], radius=44, fill=gi.GOLD)
    d.text(((W - w) // 2, 714), seal, font=fs, fill=gi.BLACK)
    for i, ln in enumerate(["SEGUE PRA NÃO", "PERDER O VALE"]):
        fb = gi.font(86, impact=True)
        w = d.textlength(ln, font=fb)
        d.text(((W - w) // 2, 850 + i * 110), ln, font=fb, fill=gi.WHITE, stroke_width=2, stroke_fill=gi.BLACK)
    sub = "Todo dia o resumo, primeiro aqui."
    fsub = gi.font(46)
    w = d.textlength(sub, font=fsub)
    d.text(((W - w) // 2, 1110), sub, font=fsub, fill=gi.MUTED)
    handle = "@radioscnews"
    fh = gi.font(64, impact=True)
    w = d.textlength(handle, font=fh)
    d.text(((W - w) // 2, 1260), handle, font=fh, fill=gi.GOLD)
    p = os.path.join(outdir, "outro.jpg")
    canvas.convert("RGB").save(p, "JPEG", quality=90)
    return p


# ---------------------------------------------------------------- narração + legenda
def _script(noticias):
    partes = ["O Vale em 60 segundos. As principais notícias de hoje."]
    for news in noticias:
        resumo = dist.groq_summary(news)
        flash = dist.flash_manchete(news)
        gancho = re.sub(r"\s+", " ", (flash or news["title"] or "")).strip().rstrip(".")
        city = news["city"] or ""
        corpo = dist._short_resumo(resumo, max_chars=200)
        seg = f"{gancho}."
        if city and city.lower() not in gancho.lower():
            seg += f" Em {city}."
        if corpo:
            seg += f" {corpo}"
        partes.append(seg)
    partes.append("Seguiu a Rádio SC News? Todo dia o resumo do Vale, primeiro pra você.")
    return " ".join(partes)


def _legenda(dia, titulos):
    nums = ["1️⃣", "2️⃣", "3️⃣"]
    linhas = "\n".join(f"{nums[i]} {t}" for i, t in enumerate(titulos[:3]))
    return (f"🎙️ O VALE EM 60 SEGUNDOS — {dia.strftime('%d/%m')}\n\n"
            f"As principais de hoje no Vale:\n{linhas}\n\n"
            f"Seguiu? Todo dia tem o resumo aqui. 👉 @radioscnews\n"
            f"Salva e marca um amigo do Vale 💚\n\n"
            f"#radioscnews #norteSC #valedoitapocu #jaraguadosul #schroeder #guaramirim #joinville #corupa")


# ---------------------------------------------------------------- pipeline
def run(post=False):
    """Gera o Reels 'O Vale em 60s' do dia. post=True publica (gated pelo scheduler)."""
    conn = dist.get_db()
    dist.ensure_column(conn)
    noticias = _selecionar(conn, 3)
    if len(noticias) < 2:
        conn.close()
        return {"ok": False, "motivo": "poucas notícias hoje"}

    dia = datetime.now()
    slug = dia.strftime("%Y-%m-%d")
    work = os.path.join(dist.PREVIEW_BASE, slug + "_resumo")
    vert = os.path.join(work, "vert")
    os.makedirs(vert, exist_ok=True)

    imgs = [_intro_card(dia, vert)]
    titulos = []
    for i, news in enumerate(noticias, 1):
        flash = dist.flash_manchete(news)
        cover = gi.slide_cover(news, work, manchete=flash)
        imgs.append(rl._to_vertical(cover, os.path.join(vert, f"n{i}.jpg")))
        titulos.append((news["title_own"] or news["title"] or "")[:80])
    imgs.append(_outro_card(vert))

    script = _script(noticias)
    os.makedirs(rl.AUDIO_DIR, exist_ok=True)
    narr = os.path.join(rl.AUDIO_DIR, f"resumo_{slug}.mp3")
    prefer_free = dist._env("REELS_USE_ELEVEN", "0") != "1"
    if not tts_engine.generate_tts(script, narr, category=None, prefer_free=prefer_free):
        conn.close()
        return {"ok": False, "motivo": "TTS falhou"}

    os.makedirs(rl.REELS_DIR, exist_ok=True)
    mp4 = os.path.join(rl.REELS_DIR, f"resumo_{slug}.mp4")
    rl.build_reel(imgs, narr, mp4, min_seconds=30.0,
                  caption_script=script, capdir=os.path.join(work, "caps"))

    legenda = _legenda(dia, titulos)
    with open(os.path.join(rl.REELS_DIR, f"resumo_{slug}.txt"), "w", encoding="utf-8") as f:
        f.write(legenda)

    res = {"ok": True, "mp4": mp4, "titulos": titulos, "legenda": legenda, "postado": False}
    if post:
        video_url = f"{dist.PUBLIC_BASE_URL}/static/social/resumo_{slug}.mp4"
        try:
            res["instagram"] = rl.post_instagram_reel(video_url, legenda)
            try:
                rl.post_facebook_video(video_url, legenda)
            except Exception:
                pass
            res["postado"] = True
        except Exception as e:
            res["erro"] = str(e)
    conn.close()
    return res


def ultimo():
    """Caminho web do último resumo gerado (pro /admin/resumo), ou None."""
    import glob
    vids = sorted(glob.glob(os.path.join(rl.REELS_DIR, "resumo_*.mp4")))
    if not vids:
        return None
    mp4 = vids[-1]
    leg = mp4[:-4] + ".txt"
    legenda = ""
    if os.path.exists(leg):
        with open(leg, encoding="utf-8") as f:
            legenda = f.read()
    return {"video": "/" + mp4.replace("\\", "/"), "legenda": legenda}


if __name__ == "__main__":
    out = run(post=False)
    print(out if not out.get("ok") else f"OK: {out['mp4']} | {out['titulos']}")
