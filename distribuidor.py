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
import unicodedata
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

# Canal do WhatsApp (motor de retencao) — CTA fixo em todo post. Troque via env.
WHATSAPP_CHANNEL = _env("WHATSAPP_CHANNEL_URL",
                        "https://whatsapp.com/channel/0029Vb7wPbRJ93wdnwfzbb2Z")

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


# ---------------------------------------------------------------- filtro editorial
# Temas sensiveis que NAO devem ser postados automaticamente: ficam SEGURADOS p/
# revisao humana (o robo pula e posta a proxima noticia segura). Foco: morte/tragedia,
# menores como vitima, crimes sexuais e suicidio — onde um post automatico no tom
# errado queima a marca ou gera bloqueio na Meta.
_SENSITIVE_DEFAULT = [
    r"mort[eoa]s?", r"falec", r"óbit", r"cadáver", r"v[íi]tima fatal", r"corpo encontrad",
    r"assassin", r"homicíd", r"feminicíd", r"esfaque", r"chacina", r"latrocínio",
    r"suicíd", r"enforcad", r"tirou a própria vida",
    r"estupr", r"abuso sexual", r"pedofil", r"importunç", r"violência sexual",
    r"criança", r"menino", r"menina", r"bebê", r"recém-nascid", r"adolescente",
    r"atropelad", r"afogad", r"queda fatal",
]


def _sensitive_regex():
    """Monta o regex de bloqueio. Voce pode ADICIONAR termos via env SOCIAL_BLOCK_WORDS
    (separados por virgula) sem mexer no codigo."""
    words = list(_SENSITIVE_DEFAULT)
    extra = _env("SOCIAL_BLOCK_WORDS")
    if extra:
        words += [re.escape(w.strip()) for w in extra.split(",") if w.strip()]
    return re.compile(r"\b(" + "|".join(words) + r")", re.IGNORECASE)


_SENSITIVE_RE = _sensitive_regex()


def sensitive_reason(news):
    """Devolve o termo sensivel encontrado (pra segurar a materia) ou None se for segura."""
    blob = f"{news['title'] or ''} {news['summary'] or ''}"
    m = _SENSITIVE_RE.search(blob)
    return m.group(0) if m else None


# ---------------------------------------------------------------- deduplicacao
# Evita postar a MESMA noticia que veio de varias fontes com titulos diferentes
# (ex: o mesmo acidente reportado por 4 portais). Compara por sobreposicao de
# palavras-chave (com stem leve por prefixo).
_DEDUP_STOP = set((
    "de da do das dos a o e os as um uma uns umas no na nos nas ao aos que com por "
    "para pra apos sobre entre ate sem sob desde como mais menos muito pouco urgente "
    "video veja confira saiba assista foto fotos imagem imagens noticia em e é foi sao "
    "ser tem ter um dois tres anos ano hoje agora cidade regiao"
).split())


