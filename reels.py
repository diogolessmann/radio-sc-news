# -*- coding: utf-8 -*-
"""
reels.py — Gerador e publicador de REELS (Instagram) / vídeo (Facebook)
Rádio SC News

IDEIA: reaproveita os slides do carrossel (gen_instagram) e a voz de IA
(tts_engine) para montar um vídeo vertical 9:16 narrado e publicar como Reels
no Instagram + vídeo na Página do Facebook. É o motor de ALCANCE do projeto.

FLUXO (run_reel):
  1. pega a próxima notícia não-postada (reaproveita distribuidor.pick_next)
  2. FILTRO EDITORIAL: tema sensível é segurado p/ revisão (não vira Reels sozinho)
  3. resume com a voz "vizinho" (distribuidor.groq_summary)
  4. gera os slides (distribuidor.generate_images) e converte p/ 1080x1920
  5. narra o resumo (tts_engine.generate_tts) -> mp3 curto
  6. monta o mp4 (moviepy + ffmpeg empacotado via imageio-ffmpeg)
  7. publica: Reels no Instagram + vídeo na Página (Graph API)
  8. marca a notícia como postada (reusa distribuidor.mark_*)

Requer no ambiente os mesmos tokens Meta do distribuidor.

USO local (dry-run, só gera o mp4, NÃO posta):
  venv\\Scripts\\python.exe reels.py --id 91
USO real (posta):
  venv\\Scripts\\python.exe reels.py --post
"""
import argparse
import os
import re
import time
from datetime import datetime

import requests

import gen_instagram as gi
import distribuidor as dist
import tts_engine

# ---------------------------------------------------------------- config
REEL_W, REEL_H = 1080, 1920          # 9:16 (formato Reels)
REELS_DIR = os.path.join("static", "social")   # mesmo dir público das imagens
AUDIO_DIR = os.environ.get("AUDIO_DIR", "audio")

GRAPH = dist.GRAPH


# ---------------------------------------------------------------- imagem 9:16
def _to_vertical(img_path, out_path):
    """Coloca um slide (1080x1350) num canvas 1080x1920 com fundo de marca (9:16)."""
    from PIL import Image
    canvas = Image.new("RGB", (REEL_W, REEL_H), gi.BG)
    im = Image.open(img_path).convert("RGB")
    if im.width != REEL_W:
        new_h = int(im.height * REEL_W / im.width)
        im = im.resize((REEL_W, new_h))
    # se ficou mais alto que o canvas, corta o excedente (centralizado)
    if im.height > REEL_H:
        top = (im.height - REEL_H) // 2
        im = im.crop((0, top, REEL_W, top + REEL_H))
    y = (REEL_H - im.height) // 2
    canvas.paste(im, (0, max(0, y)))
    canvas.save(out_path, "JPEG", quality=90)
    return out_path


# ---------------------------------------------------------------- narração
def _narration_script(news, resumo):
    """Texto curto pra narrar no Reels: cidade + título + corpo do resumo (sem emoji)."""
    title = re.sub(r"\s+", " ", (news["title"] or "")).strip().rstrip(".")
    corpo = dist._short_resumo(resumo, max_chars=320)
    city = news["city"] or "Santa Catarina"
    partes = [f"{city}.", f"{title}."]
    if corpo:
        partes.append(corpo)
    partes.append("Siga a Rádio SC News e fique por dentro de tudo no Vale.")
    return " ".join(partes)


