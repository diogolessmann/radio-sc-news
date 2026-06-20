"""
scraper.py — Coleta automática de notícias via RSS
Rádio SC News
"""
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import sqlite3
import logging
import re
import os
import unicodedata
import warnings

# Alguns portais servem HTML com declaração <?xml ...?> no topo -> bs4 avisa. Silencia o ruído.
try:
    from bs4 import XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
except Exception:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = os.environ.get('DB_PATH', 'radio_sc.db')

RSS_FEEDS = [
    # ── Santa Catarina (geral) ──────────────────
    {
        'url': 'https://g1.globo.com/rss/g1/sc/',
        'source': 'G1 Santa Catarina',
        'city': None,          # Usa detecção por keyword — pode ser qualquer cidade de SC
        'category': 'geral',
        'priority': True
    },
    {
        'url': 'https://ndmais.com.br/feed/',
        'source': 'ND Mais',
        'city': None,          # Detecção automática de cidade
        'category': 'geral',
        'priority': False
    },
    # ── Norte de SC — Joinville ─────────────────
    {
        'url': 'https://ndmais.com.br/joinville/feed/',
        'source': 'ND Mais – Joinville',
        'city': 'Joinville',
        'category': 'geral',
        'priority': True
    },
    {
        'url': 'https://g1.globo.com/rss/g1/sc/norte-catarinense/',
        'source': 'G1 Norte Catarinense',
        'city': None,          # Norte de SC — keyword decide a cidade exata
        'category': 'geral',
        'priority': True
    },
    {
        'url': 'https://ocp.news/tag/joinville/feed/',
        'source': 'OCP News – Joinville',
        'city': 'Joinville',
        'category': 'geral',
        'priority': True
    },
    # ── Norte de SC — Jaraguá do Sul ────────────
    {
        'url': 'https://ndmais.com.br/tag/jaragua-do-sul/feed/',
        'source': 'ND Mais – Jaraguá do Sul',
        'city': 'Jaraguá do Sul',
        'category': 'geral',
        'priority': True
    },
    {
        'url': 'https://ocp.news/tag/jaragua-do-sul/feed/',
        'source': 'OCP News – Jaraguá do Sul',
        'city': 'Jaraguá do Sul',
        'category': 'geral',
        'priority': True
    },
    # ── Norte de SC — Jaraguá do Sul + Guaramirim (RBN 94.3 FM) ──
    {
        'url': 'https://portal.rbnfm.com.br/feed',
        'source': 'RBN 94.3 FM',
        'city': None,          # Cobre Jaraguá e Guaramirim — keyword detecta
        'category': 'geral',
        'priority': True,
        'max_entries': 15
    },
    # ── Norte de SC — Guaramirim ────────────────
    {
        'url': 'https://ocp.news/tag/guaramirim/feed/',
        'source': 'OCP News – Guaramirim',
        'city': 'Guaramirim',
        'category': 'geral',
        'priority': True
    },
    {
        'url': 'https://ndmais.com.br/tag/guaramirim/feed/',
        'source': 'ND Mais – Guaramirim',
        'city': 'Guaramirim',
        'category': 'geral',
        'priority': True
    },
    # ── Norte de SC — Schroeder, Guaramirim, Corupá (JDV) ──
    {
        'url': 'https://www.jdv.com.br/feed/',
        'source': 'JDV',
        'city': None,          # JDV cobre Schroeder/Guaramirim/Corupá — keyword detecta
        'category': 'geral',
        'priority': True
    },
    # ── Norte de SC — Schroeder (SchPost) ───────
    {
        'url': 'https://www.schpost.com.br/feed/',
        'source': 'Portal de Schroeder',
        'city': 'Schroeder',
        'category': 'local',
        'priority': True
    },
    {
        'url': 'https://ndmais.com.br/tag/schroeder/feed/',
        'source': 'ND Mais – Schroeder',
        'city': 'Schroeder',
        'category': 'geral',
        'priority': True
    },
    # ── Norte de SC — OCP News (regional) ───────
    {
        'url': 'https://ocp.news/feed/',
        'source': 'OCP News',
        'city': None,
        'category': 'geral',
        'priority': False
    },
    # ── Futebol Nacional (limitado a 5 por feed) ─
    {
        'url': 'https://ge.globo.com/rss/ge/futebol/',
        'source': 'GE Futebol',
        'city': 'Brasil',
        'category': 'esporte',
        'priority': True,
        'max_entries': 5
    },
    {
        'url': 'https://ge.globo.com/rss/ge/brasileirao-serie-a/',
        'source': 'GE Brasileirão',
        'city': 'Brasil',
        'category': 'esporte',
        'priority': True,
        'max_entries': 5
    },
    {
        'url': 'https://www.gazetaesportiva.com/feed/',
        'source': 'Gazeta Esportiva',
        'city': 'Brasil',
        'category': 'esporte',
        'priority': False,
        'max_entries': 3
    },
    {
        'url': 'https://lance.com.br/feed/',
        'source': 'Lance!',
        'city': 'Brasil',
        'category': 'esporte',
        'priority': False,
        'max_entries': 3
    },
]