def _stem_keys(text):
    t = unicodedata.normalize("NFKD", (text or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    keys = set()
    for w in re.findall(r"[a-z0-9]+", t):
        if len(w) < 3 or w in _DEDUP_STOP:
            continue
        keys.add(w[:5])  # stem leve por prefixo (atropelado/atropelamento -> atrop)
    return keys


def _overlap(a, b):
    ka, kb = _stem_keys(a), _stem_keys(b)
    if not ka or not kb:
        return 0.0
    return len(ka & kb) / min(len(ka), len(kb))


def duplicate_of(news, others, thresh=0.55):
    """Se 'news' for o mesmo fato de alguma 'others', devolve o id dela; senao None."""
    base = news["title"] or ""
    for o in others:
        oid = o["id"] if not isinstance(o, dict) else o.get("id")
        if oid == news["id"]:
            continue
        if _overlap(base, (o["title"] if not isinstance(o, dict) else o.get("title")) or "") >= thresh:
            return oid
    return None


def recent_posted(conn, limit=100):
    """Titulos ja postados (p/ comparar e nao repetir o mesmo fato)."""
    return conn.execute(
        "SELECT id, title FROM news "
        "WHERE social_posted_at IS NOT NULL AND social_posted_at!='' "
        "ORDER BY social_posted_at DESC LIMIT ?",
        (limit,),
    ).fetchall()


def mark_dup(conn, news_id, dup_id):
    """Marca como duplicada (reusa social_hold) p/ nao postar nem reavaliar."""
    conn.execute(
        "UPDATE news SET social_hold=? WHERE id=?",
        (f"duplicada de #{dup_id} @ {datetime.now().isoformat(timespec='seconds')}", news_id),
    )
    conn.commit()


def mark_cluster(conn, posted_news, thresh=0.6):
    """BLINDAGEM: apos postar uma materia, marca TODAS as outras nao-postadas do
    MESMO fato (titulo parecido) como duplicadas. Assim nenhum motor (carrossel
    OU reels) posta a mesma noticia de novo, independente de id, timing ou linha
    duplicada no banco. Retorna quantas foram seguradas."""
    pid = posted_news["id"]
    ptitle = posted_news["title"] or ""
    rows = conn.execute(
        "SELECT id, title FROM news WHERE active=1 "
        "AND (social_posted_at IS NULL OR social_posted_at='') "
        "AND (social_hold IS NULL OR social_hold='') AND id != ?",
        (pid,),
    ).fetchall()
    stamp = datetime.now().isoformat(timespec="seconds")
    n = 0
    for r in rows:
        if _overlap(ptitle, r["title"] or "") >= thresh:
            conn.execute("UPDATE news SET social_hold=? WHERE id=?",
                         (f"duplicada de #{pid} @ {stamp}", r["id"]))
            n += 1
    if n:
        conn.commit()
        print(f"   🛡️ cluster: {n} versao(oes) do mesmo fato seguradas")
    return n


# ---------------------------------------------------------------- banco
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(news)")]
    if "social_posted_at" not in cols:
        conn.execute("ALTER TABLE news ADD COLUMN social_posted_at TEXT")
    if "social_hold" not in cols:
        # materia segurada pelo filtro editorial (tema sensivel) — nao posta sozinha
        conn.execute("ALTER TABLE news ADD COLUMN social_hold TEXT")
    # Central do Canal: mensagem pronta + midia + controle de "ja enviei no Canal"
    if "zap_text" not in cols:
        conn.execute("ALTER TABLE news ADD COLUMN zap_text TEXT")
    if "social_media" not in cols:
        conn.execute("ALTER TABLE news ADD COLUMN social_media TEXT")
    if "channel_posted_at" not in cols:
        conn.execute("ALTER TABLE news ADD COLUMN channel_posted_at TEXT")
    # Loop de Insights: guarda o id do post no Instagram p/ puxar metricas depois
    if "ig_media_id" not in cols:
        conn.execute("ALTER TABLE news ADD COLUMN ig_media_id TEXT")
    if "ig_permalink" not in cols:
        conn.execute("ALTER TABLE news ADD COLUMN ig_permalink TEXT")
    conn.commit()


def save_channel_payload(conn, news_id, zap_text, media_url):
    """Guarda a mensagem pronta do WhatsApp + a midia, p/ a Central do Canal."""
    conn.execute(
        "UPDATE news SET zap_text=?, social_media=? WHERE id=?",
        (zap_text, media_url, news_id),
    )
    conn.commit()


def pick_next(conn, only_id=None, limit=1):
    """Proximas materias ainda nao postadas. Prioriza Norte de SC, depois prioridade/data."""
    if only_id:
        return conn.execute("SELECT * FROM news WHERE id=?", (only_id,)).fetchall()

    rows = conn.execute(
        "SELECT * FROM news WHERE active=1 "
        "AND (social_posted_at IS NULL OR social_posted_at='') "
        "AND (social_hold IS NULL OR social_hold='') "
        "ORDER BY priority DESC, datetime(published_at) DESC LIMIT 200"
    ).fetchall()

    local = [r for r in rows if (r["city"] in gi.NORTE_SC)]
    rest = [r for r in rows if r["city"] not in gi.NORTE_SC]
    ordered = local + rest
    return ordered[:limit]


# ---------------------------------------------------------------- urgencia (tempo real)
_URGENT_RE = re.compile(
    r"\b(urgent|acidente|grave|gravíssim|interdi|bloquead|alerta|ao vivo|incêndi|"
    r"incendi|explos|desaparec|temporal|alagament|enchente|capotad|colis|tombament|"
    r"resgat|deslizament|vendaval|ciclone|granizo|apagão|apagao)", re.IGNORECASE)


def is_urgent(news):
    """True se a noticia tem cara de URGENTE/plantao (pra postar na hora)."""
    return bool(_URGENT_RE.search(f"{news['title'] or ''} {news['summary'] or ''}"))


def pick_urgent(conn, minutes=120, limit=5):
    """Noticias URGENTES recem-coletadas (ainda nao postadas), prioriza Norte de SC."""
    rows = conn.execute(
        "SELECT * FROM news WHERE active=1 "
        "AND (social_posted_at IS NULL OR social_posted_at='') "
        "AND (social_hold IS NULL OR social_hold='') "
        "AND created_at > datetime('now', ?) "
        "ORDER BY datetime(published_at) DESC LIMIT 60",
        (f"-{minutes} minutes",),
    ).fetchall()
    urg = [r for r in rows if is_urgent(r)]
    local = [r for r in urg if r["city"] in gi.NORTE_SC]
    rest = [r for r in urg if r["city"] not in gi.NORTE_SC]
    return (local + rest)[:limit]


def mark_posted(conn, news_id):
    conn.execute(
        "UPDATE news SET social_posted_at=? WHERE id=?",
        (datetime.now().isoformat(timespec="seconds"), news_id),
    )
    conn.commit()


def mark_media(conn, news_id, ig_media_id, permalink=None):
    """Guarda o id (e permalink) do post no Instagram — chave pro Loop de Insights."""
    if not ig_media_id:
        return
    conn.execute("UPDATE news SET ig_media_id=?, ig_permalink=? WHERE id=?",
                 (str(ig_media_id), permalink, news_id))
    conn.commit()


def _extract_ig_id(res):
    """Tira o id do post do retorno do publish (carrossel ou reels). None se nao achar."""
    if isinstance(res, dict):
        ig = res.get("instagram")
        if isinstance(ig, dict):
            return ig.get("id")
    return None


def mark_hold(conn, news_id, reason):
    """Segura a materia (filtro editorial): nao entra mais no auto-post, fica p/ revisao."""
    stamp = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "UPDATE news SET social_hold=? WHERE id=?",
        (f"sensivel:{reason} @ {stamp}", news_id),
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
    """Reescreve em ~5 linhas com pegada de rede social. HÍBRIDO: Gemini -> Groq -> local."""
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
        import cerebro
        txt = cerebro.completar(prompt)          # Gemini -> Groq
        if txt:
            return txt.strip('"').strip() or _fallback_summary(news)
    except Exception as e:
        print(f"   ! IA indisponivel ({e}) — usando resumo local")
    return _fallback_summary(news)


# ---------------------------------------------------------------- gancho da capa
def cover_hook(news):
    """Gancho SOBRIO pra CAPA (a capa carrega ~80% do peso). On-brand: jornal de bairro
    serio, NUNCA sensacionalista. Usa cerebro; se indisponivel OU se vier com cara de
    clickbait, devolve None (a capa fica so com a manchete real — comportamento seguro)."""
    title = re.sub(r"\s+", " ", (news["title"] or "")).strip()
    if not title:
        return None
    prompt = (
        "Voce e editor do RadioSC News (Norte de SC). Crie um GANCHO curto pra capa do "
        "post no Instagram da noticia abaixo. REGRAS RIGIDAS: no maximo 5 palavras; "
        "factual e sobrio (jornal de bairro serio); o angulo local de preferencia "
        "(ex: 'O que muda em Schroeder'); PROIBIDO sensacionalismo, clickbait, ponto de "
        "exclamacao e 'voce nao vai acreditar'. Responda SO o gancho, sem aspas.\n\n"
        f"TITULO: {title}"
    )
    try:
        import cerebro
        h = (cerebro.completar(prompt) or "").strip().strip('"').strip()
        h = re.sub(r"\s+", " ", h)
        # guarda-corpo anti-clickbait: descarta exclamacao, longo demais ou vazio.
        if not h or "!" in h or len(h.split()) > 6 or len(h) > 42:
            return None
        return h
    except Exception:
        return None


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

    # AUDIÊNCIA PRÓPRIA: o Canal do WhatsApp é o destino nº1 (terra nossa, à prova de bloqueio do
    # IG). Engajamento in-feed vem primeiro (o algoritmo premia), o Canal logo em seguida em
    # destaque com FOMO, e site/áudio viram um rodapé pequeno.
    bloco_canal = (
        f"🔔 Recebe a notícia ANTES de todo mundo no nosso Canal do WhatsApp:\n"
        f"👉 {WHATSAPP_CHANNEL}\n\n"
        if WHATSAPP_CHANNEL else ""
    )
    return (
        f"{resumo}\n\n"
        f"💬 Concorda? Comenta aqui 👇  ·  🔖 Salva  ·  🔁 Marca um amigo do Vale\n"
        f"➕ Segue @radioscnews — o Norte de SC em 1 minuto\n\n"
        f"{bloco_canal}"
        f"👀 Viu algo na sua cidade? Manda no direct — a próxima notícia pode ser sua.\n"
        f"📍 {city}  ·  🎧 áudio + matéria completa no site (link na bio)\n\n"
        + " ".join(uniq)
    )


# ---------------------------------------------------------------- imagens (reusa gen_instagram)
def generate_images(news, outdir, hook=None):
    """Carrossel ADAPTATIVO. 2026: o ideal sao 8-10 slides (mais swipes = sinal forte),
    mas sem encher linguica: quebra o resumo em pedacos menores (mais slides quando ha
    conteudo) e respeita materia curta (menos slides). cover -> ate 5 de corpo -> CTA."""
    os.makedirs(outdir, exist_ok=True)
    paths = [gi.slide_cover(news, outdir, hook=hook)]
    summary = re.sub(r"\s+", " ", (news["summary"] or "")).strip()
    n = 2
    if summary:
        # ~200 chars/slide (antes 320) -> uma materia decente vira 4-6 slides
        chunks = textwrap.wrap(summary, 200, break_long_words=False)[:5]
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


def _story_image(slide_path, out_path):
    """Converte um slide (1080x1350) num quadro 9:16 (1080x1920) p/ Story."""
    from PIL import Image
    canvas = Image.new("RGB", (1080, 1920), gi.BG)
    im = Image.open(slide_path).convert("RGB")
    if im.width != 1080:
        new_h = int(im.height * 1080 / im.width)
        im = im.resize((1080, new_h))
    if im.height > 1920:
        top = (im.height - 1920) // 2
        im = im.crop((0, top, 1080, top + 1920))
    y = (1920 - im.height) // 2
    canvas.paste(im, (0, max(0, y)))
    canvas.save(out_path, "JPEG", quality=90)
    return out_path


def post_instagram_story(image_url):
    """Publica um Story de imagem no Instagram (some em 24h, mas mantem no topo)."""
    cont = _graph_post(
        f"{GRAPH}/{META_IG_USER_ID}/media",
        {"media_type": "STORIES", "image_url": image_url, "access_token": META_PAGE_TOKEN},
    )["id"]
    time.sleep(2)
    return _graph_post(
        f"{GRAPH}/{META_IG_USER_ID}/media_publish",
        {"creation_id": cont, "access_token": META_PAGE_TOKEN},
    )


def post_instagram_carousel(public_urls, caption, location_id=None):
    """Posta carrossel no Instagram. ATENCAO: IG exige image_url PUBLICA (https) em JPG.
    location_id (opcional): geotag da cidade (sinal forte de busca hiperlocal)."""
    children = []
    for u in public_urls:
        res = _graph_post(
            f"{GRAPH}/{META_IG_USER_ID}/media",
            {"image_url": u, "is_carousel_item": "true", "access_token": META_PAGE_TOKEN},
        )
        children.append(res["id"])
        time.sleep(2)

    cont_data = {"media_type": "CAROUSEL", "children": ",".join(children),
                 "caption": caption, "access_token": META_PAGE_TOKEN}
    if location_id:
        cont_data["location_id"] = location_id
    container = _graph_post(f"{GRAPH}/{META_IG_USER_ID}/media", cont_data)["id"]
    time.sleep(3)

    return _graph_post(
        f"{GRAPH}/{META_IG_USER_ID}/media_publish",
        {"creation_id": container, "access_token": META_PAGE_TOKEN},
    )


def publish_images(prefix, image_paths, caption, location_id=None):
    """Copia imagens p/ static/social (servidas publicamente) e posta carrossel IG + foto FB.
    Generico: serve tanto p/ noticia quanto p/ Bom dia Vale.
    location_id (opcional): geotag da cidade no carrossel."""
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
    ig = post_instagram_carousel(public_urls, caption, location_id=location_id)
    if location_id:
        print(f"     📍 geotag: {location_id}")
    print(f"     IG ok: {ig}")
    print("   > publicando no Facebook...")
    fb = post_facebook(public_urls[0], caption)
    print(f"     FB ok: {fb}")

    # Story automatico (capa em 9:16) — desligue com SOCIAL_STORY=0
    story = None
    if _env("SOCIAL_STORY", "1") == "1":
        try:
            story_jpg = os.path.join(PUBLIC_IMG_DIR, f"{prefix}_story.jpg")
            _story_image(image_paths[0], story_jpg)
            story_url = f"{PUBLIC_BASE_URL}/static/social/{prefix}_story.jpg"
            story = post_instagram_story(story_url)
            print(f"     Story ok: {story}")
        except Exception as e:
            print(f"     ! Story falhou (segue mesmo assim): {e}")
    return {"instagram": ig, "facebook": fb, "story": story}


def publish_real(news, image_paths, caption):
    """Posta uma NOTICIA (carrossel) no IG + FB, com geotag da cidade quando resolvivel."""
    loc = None
    try:
        import geo
        loc = geo.location_id(news["city"])
    except Exception:
        loc = None
    return publish_images(f"n{news['id']}", image_paths, caption, location_id=loc)


# ---------------------------------------------------------------- ponto de entrada p/ scheduler
def post_specific(news_id):
    """Posta UMA materia especifica (usado pela Fila de Revisao ao aprovar).
    Ignora filtro/hold (decisao humana). Marca como postada no sucesso."""
    conn = get_db()
    ensure_column(conn)
    rows = pick_next(conn, only_id=news_id)
    if not rows:
        conn.close()
        return {"ok": False, "erro": "materia nao encontrada"}
    news = rows[0]
    day_dir = os.path.join(PREVIEW_BASE, datetime.now().strftime("%Y-%m-%d") + "_revisao")
    os.makedirs(day_dir, exist_ok=True)
    try:
        process_one(conn, news, True, day_dir)  # posta + marca + salva payload do Canal
        conn.close()
        return {"ok": True}
    except Exception as e:
        conn.close()
        return {"ok": False, "erro": str(e)}


def run_urgent(post=True, limit=1):
    """Posta NA HORA noticias urgentes recem-coletadas (plantao). Mesmo filtro
    editorial + dedup. Sensiveis vao p/ revisao marcadas como URGENTE."""
    conn = get_db()
    ensure_column(conn)
    pool = pick_urgent(conn)
    if not pool:
        conn.close()
        return {"postadas": 0, "erros": [], "seguradas": []}
    day_dir = os.path.join(PREVIEW_BASE, datetime.now().strftime("%Y-%m-%d") + "_urgente")
    os.makedirs(day_dir, exist_ok=True)
    vistos = list(recent_posted(conn))
    done, erros, seguradas = 0, [], []
    for news in pool:
        if done >= limit:
            break
        reason = sensitive_reason(news)
        if reason:
            mark_hold(conn, news["id"], f"sensivel:{reason} (URGENTE — revise rapido)")
            seguradas.append(f"materia {news['id']} URGENTE+sensivel -> revisao ('{reason}')")
            vistos.append(news)
            continue
        dup = duplicate_of(news, vistos)
        if dup:
            mark_dup(conn, news["id"], dup)
            vistos.append(news)
            continue
        try:
            process_one(conn, news, post, day_dir)
            vistos.append(news)
            done += 1
        except Exception as e:
            erros.append(f"materia {news['id']}: {e}")
    conn.close()
    return {"postadas": done, "erros": erros, "seguradas": seguradas}


def run_once(post=False, limit=1):
    """Chamado pelo scheduler. Prepara (e opcionalmente posta) as proximas materias.
    FILTRO EDITORIAL: ao postar de verdade, materias com tema sensivel sao SEGURADAS
    p/ revisao humana (o robo pula e segue p/ a proxima noticia segura).
    Retorna {postadas, erros, seguradas}."""
    conn = get_db()
    ensure_column(conn)
    # pega um lote maior que o limite p/ ter de onde pular as seguradas
    pool = pick_next(conn, only_id=None, limit=max(limit * 6, 12))
    if not pool:
        conn.close()
        print("[distribuidor] nada pendente.")
        return {"postadas": 0, "erros": ["nada pendente"], "seguradas": []}
    day_dir = os.path.join(PREVIEW_BASE, datetime.now().strftime("%Y-%m-%d") + "_social")
    os.makedirs(day_dir, exist_ok=True)
    done, erros, seguradas = 0, [], []
    # base de comparacao p/ dedup: ja postadas + tudo que for visto neste lote
    vistos = list(recent_posted(conn)) if post else []
    for news in pool:
        if done >= limit:
            break
        # so filtra quando vai POSTAR de verdade
        if post:
            # 1) filtro editorial (tema sensivel)
            reason = sensitive_reason(news)
            if reason:
                mark_hold(conn, news["id"], reason)
                aviso = f"materia {news['id']} SEGURADA p/ revisao (tema sensivel: '{reason}')"
                print("   ⏸ " + aviso)
                seguradas.append(aviso)
                vistos.append(news)
                continue
            # 2) deduplicacao (mesmo fato de outra fonte)
            dup = duplicate_of(news, vistos)
            if dup:
                mark_dup(conn, news["id"], dup)
                aviso = f"materia {news['id']} PULADA (duplicada do mesmo fato da #{dup})"
                print("   ♻ " + aviso)
                seguradas.append(aviso)
                vistos.append(news)
                continue
        try:
            process_one(conn, news, post, day_dir)
            if post:
                vistos.append(news)
            done += 1
        except Exception as e:
            msg = f"materia {news['id']}: {e}"
            print("   ! ERRO " + msg)
            erros.append(msg)
    conn.close()
    return {"postadas": done, "erros": erros, "seguradas": seguradas}


# ---------------------------------------------------------------- main
def process_one(conn, news, do_post, day_dir):
    nid = news["id"]
    print(f"\n=== [{nid}] {news['city']} | {news['title'][:60]} ===")

    resumo = groq_summary(news)
    caption = social_caption(news, resumo)
    zap = whatsapp_message(news, resumo)
    hook = cover_hook(news)  # gancho sobrio da capa (None se IA off/suspeito)

    outdir = os.path.join(day_dir, str(nid))
    imgs = generate_images(news, outdir, hook=hook)
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
        res = publish_real(news, imgs, caption)
        mark_posted(conn, nid)
        mark_cluster(conn, news)  # blindagem: segura todas as irmas do mesmo fato
        # Loop de Insights: salva o id do post no IG (p/ puxar alcance/saves depois)
        try:
            mark_media(conn, nid, _extract_ig_id(res))
        except Exception:
            pass
        # guarda a mensagem pronta do WhatsApp + 1a imagem p/ a Central do Canal
        media_url = f"{PUBLIC_BASE_URL}/static/social/n{nid}_s1.jpg"
        save_channel_payload(conn, nid, zap, media_url)
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