# ---------------------------------------------------------------- legendas na tela (retenção)
def _caption_images(script, total, capdir):
    """Gera PNGs de legenda (estilo CapCut) ~sincronizados ao áudio: agrupa o texto narrado em
    frases de até 3 palavras e dá a cada uma um tempo proporcional ao tamanho. SEM dependência
    nova: PIL desenha (transparente), o moviepy só sobrepõe — evita o ImageMagick do TextClip.
    Devolve [(png, inicio_seg, duracao_seg)]."""
    from PIL import Image, ImageDraw
    words = [w for w in re.sub(r"\s+", " ", (script or "")).strip().split(" ") if w]
    if not words:
        return []
    grupos = [" ".join(words[i:i + 3]) for i in range(0, len(words), 3)]
    total_chars = sum(len(g) for g in grupos) or 1
    os.makedirs(capdir, exist_ok=True)
    fnt = gi.font(66, impact=True)
    out, t = [], 0.0
    for i, g in enumerate(grupos):
        dur = max(0.6, total * len(g) / total_chars)
        img = Image.new("RGBA", (REEL_W, 320), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        lines = gi.wrap(d, g.upper(), fnt, REEL_W - 140)
        lh = int(fnt.size * 1.12)
        y = (320 - lh * len(lines)) // 2
        for ln in lines:
            w = d.textlength(ln, font=fnt)
            d.text(((REEL_W - w) // 2, y), ln, font=fnt, fill=(255, 255, 255, 255),
                   stroke_width=7, stroke_fill=(0, 0, 0, 255))
            y += lh
        p = os.path.join(capdir, f"cap_{i:03d}.png")
        img.save(p)
        out.append((p, t, dur))
        t += dur
    return out


# ---------------------------------------------------------------- montagem do vídeo
def build_reel(image_paths, audio_path, out_mp4, min_seconds=6.0, caption_script=None, capdir=None):
    """Monta o mp4 vertical: slides em sequência + narração + LEGENDA palavra-a-palavra na tela
    (retenção). Usa moviepy (ffmpeg empacotado via imageio-ffmpeg). As legendas são opcionais e
    defensivas: se algo falhar, cai pro vídeo sem legenda (nunca quebra o post)."""
    from moviepy.editor import (ImageClip, concatenate_videoclips, AudioFileClip,
                                CompositeVideoClip)

    audio = AudioFileClip(audio_path)
    total = max(float(audio.duration or 0), min_seconds)
    per = total / max(len(image_paths), 1)

    clips = [ImageClip(p).set_duration(per) for p in image_paths]
    base = concatenate_videoclips(clips, method="chain").set_duration(total)

    layers = [base]
    ligado = dist._env("REELS_CAPTIONS", "1") != "0"
    if ligado and caption_script and capdir:
        try:
            for png, start, dur in _caption_images(caption_script, total, capdir):
                cap = (ImageClip(png, transparent=True)
                       .set_start(start).set_duration(dur)
                       .set_position(("center", REEL_H - 560)))
                layers.append(cap)
        except Exception as e:
            print(f"   ! legenda na tela falhou (segue sem): {e}")
            layers = [base]

    video = CompositeVideoClip(layers, size=(REEL_W, REEL_H)).set_audio(audio).set_duration(total)

    video.write_videofile(
        out_mp4,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=2,
        ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
        logger=None,
    )
    try:
        audio.close()
        video.close()
    except Exception:
        pass
    return out_mp4


# ---------------------------------------------------------------- publicação Meta
def post_instagram_reel(video_url, caption, poll_tries=40, poll_wait=6, location_id=None):
    """Publica um Reels no Instagram. Vídeo precisa estar em URL pública (https).
    location_id (opcional): geotag da cidade (sinal forte de busca hiperlocal)."""
    cont_data = {"media_type": "REELS", "video_url": video_url, "caption": caption,
                 "share_to_feed": "true", "access_token": dist.META_PAGE_TOKEN}
    if location_id:
        cont_data["location_id"] = location_id
    container = dist._graph_post(f"{GRAPH}/{dist.META_IG_USER_ID}/media", cont_data)["id"]

    # Reels processa de forma assíncrona — espera ficar FINISHED antes de publicar
    for _ in range(poll_tries):
        time.sleep(poll_wait)
        st = requests.get(
            f"{GRAPH}/{container}",
            params={"fields": "status_code,status", "access_token": dist.META_PAGE_TOKEN},
            timeout=30,
        ).json()
        code = st.get("status_code")
        if code == "FINISHED":
            break
        if code == "ERROR":
            raise RuntimeError(f"Reels processamento falhou: {st}")
    else:
        raise RuntimeError("Reels não ficou pronto a tempo (timeout no processamento).")

    return dist._graph_post(
        f"{GRAPH}/{dist.META_IG_USER_ID}/media_publish",
        {"creation_id": container, "access_token": dist.META_PAGE_TOKEN},
    )


def post_facebook_video(video_url, caption):
    """Publica o mesmo vídeo na Página do Facebook (aparece no feed e na aba de vídeos)."""
    return dist._graph_post(
        f"{GRAPH}/{dist.META_PAGE_ID}/videos",
        {"file_url": video_url, "description": caption, "access_token": dist.META_PAGE_TOKEN},
    )


# ---------------------------------------------------------------- pipeline de UMA notícia
def make_reel_for(news, day_dir, do_post=False):
    nid = news["id"]
    print(f"\n=== REEL [{nid}] {news['city']} | {(news['title'] or '')[:60]} ===")

    resumo = dist.groq_summary(news)
    caption = dist.social_caption(news, resumo)
    zap = dist.whatsapp_message(news, resumo)
    media_url = f"{dist.PUBLIC_BASE_URL}/static/social/r{nid}.mp4"

    # 1) slides do carrossel (reusa o gerador existente)
    outdir = os.path.join(day_dir, str(nid))
    slides = dist.generate_images(news, outdir)

    # 2) converte cada slide p/ 1080x1920
    vert_dir = os.path.join(outdir, "vert")
    os.makedirs(vert_dir, exist_ok=True)
    vslides = [_to_vertical(p, os.path.join(vert_dir, f"v{i}.jpg"))
               for i, p in enumerate(slides, 1)]

    # 3) narração curta do resumo
    os.makedirs(AUDIO_DIR, exist_ok=True)
    narr_path = os.path.join(AUDIO_DIR, f"reel_{nid}.mp3")
    script = _narration_script(news, resumo)
    # Por padrao narra com edge-tts (GRATIS) p/ poupar creditos do ElevenLabs.
    # Ligue REELS_USE_ELEVEN=1 no ambiente se quiser a voz premium nos Reels.
    prefer_free = dist._env("REELS_USE_ELEVEN", "0") != "1"
    audio = tts_engine.generate_tts(script, narr_path, category=news["category"],
                                    prefer_free=prefer_free)
    if not audio:
        raise RuntimeError("não consegui gerar a narração (TTS).")

    # 4) monta o mp4 (com legenda palavra-a-palavra na tela = retenção)
    os.makedirs(REELS_DIR, exist_ok=True)
    mp4_path = os.path.join(REELS_DIR, f"r{nid}.mp4")
    build_reel(vslides, narr_path, mp4_path,
               caption_script=script, capdir=os.path.join(outdir, "caps"))
    size_mb = os.path.getsize(mp4_path) / (1024 * 1024)
    print(f"   🎬 mp4 gerado: {mp4_path} ({size_mb:.1f} MB)")

    if not do_post:
        print("   (dry-run) vídeo pronto, NADA foi publicado.")
        return {"mp4": mp4_path, "zap": zap, "media_url": media_url}

    video_url = f"{dist.PUBLIC_BASE_URL}/static/social/r{nid}.mp4"
    loc = None
    try:
        import geo
        loc = geo.location_id(news["city"])
    except Exception:
        loc = None
    print("   > publicando Reels no Instagram...")
    ig = post_instagram_reel(video_url, caption, location_id=loc)
    if loc:
        print(f"     📍 geotag: {loc}")
    print(f"     IG Reels ok: {ig}")
    print("   > publicando vídeo no Facebook...")
    try:
        fb = post_facebook_video(video_url, caption)
        print(f"     FB vídeo ok: {fb}")
    except Exception as e:
        fb = {"erro": str(e)}
        print(f"     ! FB vídeo falhou (segue mesmo assim): {e}")
    return {"instagram": ig, "facebook": fb, "mp4": mp4_path,
            "zap": zap, "media_url": media_url}


# ---------------------------------------------------------------- entrada p/ scheduler
def run_reel(post=False, limit=1):
    """Gera (e opcionalmente publica) Reels das próximas notícias. Mesmo filtro
    editorial do distribuidor. Retorna {postadas, erros, seguradas}."""
    conn = dist.get_db()
    dist.ensure_column(conn)
    pool = dist.pick_next(conn, only_id=None, limit=max(limit * 6, 12))
    if not pool:
        conn.close()
        return {"postadas": 0, "erros": ["nada pendente"], "seguradas": []}

    day_dir = os.path.join(dist.PREVIEW_BASE, datetime.now().strftime("%Y-%m-%d") + "_reels")
    os.makedirs(day_dir, exist_ok=True)

    done, erros, seguradas = 0, [], []
    vistos = list(dist.recent_posted(conn)) if post else []
    for news in pool:
        if done >= limit:
            break
        if post:
            reason = dist.sensitive_reason(news)
            if reason:
                dist.mark_hold(conn, news["id"], reason)
                aviso = f"materia {news['id']} SEGURADA p/ revisao (tema sensivel: '{reason}')"
                print("   ⏸ " + aviso)
                seguradas.append(aviso)
                vistos.append(news)
                continue
            dup = dist.duplicate_of(news, vistos)
            if dup:
                dist.mark_dup(conn, news["id"], dup)
                aviso = f"materia {news['id']} PULADA (duplicada do mesmo fato da #{dup})"
                print("   ♻ " + aviso)
                seguradas.append(aviso)
                vistos.append(news)
                continue
        try:
            res = make_reel_for(news, day_dir, do_post=post)
            if post:
                dist.mark_posted(conn, news["id"])
                dist.mark_cluster(conn, news)  # blindagem cross-engine (carrossel x reels)
                # Loop de Insights: salva o id do Reels no IG
                try:
                    dist.mark_media(conn, news["id"], dist._extract_ig_id(res))
                except Exception:
                    pass
                dist.save_channel_payload(conn, news["id"],
                                          res.get("zap", ""), res.get("media_url", ""))
                vistos.append(news)
            done += 1
        except Exception as e:
            msg = f"materia {news['id']}: {e}"
            print("   ! ERRO " + msg)
            erros.append(msg)
    conn.close()
    return {"postadas": done, "erros": erros, "seguradas": seguradas}


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Gerador de Reels RadioSC News")
    ap.add_argument("--id", type=int, default=None, help="materia especifica")
    ap.add_argument("--limit", type=int, default=1, help="quantas")
    ap.add_argument("--post", action="store_true", help="PUBLICA de verdade")
    args = ap.parse_args()

    conn = dist.get_db()
    dist.ensure_column(conn)
    news_list = dist.pick_next(conn, only_id=args.id, limit=args.limit)
    conn.close()
    if not news_list:
        print("Nenhuma materia pendente. 🎉")
        return

    day_dir = os.path.join(dist.PREVIEW_BASE, datetime.now().strftime("%Y-%m-%d") + "_reels")
    os.makedirs(day_dir, exist_ok=True)
    print(f"Modo: {'POST REAL' if args.post else 'DRY-RUN (so gera mp4)'} | Materias: {len(news_list)}")
    for news in news_list:
        try:
            make_reel_for(news, day_dir, do_post=args.post)
        except Exception as e:
            print(f"   ! ERRO na materia {news['id']}: {e}")


if __name__ == "__main__":
    main()