# Ordem importa: cidades mais específicas ANTES de genéricas
CITY_KEYWORDS = {
    'Schroeder':     ['schroeder', 'schroder'],
    'Guaramirim':    ['guaramirim'],
    'Corupá':        ['corupá', 'corupa'],
    'Joinville':     ['joinville', 'joinvilense', 'joinvilhense'],
    'Jaraguá do Sul':['jaraguá do sul', 'jaragua do sul', 'jaraguaense', 'jaraguá', 'hospital são josé', 'hospital jaraguá', 'br-280 jaraguá'],
    'Blumenau':      ['blumenau', 'blumenauense'],
    'Florianópolis': ['florianópolis', 'floripa', 'florianopolitano'],
    'Norte de SC':   ['norte catarinense', 'norte de santa catarina', 'região norte'],
    'Santa Catarina':['santa catarina', 'catarinense'],
}

# Cidades que pertencem ao Norte de SC (para o filtro de região)
NORTE_SC_CITIES = {'Schroeder', 'Joinville', 'Jaraguá do Sul', 'Guaramirim', 'Corupá', 'Norte de SC'}

CATEGORY_KEYWORDS = {
    'policial': ['crime', 'assalto', 'homicídio', 'acidente', 'preso', 'policial', 'pm', 'delegacia', 'roubo', 'furto', 'morte', 'óbito', 'batida', 'colisão'],
    'politica': ['prefeitura', 'câmara', 'vereador', 'prefeito', 'eleição', 'governo', 'governador', 'deputado', 'política'],
    'saude': ['hospital', 'saúde', 'dengue', 'vacina', 'ubs', 'médico', 'doença', 'covid', 'pandemia'],
    'esporte': ['futebol', 'esporte', 'atleta', 'campeonato', 'jogo', 'gol', 'time', 'torneio', 'libertadores', 'brasileirão', 'brasileirao', 'escalações', 'escalacao', 'rodada', 'tabela do campeonato', 'série a', 'serie a', 'copa do brasil', 'flamengo', 'corinthians', 'palmeiras', 'são paulo', 'grêmio', 'internacional', 'cruzeiro', 'atlético'],
    'economia': ['emprego', 'empresa', 'mercado', 'economia', 'negócio', 'indústria', 'comércio', 'renda'],
    'clima': ['chuva', 'temporal', 'vento', 'frio', 'calor', 'enchente', 'clima', 'previsão do tempo'],
    'cultura': ['evento', 'festa', 'show', 'cultura', 'música', 'teatro', 'exposição', 'festival'],
}


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)   # espera o banco destravar em vez de estourar
    conn.row_factory = sqlite3.Row
    return conn


