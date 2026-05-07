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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = os.environ.get('DB_PATH', 'radio_sc.db')

RSS_FEEDS = [
    # ── Santa Catarina (geral) ──────────────────
    {
        'url': 'https://g1.globo.com/rss/g1/sc/',
        'source': 'G1 Santa Catarina',
        'city': 'Santa Catarina',
        'category': 'geral',
        'priority': True
    },
    {
        'url': 'https://ndmais.com.br/feed/',
        'source': 'ND Mais',
        'city': 'Santa Catarina',
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
    # ── Norte de SC — Schroeder, Guaramirim, Corupá (JDV) ──
    {
        'url': 'https://www.jdv.com.br/feed/',
        'source': 'JDV',
        'city': None,
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

CITY_KEYWORDS = {
    'Schroeder': ['schroeder', 'schroder'],
    'Joinville': ['joinville', 'joinvilense', 'joinvilhense'],
    'Jaraguá do Sul': ['jaraguá do sul', 'jaragua do sul', 'jaraguaense'],
    'Guaramirim': ['guaramirim'],
    'Corupá': ['corupá', 'corupa'],
    'Blumenau': ['blumenau', 'blumenauense'],
    'Florianópolis': ['florianópolis', 'floripa', 'florianopolitano'],
    'Norte de SC': ['norte catarinense', 'norte de santa catarina', 'região norte'],
    'Santa Catarina': ['santa catarina', 'catarinense'],
}

# Cidades que pertencem ao Norte de SC (para o filtro de região)
NORTE_SC_CITIES = {'Schroeder', 'Joinville', 'Jaraguá do Sul', 'Guaramirim', 'Corupá', 'Norte de SC'}

CATEGORY_KEYWORDS = {
    'policial': ['crime', 'assalto', 'homicídio', 'acidente', 'preso', 'policial', 'pm', 'delegacia', 'roubo', 'furto', 'morte', 'óbito', 'batida', 'colisão'],
    'politica': ['prefeitura', 'câmara', 'vereador', 'prefeito', 'eleição', 'governo', 'governador', 'deputado', 'política'],
    'saude': ['hospital', 'saúde', 'dengue', 'vacina', 'ubs', 'médico', 'doença', 'covid', 'pandemia'],
    'esporte': ['futebol', 'esporte', 'atleta', 'campeonato', 'jogo', 'gol', 'time', 'torneio'],
    'economia': ['emprego', 'empresa', 'mercado', 'economia', 'negócio', 'indústria', 'comércio', 'renda'],
    'clima': ['chuva', 'temporal', 'vento', 'frio', 'calor', 'enchente', 'clima', 'previsão do tempo'],
    'cultura': ['evento', 'festa', 'show', 'cultura', 'música', 'teatro', 'exposição', 'festival'],
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def detect_city(text):
    text_lower = text.lower()
    for city, keywords in CITY_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return city
    return 'Santa Catarina'


def detect_category(text):
    text_lower = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return category
    return 'geral'


def clean_html(text):
    if not text:
        return ''
    soup = BeautifulSoup(text, 'lxml')
    return soup.get_text(separator=' ').strip()


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

        if not title or not link:
            continue

        full_text = f"{title} {summary}"
        city = feed_config.get('city') or detect_city(full_text)
        category = detect_category(full_text)

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


def save_articles(articles):
    """Salva notícias no banco, ignorando duplicatas."""
    conn = get_db()
    saved = 0
    for art in articles:
        try:
            existing = conn.execute(
                'SELECT id FROM news WHERE link = ?', (art['link'],)
            ).fetchone()
            if existing:
                continue

            conn.execute('''
                INSERT INTO news (title, summary, link, source, city, category,
                                  published_at, image_url, priority, audio_file, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
            ''', (
                art['title'], art['summary'], art['link'],
                art['source'], art['city'], art['category'],
                art['published_at'], art.get('image_url'), int(art.get('priority', False)),
                datetime.now().isoformat()
            ))
            conn.commit()
            saved += 1
        except Exception as e:
            logger.error(f"Erro ao salvar notícia: {e}")

    conn.close()
    logger.info(f"Salvas {saved} novas notícias.")
    return saved


def collect_all():
    """Coleta de todos os feeds RSS configurados."""
    total = 0
    for feed_config in RSS_FEEDS:
        articles = fetch_feed(feed_config)
        saved = save_articles(articles)
        total += saved
    logger.info(f"Coleta concluída. Total de novas notícias: {total}")
    return total


if __name__ == '__main__':
    collect_all()
