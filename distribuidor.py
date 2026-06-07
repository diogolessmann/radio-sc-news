# -*- coding: utf-8 -*-
"""
distribuidor.py — Bot distribuidor de noticias para redes sociais
Radio SC News

FLUXO:
  1. pega a proxima materia ainda nao postada (prioriza Norte de SC)
  2. resume em ~5 linhas com pegada (Groq se houver GROQ_API_KEY; senao fallback local)
  3. gera o carrossel reaproveitando gen_instagram.py
  4. monta a legenda social (gancho + resumo + CTA + hashtags)
  5. dry-run: salva preview e MOSTRA o que postaria, SEM publicar
     --post : publica no Instagram + Facebook via Meta Graph (Fase 1)
  6. marca a materia como postada (coluna social_posted_at) — so quando posta de verdade

USO:
  venv\\Scripts\\python.exe distribuidor.py            # dry-run (NAO posta) — so mostra
  venv\\Scripts\\python.exe distribuidor.py --id 290   # materia especifica (dry-run)
  venv\\Scripts\\python.exe distribuidor.py --limit 3  # prepara as 3 proximas (dry-run)
  venv\\Scripts\\python.exe distribuidor.py --post     # publica de verdade (precisa tokens Meta)

VARIAVEIS DE AMBIENTE (Fase 1 — postagem real):
  GROQ_API_KEY            chave Groq (resumo IA). Sem ela, usa fallback local.
  GROQ_MODEL             (opcional) default llama-3.3-70b-versatile
  META_PAGE_TOKEN         token de pagina de longa duracao (Facebook)
  META_IG_USER_ID         ID da conta Instagram Business
  META_PAGE_ID            ID da Pagina do Facebook
  PUBLIC_BASE_URL         URL publica do site (ex: https://www.radioscnews.com.br)
                          — o Instagram exige image_url PUBLICA; as imagens vao p/ static/social/
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import textwrap
import time
from datetime import datetime

import requests

# Console do Windows nao aceita emoji por padrao (cp1252) — forca UTF-8 na saida.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Reaproveita TODO o gerador de imagem que ja existe e funciona
import gen_instagram as gi

# ---------------------------------------------------------------- config
def _env(name, default=""):
    """Le variavel de ambiente TOLERANDO espacos acidentais no nome ou no valor
    (comum ao colar no painel do Railway). Devolve o valor ja sem espacos nas pontas."""
    v = os.environ.get(name)
    if not v:
        target = name.strip()
        for k, val in os.environ.items():
            if k.strip() == target and val:
                v = val
                break
    if v is None:
        return default
    v = v.strip()
    return v if v else default


DB_PATH = os.environ.get("DB_PATH", "radio_sc.db")
SITE = gi.SITE
PUBLIC_BASE_URL = _env("PUBLIC_BASE_URL", "https://www.radioscnews.com.br").rstrip("/")

GROQ_API_KEY = _env("GROQ_API_KEY")
GROQ_MODEL = _env("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Meta (Fase 1) — _env tolera espaco invisivel no nome da variavel
META_PAGE_TOKEN = _env("META_PAGE_TOKEN")
META_IG_USER_ID = _env("META_IG_USER_ID")
META_PAGE_ID = _env("META_PAGE_ID")
GRAPH = "https://graph.facebook.com/v21.0"

PREVIEW_BASE = "instagram_posts"          # dry-run salva aqui (mesma pasta do gen_instagram)
PUBLIC_IMG_DIR = os.path.join("static", "social")  # postagem real serve as imagens daqui


# ---------------------------------------------------------------- banco
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(news)")]
    if "social_posted_at" not in cols:
        conn.execute("ALTER TABLE news ADD COLUMN social_posted_at TEXT")
        conn.commit()


def pick_next(conn, only_id=None, limit=1):
    """Proximas materias ainda nao postadas. Prioriza Norte de SC, depois prioridade/data."""
    if only_id:
        return conn.execute("SELECT * FROM news WHERE id=?", (only_id,)).fetchall()

    rows = conn.execute(
        "SELECT * FROM news WHERE active=1 "
        "AND (social_posted_at IS NULL OR social_posted_at='') "
        "ORDER BY priority DESC, datetime(published_at) DESC LIMIT 200"
    ).fetchall()

    local = [r for r in rows if (r["city"] in gi.NORTE_SC)]
    rest = [r for r in rows if r["city"] not in gi.NORTE_SC]
    ordered = local + rest
    return ordered[:limit]


def mark_posted(conn, news_id):
    conn.execute(
        "UPDATE news SET social_posted_at=? WHERE id=?",
        (datetime.now().isoformat(timespec="seconds"), news_id),
    )
    conn.commit()


# ---------------------------------------------------------------- resumo (Groq + fallback)
def _fallback_summary(news):
    """Sem Groq: monta um resumo local — gancho do titulo + primeiras frases."""
    title = re.sub(r"\s+", " ", (news["title"] or "")).strip().rstrip(".")
    body = re.sub(r"\s+", " ", (news["summary"] or "")).strip()
    frases = re.split(r"(?<=[.!?])\s+", body)
    resumo = " ".join(frases[:3])[:300].strip()
    hook = f"🚨 {title}" if (news["category"] or "") in ("policial", "clima") else f"📰 {title}"
    if resumo:
        return f"{hook}\n\n{resumo}"
    return hook


def groq_summary(news):
    """Resume a materia em ~5 linhas com pegada de rede social. Usa Groq se houver chave."""
    if not GROQ_API_KEY:
        return _fallback_summary(news)

    title = re.sub(r"\s+", " ", (news["title"] or "")).strip()
    body = re.sub(r"\s+", " ", (news["summary"] or "")).strip()
    prompt = (
        "Voce e o editor do RadioSC News, portal de noticias do Vale do Itapocu "
        "(Norte de SC: Schroeder, Jaragua do Sul, Guaramirim, Corupa). Sua VOZ e a de "
        "um vizinho bem informado: humano, direto e acolhedor, com leve simpatia "
        "regional — nunca robotico, nunca sensacionalista barato. "
        "Reescreva a noticia abaixo como legenda de Instagram em portugues do Brasil. "
        "Regras: a PRIMEIRA linha e um gancho curto que faca a pessoa parar de rolar "
        "(no maximo 1 emoji). Depois, 3 a 4 linhas curtas com o fato. No maximo 5 "
        "linhas no total. Nao invente nada alem do texto fornecido. NAO use hashtags "
        "nem 'clique aqui'. Seja direto e com personalidade.\n\n"
        f"TITULO: {title}\nTEXTO: {body}"
    )
    try:
        r = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                     "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
                "max_tokens": 320,
            },
            timeout=30,
        )
        r.raise_for_status()
        txt = r.json()["choices"][0]["message"]["content"].strip()
        # limpa aspas/explicacoes acidentais
        txt = txt.strip('"').strip()
        return txt or _fallback_summary(news)
    except Exception as e:
        print(f"   ! Groq indisponivel ({e}) — usando resumo local")
        return _fallback_summary(news)


# ---------------------------------------------------------------- links
def news_permalink(news):
    """Link compartilhavel da materia no proprio site (rota /noticia/<id> com OpenGraph)."""
    return f"{PUBLIC_BASE_URL}/noticia/{news['id']}"


# ---------------------------------------------------------------- WhatsApp Canal
def _short_resumo(resumo, max_chars=240):
    """Versao curta do resumo pro WhatsApp: tira a 1a linha (gancho) e enxuga."""
    linhas = [l for l in resumo.splitlines() if l.strip()]
    corpo = " ".join(linhas[1:]) if len(linhas) > 1 else (linhas[0] if linhas else "")
    corpo = re.sub(r"\s+", " ", corpo).strip()
    if len(corpo) > max_chars:
        corpo = corpo[:max_chars].rsplit(" ", 1)[0] + "..."
    return corpo


def whatsapp_message(news, resumo):
    """Mensagem pronta pro WhatsApp Canal (curta, com *negrito*, emoji e link que abre card)."""
    title = re.sub(r"\s+", " ", (news["title"] or "")).strip().rstrip(".")
    city = news["city"] or "Santa Catarina"
    corpo = _short_resumo(resumo)
    selo = "🚨" if (news["category"] or "") in ("policial", "clima") else "📰"
    partes = [f"{selo} *{title}*", ""]
    if corpo:
        partes += [corpo, ""]
    partes += [
        f"📍 {city}",
        f"🔊 Leia e ouça a notícia completa:",
        news_permalink(news),
    ]
    return "\n".join(partes)


# ---------------------------------------------------------------- legenda social
def social_caption(news, resumo):
    city = news["city"] or "Santa Catarina"
    tags = []
    tags += gi.CITY_TAGS.get(city, [])
    tags += gi.CAT_TAGS.get(news["category"] or "", [])
    tags += gi.BASE_TAGS
    seen, uniq = set(), []
    for t in tags:
        if t not in seen:
            seen.add(t)
            uniq.append(t)

    return (
        f"{resumo}\n\n"
        f"📲 Leia a materia completa e OUCA em audio no site (link na bio)\n"
        f"📍 {city}  ·  🔗 {SITE}\n\n"
        f"👀 Viu algo na sua cidade? Manda no nosso direct ou WhatsApp — a proxima "
        f"noticia pode ser sua.\n"
        f"Siga @radioscnews — tudo do Norte de SC em 1 minuto.\n\n"
        + " ".join(uniq)
    )


# ---------------------------------------------------------------- imagens (reusa gen_instagram)
def generate_images(news, outdir):
    os.makedirs(outdir, exist_ok=True)
    paths = [gi.slide_cover(news, outdir)]
    summary = re.sub(r"\s+", " ", (news["summary"] or "")).strip()
    n = 2
    if summary:
        chunks = textwrap.wrap(summary, 320, break_long_words=False)[:2]
        for i, ch in enumerate(chunks, 1):
            paths.append(gi.slide_text(ch, i, len(chunks), outdir, n))
            n += 1
    paths.append(gi.slide_cta(news, outdir, n))
    return paths


# ---------------------------------------------------------------- postagem Meta (Fase 1)
def _meta_ready():
    return bool(META_PAGE_TOKEN and META_IG_USER_ID and META_PAGE_ID)


def _graph_post(url, data, tries=2):
    """POST na Graph API mostrando o ERRO DETALHADO da Meta (nao so o status)."""
    last = ""
    for _ in range(tries):
        r = requests.post(url, data=data, timeout=60)
        if r.ok:
            return r.json()
        last = r.text[:400]
        # erro de imagem ainda processando -> espera e tenta de novo
        if r.status_code in (400, 500) and ("media" in last.lower() or "process" in last.lower()):
            time.sleep(4)
            continue
        break
    raise RuntimeError(f"Graph {url.rsplit('/', 1)[-1]} -> {last}")


def post_facebook(image_path_public_url, caption):
    """Posta UMA foto na Pagina do Facebook (FB aceita upload direto OU url)."""
    return _graph_post(f"{GRAPH}/{META_PAGE_ID}/photos",
                       {"caption": caption, "url": image_path_public_url,
                        "access_token": META_PAGE_TOKEN})


def post_instagram_carousel(public_urls, caption):
    """Posta carrossel no Instagram. ATENCAO: IG exige image_url PUBLICA (https) em JPG."""
    children = []
    for u in public_urls:
        res = _graph_post(
            f"{GRAPH}/{META_IG_USER_ID}/media",
            {"image_url": u, "is_carousel_item": "true", "access_token": META_PAGE_TOKEN},
        )
        children.append(res["id"])
        time.sleep(2)

    container = _graph_post(
        f"{GRAPH}/{META_IG_USER_ID}/media",
        {"media_type": "CAROUSEL", "children": ",".join(children),
         "caption": caption, "access_token": META_PAGE_TOKEN},
    )["id"]
    time.sleep(3)

    return _graph_post(
        f"{GRAPH}/{META_IG_USER_ID}/media_publish",
        {"creation_id": container, "access_token": META_PAGE_TOKEN},
    )


def publish_images(prefix, image_paths, caption):
    """Copia imagens p/ static/social (servidas publicamente) e posta carrossel IG + foto FB.
    Generico: serve tanto p/ noticia quanto p/ Bom dia Vale."""
    if not _meta_ready():
        raise RuntimeError(
            "Tokens Meta ausentes. Configure META_PAGE_TOKEN, META_IG_USER_ID e "
            "META_PAGE_ID no ambiente (Railway) antes de postar."
        )
    from PIL import Image
    os.makedirs(PUBLIC_IMG_DIR, exist_ok=True)
    public_urls = []
    for i, p in enumerate(image_paths, 1):
        # Instagram exige JPG (nao aceita PNG) -> converte
        fname = f"{prefix}_s{i}.jpg"
        dest = os.path.join(PUBLIC_IMG_DIR, fname)
        Image.open(p).convert("RGB").save(dest, "JPEG", quality=90)
        public_urls.append(f"{PUBLIC_BASE_URL}/static/social/{fname}")

    print("   > publicando no Instagram...")
    ig = post_instagram_carousel(public_urls, caption)
    print(f"     IG ok: {ig}")
    print("   > publicando no Facebook...")
    fb = post_facebook(public_urls[0], caption)
    print(f"     FB ok: {fb}")
    return {"instagram": ig, "facebook": fb}


def publish_real(news, image_paths, caption):
    """Posta uma NOTICIA (carrossel) no IG + FB."""
    return publish_images(f"n{news['id']}", image_paths, caption)


# ---------------------------------------------------------------- ponto de entrada p/ scheduler
def run_once(post=False, limit=1):
    """Chamado pelo scheduler. Prepara (e opcionalmente posta) as proximas materias.
    Retorna quantas foram processadas."""
    conn = get_db()
    ensure_column(conn)
    news_list = pick_next(conn, only_id=None, limit=limit)
    if not news_list:
        conn.close()
        print("[distribuidor] nada pendente.")
        return {"postadas": 0, "erros": ["nada pendente"]}
    day_dir = os.path.join(PREVIEW_BASE, datetime.now().strftime("%Y-%m-%d") + "_social")
    os.makedirs(day_dir, exist_ok=True)
    done, erros = 0, []
    for news in news_list:
        try:
            process_one(conn, news, post, day_dir)
            done += 1
        except Exception as e:
            msg = f"materia {news['id']}: {e}"
            print("   ! ERRO " + msg)
            erros.append(msg)
    conn.close()
    return {"postadas": done, "erros": erros}


# ---------------------------------------------------------------- main
def process_one(conn, news, do_post, day_dir):
    nid = news["id"]
    print(f"\n=== [{nid}] {news['city']} | {news['title'][:60]} ===")

    resumo = groq_summary(news)
    caption = social_caption(news, resumo)
    zap = whatsapp_message(news, resumo)

    outdir = os.path.join(day_dir, str(nid))
    imgs = generate_images(news, outdir)
    print(f"   {len(imgs)} imagens geradas em {outdir}")

    # salva previews (Instagram/Facebook + WhatsApp Canal)
    with open(os.path.join(outdir, "legenda_social.txt"), "w", encoding="utf-8") as f:
        f.write(caption)
    with open(os.path.join(outdir, "whatsapp.txt"), "w", encoding="utf-8") as f:
        f.write(zap)

    print("   ----- LEGENDA INSTAGRAM/FACEBOOK -----")
    for ln in caption.splitlines():
        print("   | " + ln)
    print("   ----- WHATSAPP CANAL (pronto p/ colar) -----")
    for ln in zap.splitlines():
        print("   > " + ln)
    print("   --------------------------------------------")
    print(f"   Resumo via: {'GROQ (voz RadioSC)' if GROQ_API_KEY else 'FALLBACK LOCAL (sem chave Groq)'}")

    if do_post:
        publish_real(news, imgs, caption)
        mark_posted(conn, nid)
        print(f"   ✔ POSTADO e marcado (social_posted_at) — id {nid}")
    else:
        print("   (dry-run) NADA foi publicado e a materia NAO foi marcada.")


def main():
    ap = argparse.ArgumentParser(description="Bot distribuidor RadioSC News")
    ap.add_argument("--id", type=int, default=None, help="materia especifica")
    ap.add_argument("--limit", type=int, default=1, help="quantas preparar")
    ap.add_argument("--post", action="store_true", help="PUBLICA de verdade (precisa tokens Meta)")
    args = ap.parse_args()

    conn = get_db()
    ensure_column(conn)

    news_list = pick_next(conn, only_id=args.id, limit=args.limit)
    if not news_list:
        print("Nenhuma materia pendente para postar. 🎉")
        return

    day_dir = os.path.join(PREVIEW_BASE, datetime.now().strftime("%Y-%m-%d") + "_social")
    os.makedirs(day_dir, exist_ok=True)

    modo = "POSTAGEM REAL" if args.post else "DRY-RUN (so mostra, nao posta)"
    print(f"Modo: {modo}  |  Materias: {len(news_list)}  |  Meta pronto: {_meta_ready()}")

    for news in news_list:
        try:
            process_one(conn, news, args.post, day_dir)
        except Exception as e:
            print(f"   ! ERRO na materia {news['id']}: {e}")

    conn.close()
    print(f"\nPronto. Previews em: {os.path.abspath(day_dir)}")


if __name__ == "__main__":
    main()