# ── Deduplicação por CONTEÚDO (mesmo fato vindo de várias fontes) ──
_DEDUP_STOP = set((
    "de da do das dos a o e os as um uma uns umas no na nos nas ao aos que com por "
    "para pra apos sobre entre ate sem sob desde como mais menos muito pouco urgente "
    "video veja confira saiba assista foto fotos imagem imagens noticia em e foi sao "
    "ser tem ter dois tres anos ano hoje agora cidade regiao apos"
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


def _is_similar(title, titles, thresh=0.6):
    """True se 'title' for o mesmo fato de algum título já visto."""
    for t in titles:
        if _overlap(title, t) >= thresh:
            return True
    return False


def detect_city(text):
    text_lower = text.lower()
    for city, keywords in CITY_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return city
    return 'Santa Catarina'


def detect_category(text):
    """Categoria por PALAVRA INTEIRA (\\b) — evita 'preso' casar dentro de 'Caropreso' (sobrenome)
    e marcar política/saúde como POLICIAL. Escolhe a categoria com MAIS acertos (não a 1ª que casa)."""
    text_lower = text.lower()
    best, best_score = 'geral', 0
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords
                    if re.search(r'\b' + re.escape(kw) + r'\b', text_lower))
        if score > best_score:
            best, best_score = category, score
    return best


def clean_html(text):
    if not text:
        return ''
    soup = BeautifulSoup(text, 'lxml')
    return soup.get_text(separator=' ').strip()


# Cabeçalhos de navegador real — portais regionais (ex: SchPost) devolvem 403 p/ UA de bot.
# Accept-Language pt-BR + Referer do Google + Upgrade-Insecure-Requests passam pelo bloqueio.
_BROWSER_HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9',
    'Referer': 'https://www.google.com/',
    'Upgrade-Insecure-Requests': '1',
    'Connection': 'keep-alive',
}


# ── Fontes cujas IMAGENS NÃO usamos (litigiosas: OCP e Portal de Schroeder/Gabriel). Mantemos o
#    TEXTO (o fato é livre; a gente reescreve). G1 fica liberado. Edite via env IMG_BLOCK_DOMAINS.
_IMG_BLOCK = [d.strip().lower() for d in
              os.environ.get("IMG_BLOCK_DOMAINS", "ocp.news,schpost.com.br").split(",") if d.strip()]


def _image_blocked(link, source=""):
    """True se a notícia vem de fonte com imagem bloqueada (não usar a foto, só o texto)."""
    blob = f"{link or ''} {source or ''}".lower()
    return any(d and d in blob for d in _IMG_BLOCK)


def fetch_og_image(link):
    """Foto da PÁGINA da matéria (og:image / twitter:image). Resolve o buraco dos feeds
    locais que não trazem foto no RSS mas têm na página. Devolve URL ou None.
    É a foto do PRÓPRIO portal da notícia que estamos reportando (uso jornalístico)."""
    if not link or not link.startswith(('http://', 'https://')):
        return None
    try:
        r = requests.get(link, headers=_BROWSER_HEADERS, timeout=8, verify=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, 'lxml')
        for attrs in ({'property': 'og:image'}, {'property': 'og:image:url'},
                      {'name': 'twitter:image'}, {'name': 'twitter:image:src'}):
            tag = soup.find('meta', attrs=attrs)
            if tag and tag.get('content', '').strip().startswith(('http://', 'https://')):
                return tag['content'].strip()
    except Exception as e:
        logger.info(f"og:image falhou ({link[:50]}): {e}")
    return None


_TEXT_LIXO = re.compile(
    r"leia (mais|tamb[eé]m)|compartilh|publicidade|continua ap[oó]s|aceit[ae].*cookies|"
    r"(siga|participe|receba).*(instagram|whatsapp|telegram|grupo|not[ií]cias)|"
    r"fale conosco|grupo no whatsapp|todos os direitos|clique aqui|"
    r"\bfoto:|\bfonte:|inscreva-se|newsletter", re.IGNORECASE)


def fetch_article_text(link, min_total=180, max_total=1400):
    """Puxa o CORPO da matéria da página, p/ encher o carrossel quando o RSS vem sem resumo
    (15% das notícias). Funciona com texto em <p> OU solto dentro do <article>: usa
    stripped_strings (cada fragmento de texto), filtra boilerplate (leia mais, WhatsApp,
    cookies) e junta. Devolve texto corrido ou None (best-effort, nunca quebra a coleta)."""
    if not link or not link.startswith(('http://', 'https://')):
        return None
    try:
        r = requests.get(link, headers=_BROWSER_HEADERS, timeout=8, verify=True)
        r.raise_for_status()
        # html.parser evita o modo XML (portais com <?xml?> no topo) e acha o <article>.
        soup = BeautifulSoup(r.content, 'html.parser')
        for tag in soup(['script', 'style', 'nav', 'aside', 'footer', 'header', 'form', 'figure']):
            tag.decompose()

        # escopo: o <article> (ou o container com mais texto); senão a página toda
        scope = soup.find('article')
        if scope is None:
            best, best_len = None, 0
            for cont in soup.find_all(['div', 'section', 'main']):
                tlen = len(cont.get_text(strip=True))
                if tlen > best_len:
                    best, best_len = cont, tlen
            scope = best or soup

        partes, total, seen = [], 0, set()
        for frag in scope.stripped_strings:
            t = re.sub(r'\s+', ' ', frag).strip()
            if len(t) < 40 or t in seen or _TEXT_LIXO.search(t):
                continue
            seen.add(t)
            partes.append(t)
            total += len(t)
            if total >= max_total:
                break
        corpo = ' '.join(partes).strip()
        if len(corpo) >= min_total:
            return corpo[:max_total]
    except Exception as e:
        logger.info(f"corpo da matéria falhou ({link[:50]}): {e}")
    return None


def fetch_feed(feed_config):
    """Coleta notícias de um feed RSS."""
    url = feed_config['url']
    logger.info(f"Coletando: {feed_config['source']} — {url}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; RadioSCBot/1.0)',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
        }
        response = requests.get(url, headers=headers, timeout=15, verify=True)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
    except Exception as e:
        logger.warning(f"Erro ao acessar {url}: {e}")
        try:
            # Tenta sem verificação SSL para sites com certificado auto-assinado
            response = requests.get(url, headers=headers, timeout=15, verify=False)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
        except Exception:
            try:
                feed = feedparser.parse(url)
            except Exception as e2:
                logger.error(f"Falha total em {url}: {e2}")
                return []

    max_entries = feed_config.get('max_entries', 20)
    articles = []
    for entry in feed.entries[:max_entries]:
        title = clean_html(getattr(entry, 'title', ''))
        summary = clean_html(getattr(entry, 'summary', '') or getattr(entry, 'description', ''))
        link = getattr(entry, 'link', '')
        
        # Data de publicação
        published = None
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                published = datetime(*entry.published_parsed[:6]).isoformat()
            except Exception:
                pass
        if not published:
            published = datetime.now().isoformat()

        # Imagem da notícia
        image_url = None
        if hasattr(entry, 'media_content') and entry.media_content:
            image_url = entry.media_content[0].get('url')
        elif hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
            image_url = entry.media_thumbnail[0].get('url')
        elif hasattr(entry, 'enclosures') and entry.enclosures:
            for enc in entry.enclosures:
                if enc.get('type', '').startswith('image'):
                    image_url = enc.get('href') or enc.get('url')
                    break

        # 🚫 fonte de imagem bloqueada (OCP/Schroeder): descarta a foto, mantém o texto
        if _image_blocked(link, feed_config.get('source', '')):
            image_url = None

        # Valida que o link é uma URL real (http/https)
        if not title or not link or not link.startswith(('http://', 'https://')):
            continue

        full_text = f"{title} {summary}"
        city = feed_config.get('city') or detect_city(full_text)
        # Usa categoria do feed quando for explícita (esporte, local); senão detecta pelo texto
        feed_cat = feed_config.get('category', 'geral')
        category = feed_cat if feed_cat and feed_cat != 'geral' else detect_category(full_text)

        articles.append({
            'title': title[:500],
            'summary': summary[:2000],
            'link': link,
            'source': feed_config['source'],
            'city': city,
            'category': category,
            'published_at': published,
            'image_url': image_url,
            'priority': feed_config.get('priority', False),
        })

    return articles


def _ensure_text_cols(conn):
    """Garante as colunas do NOSSO texto (reescrita) na tabela news."""
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(news)")]
        if 'title_own' not in cols:
            conn.execute("ALTER TABLE news ADD COLUMN title_own TEXT")
        if 'resumo_own' not in cols:
            conn.execute("ALTER TABLE news ADD COLUMN resumo_own TEXT")
        conn.commit()
    except Exception as e:
        logger.error(f"_ensure_text_cols falhou: {e}")


def _reescreve(art):
    """Reescreve a notícia no NOSSO tom (anti-strike + emoção) via cerebro. (titulo, corpo) ou
    (None, None) se desligado/IA falhar — aí o site cai no texto original."""
    if os.environ.get("REWRITE_ON", "1").strip() == "0":
        return None, None
    try:
        import cerebro
        t, c, _ = cerebro.gerar_texto(
            art.get('summary') or art.get('title') or '',
            cidade=art.get('city') or '', fonte=art.get('source') or '',
            titulo_hint=art.get('title') or '')
        if t and c:
            return t.strip()[:500], c.strip()[:2000]
    except Exception as e:
        logger.error(f"reescrita falhou p/ '{(art.get('title') or '')[:40]}': {e}")
    return None, None


def save_articles(articles):
    """Salva notícias, ignorando duplicatas. ENRIQUECE (Fase 2): se a duplicata trouxer foto
    e a versão já salva estiver SEM foto, preenche a foto (não joga a foto fora).
    TEXTO NOSSO: reescreve cada notícia nova no tom da Rádio (title_own/resumo_own)."""
    conn = get_db()
    _ensure_text_cols(conn)
    saved = 0
    # base de comparação: registros recentes (id, título, foto) — p/ dedup E enriquecimento
    try:
        recent = conn.execute(
            "SELECT id, title, image_url FROM news WHERE created_at > datetime('now','-3 days')"
        ).fetchall()
        vistos = [{'id': r['id'], 'title': r['title'], 'image_url': r['image_url']}
                  for r in recent if r['title']]
    except Exception:
        vistos = []

    for art in articles:
        try:
            if conn.execute('SELECT id FROM news WHERE link = ?', (art['link'],)).fetchone():
                continue

            # acha a gêmea (mesmo fato) já salva
            gemea = next((v for v in vistos if _overlap(art['title'], v['title']) >= 0.6), None)

            if gemea:
                # FOTO (Fase 2): se a salva está SEM foto e dá pra achar uma, preenche
                if not gemea.get('image_url') and not _image_blocked(art.get('link'), art.get('source')):
                    foto = art.get('image_url') or (fetch_og_image(art['link']) if art.get('link') else None)
                    if foto:
                        conn.execute('UPDATE news SET image_url=? WHERE id=?', (foto, gemea['id']))
                        gemea['image_url'] = foto
                        logger.info(f"📷 enriqueci gêmea #{gemea['id']} com foto de '{art['title'][:40]}'")
                logger.info(f"♻ Duplicada (mesmo fato) ignorada: {art['title'][:60]}")
                continue

            # NOVA notícia -> og:image se vier sem foto (Fase 1), depois insere
            if not art.get('image_url') and art.get('link') and not _image_blocked(art.get('link'), art.get('source')):
                art['image_url'] = fetch_og_image(art['link'])
                if art['image_url']:
                    logger.info(f"📷 og:image achada p/ '{art['title'][:45]}'")

            # TEXTO: resumo vazio/curto -> puxa o corpo da matéria (carrossel deixa de ser raso)
            if len((art.get('summary') or '').strip()) < 180 and art.get('link'):
                corpo = fetch_article_text(art['link'])
                if corpo and len(corpo) > len((art.get('summary') or '').strip()):
                    art['summary'] = corpo[:2000]
                    logger.info(f"📝 texto enriquecido p/ '{art['title'][:45]}' ({len(corpo)} chars)")

            # TEXTO NOSSO: reescreve no tom da Rádio (anti-strike + emoção). Site/Insta usam o nosso.
            title_own, resumo_own = _reescreve(art)
            if title_own:
                logger.info(f"✍️ reescrito p/ '{art['title'][:45]}' -> '{title_own[:45]}'")

            cur = conn.execute('''
                INSERT INTO news (title, summary, title_own, resumo_own, link, source, city, category,
                                  published_at, image_url, priority, audio_file, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
            ''', (
                art['title'], art['summary'], title_own, resumo_own, art['link'],
                art['source'], art['city'], art['category'],
                art['published_at'], art.get('image_url'), int(art.get('priority', False)),
                datetime.now().isoformat()
            ))
            vistos.append({'id': cur.lastrowid, 'title': art['title'], 'image_url': art.get('image_url')})
            saved += 1
        except Exception as e:
            logger.error(f"Erro ao salvar notícia: {e}")

    conn.commit()  # commita inserts E enriquecimentos
    conn.close()
    logger.info(f"Salvas {saved} novas notícias.")
    return saved


def clear_blocked_images(conn):
    """Apaga imagens JÁ salvas de fontes bloqueadas (OCP/Schroeder) — fica só o texto. Idempotente."""
    try:
        rows = conn.execute(
            "SELECT id, link, source FROM news WHERE image_url IS NOT NULL AND image_url!=''"
        ).fetchall()
        n = 0
        for r in rows:
            if _image_blocked(r['link'], r['source']):
                conn.execute("UPDATE news SET image_url=NULL WHERE id=?", (r['id'],))
                n += 1
        if n:
            conn.commit()
            logger.info(f"🧹 {n} imagem(ns) de fonte bloqueada (OCP/Schroeder) limpa(s).")
        return n
    except Exception as e:
        logger.error(f"clear_blocked_images falhou: {e}")
        return 0


def backfill_text(conn, limit=8):
    """Reescreve aos poucos as notícias ANTIGAS sem o nosso texto (title_own) — converte a base
    inteira p/ o nosso tom sem rodar tudo de uma vez (um punhado por coleta). Trava BACKFILL_ON."""
    if os.environ.get("BACKFILL_ON", "1").strip() == "0":
        return 0
    try:
        rows = conn.execute(
            "SELECT id, title, summary, source, city FROM news "
            "WHERE active=1 AND (title_own IS NULL OR title_own='') "
            "ORDER BY datetime(published_at) DESC LIMIT ?", (limit,)
        ).fetchall()
    except Exception:
        return 0
    n = 0
    for r in rows:
        t, c = _reescreve({'title': r['title'], 'summary': r['summary'],
                           'source': r['source'], 'city': r['city']})
        if t:
            conn.execute("UPDATE news SET title_own=?, resumo_own=? WHERE id=?", (t, c, r['id']))
            n += 1
    if n:
        conn.commit()
        logger.info(f"✍️ backfill: {n} notícia(s) antiga(s) reescrita(s) no nosso tom.")
    return n


def collect_all():
    """Coleta de todos os feeds RSS configurados."""
    # limpeza idempotente: tira imagem de OCP/Schroeder que tenha entrado antes do bloqueio
    try:
        _c = get_db()
        clear_blocked_images(_c)
        _c.close()
    except Exception:
        pass
    total = 0
    for feed_config in RSS_FEEDS:
        articles = fetch_feed(feed_config)
        saved = save_articles(articles)
        total += saved
    logger.info(f"Coleta concluída. Total de novas notícias: {total}")
    # backfill gradual do texto antigo (converte a base p/ o nosso tom, um pouco por coleta)
    try:
        _c = get_db()
        _ensure_text_cols(_c)
        backfill_text(_c)
        _c.close()
    except Exception:
        pass
    return total


if __name__ == '__main__':
    collect_all()
