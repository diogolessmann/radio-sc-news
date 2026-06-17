"""
app.py — Backend principal Flask
Rádio SC News — Portal de notícias com áudio e painel admin
"""
import os
import sqlite3
import logging
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, render_template, request, jsonify,
                   redirect, url_for, session, send_from_directory,
                   render_template_string)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# ──────────────────────────────────────────────
# Configurações
# ──────────────────────────────────────────────
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# PERSISTÊNCIA: se a Railway montou um VOLUME e DB_PATH não foi setado, usa o volume.
# Sem isso o SQLite fica no diretório efêmero e ZERA a cada deploy (perde parceiros,
# eventos, histórico de posts, insights). Todos os módulos leem DB_PATH do ambiente,
# então setar aqui (cedo) vale pra todos.
# ──────────────────────────────────────────────
_vol = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH')
if _vol and not os.environ.get('DB_PATH'):
    os.environ['DB_PATH'] = os.path.join(_vol, 'radio_sc.db')
    logging.getLogger(__name__).info("💾 DB no volume persistente: %s", os.environ['DB_PATH'])

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'radio-sc-secret-2024-xk91')

DB_PATH       = os.environ.get('DB_PATH', 'radio_sc.db')
AUDIO_DIR     = os.environ.get('AUDIO_DIR', 'audio')
UPLOAD_DIR    = os.environ.get('UPLOAD_DIR', 'uploads')
_admin_pw_env = os.environ.get('ADMIN_PASSWORD', 'julia181014')
# Aceita hash bcrypt na env var (recomendado) ou plain text com hash gerado em runtime
if _admin_pw_env.startswith('$2b$') or _admin_pw_env.startswith('$2a$'):
    ADMIN_PASSWORD_HASH = _admin_pw_env
else:
    ADMIN_PASSWORD_HASH = generate_password_hash(_admin_pw_env)

ALLOWED_IMAGE = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_UPLOAD_MB = 10
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_MB * 1024 * 1024

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ──────────────────────────────────────────────
# Banco de dados
# ──────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS news (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            summary     TEXT,
            link        TEXT UNIQUE,
            source      TEXT,
            city        TEXT DEFAULT "Santa Catarina",
            category    TEXT DEFAULT "geral",
            published_at TEXT,
            image_url   TEXT,
            admin_image TEXT,
            audio_file  TEXT,
            priority    INTEGER DEFAULT 0,
            active      INTEGER DEFAULT 1,
            created_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS media (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            filename    TEXT NOT NULL,
            type        TEXT DEFAULT "image",
            caption     TEXT,
            news_id     INTEGER,
            created_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS ads (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            text        TEXT,
            image       TEXT,
            audio_file  TEXT,
            link        TEXT,
            active      INTEGER DEFAULT 1,
            show_in_feed INTEGER DEFAULT 1,
            created_at  TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_news_published ON news(published_at DESC);
        CREATE INDEX IF NOT EXISTS idx_news_city      ON news(city);
        CREATE INDEX IF NOT EXISTS idx_news_category  ON news(category);

        CREATE TABLE IF NOT EXISTS transmissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            type TEXT DEFAULT 'geral',
            description TEXT,
            stream_url TEXT,
            youtube_channel_id TEXT,
            youtube_video_id TEXT,
            scheduled_at TEXT,
            duration_minutes INTEGER DEFAULT 90,
            is_live INTEGER DEFAULT 0,
            is_recurring INTEGER DEFAULT 0,
            recurrence_days TEXT,
            thumbnail_url TEXT,
            city TEXT DEFAULT 'Região',
            active INTEGER DEFAULT 1,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS monitored_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            youtube_channel_id TEXT,
            youtube_handle TEXT,
            type TEXT DEFAULT 'geral',
            city TEXT,
            auto_publish INTEGER DEFAULT 1,
            active INTEGER DEFAULT 1,
            last_checked TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS classifieds (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            title            TEXT NOT NULL,
            description      TEXT,
            category         TEXT NOT NULL DEFAULT 'outros',
            price            REAL,
            price_negotiable INTEGER DEFAULT 0,
            city             TEXT DEFAULT 'Schroeder',
            contact_name     TEXT NOT NULL,
            contact_whatsapp TEXT NOT NULL,
            photo            TEXT,
            status           TEXT DEFAULT 'pending',
            terms_accepted   INTEGER DEFAULT 0,
            views            INTEGER DEFAULT 0,
            featured         INTEGER DEFAULT 0,
            created_at       TEXT,
            approved_at      TEXT,
            expires_at       TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_classifieds_status   ON classifieds(status);
        CREATE INDEX IF NOT EXISTS idx_classifieds_category ON classifieds(category);
        CREATE INDEX IF NOT EXISTS idx_classifieds_city     ON classifieds(city);

        CREATE TABLE IF NOT EXISTS jobs (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            title            TEXT NOT NULL,
            company          TEXT NOT NULL,
            description      TEXT,
            category         TEXT DEFAULT 'outros',
            job_type         TEXT DEFAULT 'clt',
            salary           TEXT,
            city             TEXT DEFAULT 'Schroeder',
            contact_whatsapp TEXT NOT NULL,
            contact_email    TEXT,
            status           TEXT DEFAULT 'pending',
            views            INTEGER DEFAULT 0,
            featured         INTEGER DEFAULT 0,
            created_at       TEXT,
            approved_at      TEXT,
            expires_at       TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_status   ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_jobs_city     ON jobs(city);
        CREATE INDEX IF NOT EXISTS idx_jobs_category ON jobs(category);
        CREATE INDEX IF NOT EXISTS idx_jobs_expires  ON jobs(expires_at);

        CREATE TABLE IF NOT EXISTS youtube_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            channel_id TEXT NOT NULL UNIQUE,
            category TEXT DEFAULT 'geral',
            description TEXT,
            active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT
        );

    ''')
    conn.commit()
    conn.close()
    logger.info("Banco de dados inicializado.")


# ──────────────────────────────────────────────
# Autenticação Admin
# ──────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def allowed_file(filename):
    return ('.' in filename and
            filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE)


# ──────────────────────────────────────────────
# Rotas Públicas
# ──────────────────────────────────────────────
WA_CHANNEL_URL = os.environ.get('WA_CHANNEL_URL', '')
TV_STREAM_ID   = os.environ.get('TV_STREAM_ID', 'EKqjDNytTkw')   # SCC SBT 24h — fallback estático
PORTAL_URL     = os.environ.get('PORTAL_URL', 'https://www.radioscnews.com.br')  # URL canônica do portal

# ── Canais monitorados para detecção automática de live ──
LIVE_CHANNELS = {
    'scc':    { 'channel_id': 'UCEzVIIPtAIfsRCEHwn4AOzw', 'fallback': 'EKqjDNytTkw' },
    'jpnews': { 'channel_id': 'UCP391YRAjSOdM_bwievgaZA', 'fallback': 'D9dBBE4dKeY' },
    'nasa':   { 'channel_id': 'UCLA_DiR1FfKNvjuUpBHmylQ', 'fallback': 'uwXgcTc8oY8' },
}

# Cache em memória: { 'scc': {'vid': 'abc123', 'ts': 1234567890.0} }
_live_cache = {}
LIVE_CACHE_TTL = 600  # 10 minutos

def get_channel_live_id(channel_id, fallback=None):
    """Segue o redirect de /live do canal e extrai o video ID atual. Sem API key."""
    import re, requests as req
    try:
        url = f'https://www.youtube.com/channel/{channel_id}/live'
        r = req.get(url, timeout=8, allow_redirects=True, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0'
        })
        # Tenta extrair do URL final após redirect
        final = r.url
        if 'watch?v=' in final:
            return final.split('watch?v=')[1].split('&')[0]
        # Fallback: busca no HTML da página
        m = re.search(r'"videoId":"([A-Za-z0-9_-]{11})"', r.text)
        if m:
            return m.group(1)
    except Exception as e:
        logger.warning(f'Live detect failed for {channel_id}: {e}')
    return fallback

@app.route('/api/live-channels')
def api_live_channels():
    """Retorna os video IDs ao vivo de cada canal monitorado (cache 10min)."""
    import time
    now = time.time()
    result = {}
    for key, cfg in LIVE_CHANNELS.items():
        cached = _live_cache.get(key)
        if cached and now - cached['ts'] < LIVE_CACHE_TTL:
            result[key] = cached['vid']
        else:
            vid = get_channel_live_id(cfg['channel_id'], cfg['fallback'])
            _live_cache[key] = {'vid': vid, 'ts': now}
            result[key] = vid
    return jsonify(result)



@app.route('/admin/channels', methods=['GET', 'POST'])
@login_required
def admin_channels():
    if request.method == 'POST':
        data = request.form
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'success': False, 'message': 'Nome obrigatório.'}), 400

        yt_channel = data.get('youtube_channel_id', '').strip()
        yt_handle  = data.get('youtube_handle', '').strip()
        c_type     = data.get('type', 'geral').strip()
        city       = data.get('city', '').strip()
        auto_pub   = 1 if data.get('auto_publish') else 0

        conn = get_db()
        cur = conn.execute('''
            INSERT INTO monitored_channels
            (name, youtube_channel_id, youtube_handle, type, city, auto_publish, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        ''', (name, yt_channel or None, yt_handle or None, c_type,
              city or None, auto_pub, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'id': cur.lastrowid})

    conn = get_db()
    channels = conn.execute(
        'SELECT * FROM monitored_channels ORDER BY created_at DESC'
    ).fetchall()
    conn.close()
    return jsonify([dict(c) for c in channels])


@app.route('/admin/channels/<int:c_id>/delete', methods=['POST'])
@login_required
def admin_delete_channel(c_id):
    conn = get_db()
    conn.execute('DELETE FROM monitored_channels WHERE id=?', (c_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/admin/channels/check_live', methods=['POST'])
@login_required
def admin_check_live():
    """Força verificação imediata de ao vivo para todos os canais monitorados."""
    try:
        from stream_checker import update_live_status
        update_live_status(DB_PATH)
        return jsonify({'success': True, 'message': 'Verificação concluída.'})
    except Exception as e:
        logger.error(f'Erro em check_live manual: {e}')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/')
def index():
    return render_template('index.html',
                           wa_channel=WA_CHANNEL_URL,
                           tv_stream_id=TV_STREAM_ID)


@app.route('/noticia/<int:news_id>')
def noticia_permalink(news_id):
    """Página de artigo individual — permalink compartilhável com Open Graph."""
    conn = get_db()
    n = conn.execute('SELECT * FROM news WHERE id=? AND active=1', (news_id,)).fetchone()
    conn.close()
    if not n:
        return redirect('/', 302)
    n = dict(n)
    # Imagem para OG: prefere admin_image, depois image_url
    og_image = ''
    if n.get('admin_image'):
        og_image = f"{PORTAL_URL}/uploads/{n['admin_image']}"
    elif n.get('image_url'):
        og_image = n['image_url']
    og_url = f"{PORTAL_URL}/noticia/{news_id}"
    return render_template('noticia.html', n=n, og_url=og_url, og_image=og_image,
                           portal_url=PORTAL_URL)


@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')


@app.route('/api/news')
def api_news():
    """Feed de notícias paginado com filtros."""
    page     = max(1, int(request.args.get('page', 1)))
    per_page = min(20, int(request.args.get('per_page', 10)))
    city     = request.args.get('city', '')
    category = request.args.get('category', '')
    search   = request.args.get('q', '')
    offset   = (page - 1) * per_page

    conn = get_db()
    where = ['n.active = 1', "n.link IS NOT NULL", "n.link != ''", "n.link LIKE 'http%'"]
    params = []

    # Filtro de cidade (independente)
    if city:
        where.append('n.city = ?')
        params.append(city)

    # Filtro de categoria (independente — combina com cidade)
    if category:
        where.append('n.category = ?')
        params.append(category)
    else:
        # Esporte só aparece quando explicitamente selecionado
        where.append("n.category != 'esporte'")

    if search:
        where.append('(n.title LIKE ? OR n.summary LIKE ?)')
        params += [f'%{search}%', f'%{search}%']

    where_sql = ' AND '.join(where)

    # Limita esporte a 10 por página mesmo que per_page seja maior
    effective_limit = min(per_page, 10) if category == 'esporte' else per_page

    news_rows = conn.execute(f'''
        SELECT n.*,
               GROUP_CONCAT(m.filename) as media_files
        FROM news n
        LEFT JOIN media m ON m.news_id = n.id AND m.type = "image"
        WHERE {where_sql}
        GROUP BY n.id
        ORDER BY n.priority DESC, n.published_at DESC
        LIMIT ? OFFSET ?
    ''', params + [effective_limit, offset]).fetchall()

    total = conn.execute(
        f'SELECT COUNT(*) FROM news n WHERE {where_sql}', params
    ).fetchone()[0]

    # Propagandas ativas
    ads = conn.execute(
        'SELECT * FROM ads WHERE active=1 AND show_in_feed=1 ORDER BY RANDOM() LIMIT 3'
    ).fetchall()

    conn.close()

    news_list = []
    for row in news_rows:
        item = dict(row)
        item['media_files'] = row['media_files'].split(',') if row['media_files'] else []
        news_list.append(item)

    return jsonify({
        'news': news_list,
        'ads': [dict(a) for a in ads],
        'page': page,
        'per_page': per_page,
        'total': total,
        'has_more': (offset + per_page) < total
    })


@app.route('/api/weather')
def api_weather():
    """Clima atual das cidades do Norte de SC."""
    import os
    key_set = bool(os.environ.get('OPENWEATHER_API_KEY', ''))
    try:
        from weather import fetch_all_weather
        data = fetch_all_weather()
        return jsonify({'weather': data, 'available': len(data) > 0, 'key_set': key_set})
    except Exception as e:
        logger.error(f"Erro no clima: {e}")
        return jsonify({'weather': [], 'available': False, 'key_set': key_set})


# Cache de ofertas ML (30 min)
import time as _time
_deals_cache = {'data': [], 'ts': 0}
DEALS_CACHE_SEC = 1800

ML_AFFILIATE_ID = os.environ.get('ML_AFFILIATE_ID', '')

def build_affiliate_link(url):
    """Adiciona parâmetros de afiliado ML ao link do produto."""
    if not url or not ML_AFFILIATE_ID:
        return url
    sep = '&' if '?' in url else '?'
    return f"{url}{sep}matt_tool={ML_AFFILIATE_ID}&matt_word=radioscnews&matt_source=radioscnews&matt_campaign=ofertas"

@app.route('/api/deals')
def api_deals():
    """Ofertas com desconto do Mercado Livre."""
    global _deals_cache
    now = _time.time()
    if now - _deals_cache['ts'] < DEALS_CACHE_SEC and _deals_cache['data']:
        return jsonify({'deals': _deals_cache['data'], 'cached': True})

    try:
        import requests as _req

        SEARCH_QUERIES = [
            'oferta do dia eletronicos',
            'fone bluetooth oferta',
            'smartwatch oferta',
            'caixa de som bluetooth oferta',
            'carregador portatil oferta',
        ]

        deals = []
        seen_ids = set()

        for q in SEARCH_QUERIES:
            if len(deals) >= 10:
                break
            try:
                resp = _req.get(
                    'https://api.mercadolibre.com/sites/MLB/search',
                    params={'q': q, 'sort': 'relevance', 'limit': 50, 'condition': 'new'},
                    timeout=8
                )
                if resp.status_code != 200:
                    continue
                items = resp.json().get('results', [])
                for item in items:
                    if item['id'] in seen_ids or not item.get('thumbnail'):
                        continue
                    price = item.get('price', 0)
                    if price <= 0:
                        continue
                    orig = item.get('original_price')
                    discount = round((1 - price / orig) * 100) if orig and orig > price else 0
                    thumb = item['thumbnail'].replace('http://', 'https://')
                    seen_ids.add(item['id'])
                    deals.append({
                        'id': item['id'],
                        'title': item['title'][:70],
                        'price': price,
                        'original_price': orig,
                        'discount': discount,
                        'thumbnail': thumb,
                        'link': build_affiliate_link(item.get('permalink', '')),
                        'free_shipping': item.get('shipping', {}).get('free_shipping', False),
                    })
                    if len(deals) >= 10:
                        break
            except Exception:
                continue

        _deals_cache = {'data': deals, 'ts': now}
        return jsonify({'deals': deals, 'cached': False})
    except Exception as e:
        logger.error(f"Erro ao buscar ofertas ML: {e}")
        return jsonify({'deals': [], 'cached': False})


@app.route('/api/counts')
def api_counts():
    """Contagem de notícias por cidade e categoria para os badges."""
    conn = get_db()
    city_rows = conn.execute(
        "SELECT city, COUNT(*) as n FROM news WHERE active=1 AND category != 'esporte' GROUP BY city"
    ).fetchall()
    cat_rows = conn.execute(
        "SELECT category, COUNT(*) as n FROM news WHERE active=1 GROUP BY category"
    ).fetchall()
    conn.close()
    return jsonify({
        'cities': {r['city']: r['n'] for r in city_rows},
        'categories': {r['category']: r['n'] for r in cat_rows}
    })


@app.route('/api/cities')
def api_cities():
    conn = get_db()
    rows = conn.execute(
        'SELECT DISTINCT city FROM news WHERE active=1 ORDER BY city'
    ).fetchall()
    conn.close()
    return jsonify([r['city'] for r in rows])


@app.route('/api/categories')
def api_categories():
    conn = get_db()
    rows = conn.execute(
        'SELECT DISTINCT category FROM news WHERE active=1 ORDER BY category'
    ).fetchall()
    conn.close()
    return jsonify([r['category'] for r in rows])


# Servir áudio
@app.route('/audio/<path:filename>')
def serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename)


# Servir uploads
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route('/api/audio/<int:news_id>')
def api_get_audio(news_id):
    """Gera e retorna áudio de uma notícia — acesso público (geração sob demanda)."""
    conn = get_db()
    news = conn.execute('SELECT * FROM news WHERE id=? AND active=1', (news_id,)).fetchone()
    conn.close()

    if not news:
        return jsonify({'success': False, 'message': 'Notícia não encontrada.'}), 404

    # Já tem áudio gerado
    if news['audio_file']:
        audio_path = os.path.join(AUDIO_DIR, news['audio_file'])
        if os.path.exists(audio_path):
            return jsonify({'success': True, 'audio_url': f"/audio/{news['audio_file']}"})

    # Gera sob demanda
    try:
        from tts_engine import generate_audio
        audio_file = generate_audio(
            title=news['title'],
            summary=news['summary'] or '',
            source=news['source'],
            city=news['city'],
            news_id=news_id,
            category=news['category']
        )
        if audio_file:
            conn = get_db()
            conn.execute('UPDATE news SET audio_file=? WHERE id=?', (audio_file, news_id))
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'audio_url': f'/audio/{audio_file}'})
        else:
            return jsonify({'success': False, 'message': 'Falha ao gerar áudio.'}), 500
    except Exception as e:
        logger.error(f"Erro ao gerar áudio público {news_id}: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ──────────────────────────────────────────────
# Rotas Admin — Autenticação
# ──────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin'))
    
    error = None
    if request.method == 'POST':
        pwd = request.form.get('password', '')
        if check_password_hash(ADMIN_PASSWORD_HASH, pwd):
            session['admin_logged_in'] = True
            session.permanent = True
            return redirect(url_for('admin'))
        else:
            error = 'Senha incorreta.'
    
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ──────────────────────────────────────────────
# Rotas Admin — Painel
# ──────────────────────────────────────────────
@app.route('/admin')
@login_required
def admin():
    conn = get_db()
    news = conn.execute(
        'SELECT * FROM news ORDER BY created_at DESC LIMIT 100'
    ).fetchall()
    media = conn.execute(
        'SELECT * FROM media ORDER BY created_at DESC LIMIT 50'
    ).fetchall()
    ads = conn.execute(
        'SELECT * FROM ads ORDER BY created_at DESC'
    ).fetchall()
    stats = {
        'total_news': conn.execute('SELECT COUNT(*) FROM news').fetchone()[0],
        'with_audio': conn.execute('SELECT COUNT(*) FROM news WHERE audio_file IS NOT NULL').fetchone()[0],
        'total_ads':  conn.execute('SELECT COUNT(*) FROM ads').fetchone()[0],
        'total_media': conn.execute('SELECT COUNT(*) FROM media').fetchone()[0],
    }
    # métricas úteis do motor (substituem os zeros): posts hoje, % com foto, eventos, parceiros
    try:
        import metricas
        m = metricas.coletar()
        stats['posts_hoje'] = m['postados_hoje']
        stats['pct_foto'] = m['pct_foto']
    except Exception:
        stats['posts_hoje'] = stats.get('posts_hoje', 0)
        stats['pct_foto'] = stats.get('pct_foto', 0)
    try:
        import agenda
        stats['eventos'] = len(agenda.eventos_proximos())
    except Exception:
        stats['eventos'] = 0
    try:
        import sponsors
        stats['parceiros'] = len(sponsors.active_sponsors())
    except Exception:
        stats['parceiros'] = 0
    conn.close()
    return render_template('admin.html', news=news, media=media, ads=ads, stats=stats)


# ──────────────────────────────────────────────
# A REDAÇÃO — produção de post sob demanda (IA híbrida: Gemini/Groq/Claude)
# ──────────────────────────────────────────────
@app.route('/admin/redacao')
@login_required
def admin_redacao():
    try:
        import cerebro
        brains = cerebro.disponiveis()
    except Exception:
        brains = {'gemini': False, 'groq': False, 'claude': False}
    categorias = ['politica', 'policial', 'saude', 'esporte', 'economia',
                  'clima', 'cultura', 'local', 'geral']
    return render_template('redacao.html', brains=brains, categorias=categorias)


@app.route('/admin/redacao/gerar', methods=['POST'])
@login_required
def admin_redacao_gerar():
    """Recebe info bruta → redator (IA híbrida) → revisor → card. Não publica."""
    import os as _os, shutil, time
    data = request.get_json(force=True, silent=True) or {}
    bruto = (data.get('bruto') or '').strip()
    if not bruto:
        return jsonify({'ok': False, 'erro': 'Cole a informação primeiro.'}), 400
    cidade = (data.get('cidade') or 'Schroeder').strip()
    categoria = (data.get('categoria') or 'geral').strip()
    fonte = (data.get('fonte') or '').strip()
    titulo_hint = (data.get('titulo') or '').strip()
    brain = (data.get('brain') or 'auto').strip()
    try:
        import cerebro, redator
        titulo, corpo, usado = cerebro.gerar_texto(bruto, cidade, fonte, titulo_hint, brain)
        legenda = redator.legenda(titulo, corpo, cidade, categoria)
        alertas = redator.revisar(titulo, corpo, fonte)
        # gera os slides (reusa o motor oficial) e copia a CAPA p/ static/redacao (preview)
        slug = redator._slug(titulo)
        outdir, paths = redator.gerar_arte(titulo, corpo, cidade, categoria, slug)
        prev_dir = _os.path.join('static', 'redacao')
        _os.makedirs(prev_dir, exist_ok=True)
        fname = f"{slug}_{int(time.time())}.png"
        shutil.copyfile(paths[0], _os.path.join(prev_dir, fname))
        return jsonify({'ok': True, 'titulo': titulo, 'corpo': corpo,
                        'legenda': legenda, 'alertas': alertas, 'cerebro': usado,
                        'card_url': f"/static/redacao/{fname}", 'n_slides': len(paths),
                        'pasta_slides': _os.path.abspath(outdir)})
    except Exception as e:
        logger.error(f"Redacao gerar falhou: {e}")
        return jsonify({'ok': False, 'erro': str(e)}), 500


@app.route('/admin/saude')
@login_required
def admin_saude():
    """Health check do motor — guia o kaizen com dado, não achismo (posts/dia, % foto,
    distribuição por cidade/categoria, fila). SQL puro, sem IA."""
    try:
        import metricas
        m = metricas.coletar()
    except Exception as e:
        logger.error(f"Health check falhou: {e}")
        return f"<pre>health check falhou: {e}</pre>", 500
    return render_template_string(_SAUDE_HTML, m=m)


_SAUDE_HTML = """<!doctype html><html lang=pt-br><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Saúde do Motor · Rádio SC News</title>
<style>
 body{background:#11121a;color:#eee;font-family:system-ui,Segoe UI,Arial;margin:0;padding:24px}
 h1{font-size:20px;margin:0 0 4px} .sub{color:#9a9cab;font-size:13px;margin-bottom:20px}
 .grid{display:flex;flex-wrap:wrap;gap:14px;margin-bottom:22px}
 .card{background:#181a22;border:1px solid #262838;border-radius:14px;padding:16px 20px;min-width:130px}
 .num{font-size:30px;font-weight:800} .lbl{color:#9a9cab;font-size:12px;margin-top:4px}
 .ok{color:#46d27e} .warn{color:#f5c518} .bad{color:#e74c3c}
 h2{font-size:15px;margin:18px 0 8px;color:#cfd0db}
 .bar{background:#222433;border-radius:8px;height:22px;margin:5px 0;position:relative;overflow:hidden}
 .bar > i{display:block;height:100%;background:#e74c3c}
 .bar > span{position:absolute;left:10px;top:2px;font-size:12px;color:#fff}
 a{color:#f5c518}
</style></head><body>
<h1>🩺 Saúde do Motor — Rádio SC News</h1>
<div class=sub>Sem medir, kaizen é chute. (atualiza a cada refresh)</div>
<div class=grid>
 <div class=card><div class=num>{{m.postados_hoje}}</div><div class=lbl>posts hoje</div></div>
 <div class=card><div class=num>{{m.postados_7d}}</div><div class=lbl>posts 7 dias</div></div>
 <div class=card><div class="num {{'ok' if m.pct_foto>=70 else 'warn'}}">{{m.pct_foto}}%</div><div class=lbl>com foto</div></div>
 <div class=card><div class="num {{'ok' if m.pct_norte>=50 else 'warn'}}">{{m.pct_norte}}%</div><div class=lbl>Norte de SC</div></div>
 <div class=card><div class=num>{{m.pendentes}}</div><div class=lbl>na fila</div></div>
 <div class=card><div class="num {{'warn' if m.seguradas else ''}}">{{m.seguradas}}</div><div class=lbl>seguradas (revisão)</div></div>
 <div class=card><div class="num {{'warn' if m.pct_sem_summary>20 else ''}}">{{m.pct_sem_summary}}%</div><div class=lbl>sem texto (carrossel raso)</div></div>
</div>
<h2>Por cidade</h2>
{% for c,n,p in m.cidades %}<div class=bar><i style="width:{{p}}%"></i><span>{{c}} — {{n}} ({{p}}%)</span></div>{% endfor %}
<h2>Por categoria</h2>
{% for c,n,p in m.categorias %}<div class=bar><i style="width:{{p}}%;background:#3a7"></i><span>{{c}} — {{n}} ({{p}}%)</span></div>{% endfor %}
<h2>🏆 Top posts — o que o Vale salvou + compartilhou</h2>
{% if m.top_posts %}
 {% for t,c,reach,saved,shares in m.top_posts %}
  <div style="background:#181a22;border:1px solid #262838;border-radius:10px;padding:8px 12px;margin:5px 0">
   <span style="color:#46d27e;font-weight:800">{{saved+shares}}</span>
   <span style="color:#9a9cab;font-size:12px"> 💾{{saved}} · 🔁{{shares}} · alcance {{reach}}</span><br>
   <span style="font-size:13px">{{c}} — {{t[:64]}}</span></div>
 {% endfor %}
{% else %}
 <div class=sub>Ainda sem dados de Insights — aparece após o 1º post novo (que salva o id) + o job das 23h30. Coletados até agora: {{m.com_insights}}.</div>
{% endif %}
<h2>Fotos de stock regional ({{m.stock_fotos|length}})</h2>
<div class=sub>{% if m.stock_fotos %}{{m.stock_fotos|join(' · ')}}{% else %}nenhuma ainda — põe fotos das cidades em static/stock/ (schroeder.jpg, jaragua-do-sul.jpg...){% endif %}</div>
<p style="margin-top:24px"><a href="/admin">← voltar ao painel</a></p>
</body></html>"""


@app.route('/admin/geo')
@login_required
def admin_geo():
    """Descobre os Place ids do Facebook das cidades (pro geotag) usando o token Meta.
    Mostra candidatos p/ o dono copiar o GEO_LOCATIONS certo no Railway."""
    cidades = ['Schroeder', 'Jaragua do Sul', 'Guaramirim', 'Joinville', 'Corupa']
    try:
        import geo, distribuidor
        tem_token = bool(distribuidor.META_PAGE_TOKEN)
        resultados = [(c, geo.candidatos(c)) for c in cidades] if tem_token else []
    except Exception as e:
        logger.error(f"admin_geo falhou: {e}")
        tem_token, resultados = False, []
    return render_template_string(_GEO_HTML, resultados=resultados, tem_token=tem_token)


_GEO_HTML = """<!doctype html><html lang=pt-br><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Geotag · Place ids</title>
<style>
 body{background:#11121a;color:#eee;font-family:system-ui,Segoe UI,Arial;margin:0;padding:24px;line-height:1.5}
 h1{font-size:20px} h2{font-size:15px;margin:18px 0 6px;color:#f5c518}
 code{background:#222433;padding:2px 7px;border-radius:6px;color:#9fe} a{color:#f5c518}
 .cand{background:#181a22;border:1px solid #262838;border-radius:10px;padding:10px 14px;margin:6px 0}
 .id{color:#46d27e;font-weight:700} .warn{color:#f5c518}
 .box{background:#181a22;border:1px solid #262838;border-radius:10px;padding:14px;margin-top:18px}
</style></head><body>
<h1>📍 Geotag — achar os Place ids das cidades</h1>
{% if not tem_token %}
 <p class=warn>Sem META_PAGE_TOKEN no ambiente — não dá pra buscar. (Confere o token no Railway.)</p>
{% elif not resultados or resultados|map(attribute=1)|select|list|length == 0 %}
 <p class=warn>O token não retornou lugares (o /pages/search do Facebook é restrito a apps aprovados).</p>
 <div class=box>
  <b>Plano B — pega o id na mão (2 min):</b>
  <ol>
   <li>Abre <a href="https://www.facebook.com/" target=_blank>facebook.com</a> e busca a cidade (ex: "Schroeder, Santa Catarina").</li>
   <li>Entra na página do LUGAR (cidade), e na URL/sobre pega o número do id.</li>
   <li>Ou deixa o geotag desligado por enquanto (apaga a variável GEO_LOCATIONS) — nada quebra.</li>
  </ol>
 </div>
{% else %}
 <p>Escolhe o lugar certo de cada cidade e monta a variável <code>GEO_LOCATIONS</code> no Railway:</p>
 {% for cidade, cands in resultados %}
  <h2>{{cidade}}</h2>
  {% if cands %}
   {% for c in cands[:5] %}
    <div class=cand><span class=id>{{c.id}}</span> — {{c.name}}{% if c.local %} <span style="color:#9a9cab">({{c.local}})</span>{% endif %}</div>
   {% endfor %}
  {% else %}<div class=cand class=warn>nada encontrado</div>{% endif %}
 {% endfor %}
 <div class=box>Depois monta assim (cola no Railway, sem espaços a mais):<br><br>
  <code>GEO_LOCATIONS=Schroeder=ID1,Jaragua do Sul=ID2,Guaramirim=ID3,Joinville=ID4</code><br><br>
  trocando ID1..ID4 pelos números <span class=id>verdes</span> acima.</div>
{% endif %}
<p style="margin-top:22px"><a href="/admin/saude">→ painel de saúde</a> · <a href="/admin">← painel</a></p>
</body></html>"""


@app.route('/admin/patrocinadores', methods=['GET', 'POST'])
@login_required
def admin_patrocinadores():
    """Gestão dos parceiros (Selo Patrocinador + publipost). Cadastra/liga/remove fácil."""
    import sponsors as sp
    msg = ""
    if request.method == 'POST':
        acao = request.form.get('acao')
        try:
            if acao == 'add':
                nome = (request.form.get('name') or '').strip()
                if nome:
                    sp.add_sponsor(nome, request.form.get('logo', ''),
                                   request.form.get('phone', ''), request.form.get('instagram', ''))
                    msg = f"✅ Parceiro '{nome}' cadastrado e ATIVO!"
                else:
                    msg = "⚠️ Informe o nome do parceiro."
            elif acao == 'toggle':
                sp.set_active(request.form.get('id'), 0 if request.form.get('active') == '1' else 1)
            elif acao == 'remove':
                sp.remove_sponsor(request.form.get('id'))
                msg = "🗑️ Parceiro removido."
        except Exception as e:
            logger.error(f"admin_patrocinadores: {e}")
            msg = f"erro: {e}"
    try:
        lista = sp.list_sponsors()
        semana = sp.sponsor_of_the_week()
    except Exception:
        lista, semana = [], None
    return render_template_string(_PATRO_HTML, lista=lista, msg=msg, semana=semana)


_PATRO_HTML = """<!doctype html><html lang=pt-br><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Parceiros · Rádio SC News</title>
<style>
 body{background:#11121a;color:#eee;font-family:system-ui,Segoe UI,Arial;margin:0;padding:24px;line-height:1.5}
 h1{font-size:20px} h2{font-size:15px;margin:18px 0 8px;color:#cfd0db}
 input{background:#181a22;border:1px solid #2a2c3c;color:#eee;border-radius:8px;padding:10px;margin:4px 0;width:100%;max-width:420px;box-sizing:border-box}
 button{background:#e74c3c;color:#fff;border:0;border-radius:8px;padding:9px 16px;cursor:pointer;font-weight:700}
 button.alt{background:#2a2c3c} .msg{background:#16321f;border:1px solid #2e7d4e;border-radius:8px;padding:10px;margin:10px 0}
 table{border-collapse:collapse;width:100%;max-width:760px;margin-top:8px}
 td,th{border-bottom:1px solid #262838;padding:8px 10px;text-align:left;font-size:14px}
 .on{color:#46d27e;font-weight:700} .off{color:#e74c3c} a{color:#f5c518}
 .card{background:#181a22;border:1px solid #262838;border-radius:12px;padding:16px;max-width:460px}
</style></head><body>
<h1>💙 Parceiros — Selo + Publipost</h1>
<p class=sub style="color:#9a9cab">O parceiro aparece TODO dia no "Bom dia, Vale" (selo + legenda) e ganha 1 publipost por semana (sexta 19h). Vários parceiros rotacionam.</p>
{% if msg %}<div class=msg>{{msg}}</div>{% endif %}
{% if semana %}<p>⭐ Parceiro DESTA semana no publipost: <b>{{semana.name}}</b></p>{% endif %}

<div class=card>
 <h2>Cadastrar parceiro</h2>
 <form method=post>
  <input type=hidden name=acao value=add>
  <input name=name placeholder="Nome do comércio (ex: Padaria do Zé)" required><br>
  <input name=instagram placeholder="@instagram (ou link)"><br>
  <input name=phone placeholder="Telefone / WhatsApp"><br>
  <input name=logo placeholder="URL do logo (opcional, https://...)"><br>
  <button type=submit>Cadastrar parceiro</button>
 </form>
</div>

<h2>Parceiros cadastrados ({{lista|length}})</h2>
<table>
 <tr><th>#</th><th>Nome</th><th>@ / Fone</th><th>Status</th><th></th></tr>
 {% for s in lista %}
 <tr>
  <td>{{s.id}}</td>
  <td>{{s.name}}</td>
  <td>{{s.instagram or ''}} {{('· '+s.phone) if s.phone else ''}}</td>
  <td>{% if s.active %}<span class=on>ATIVO</span>{% else %}<span class=off>pausado</span>{% endif %}</td>
  <td>
   <form method=post style="display:inline">
    <input type=hidden name=acao value=toggle><input type=hidden name=id value={{s.id}}>
    <input type=hidden name=active value="{{s.active}}">
    <button class=alt type=submit>{{'pausar' if s.active else 'ativar'}}</button></form>
   <form method=post style="display:inline" onsubmit="return confirm('Remover {{s.name}}?')">
    <input type=hidden name=acao value=remove><input type=hidden name=id value={{s.id}}>
    <button type=submit>remover</button></form>
  </td>
 </tr>
 {% endfor %}
</table>
<p style="margin-top:22px"><a href="/admin/saude">→ saúde</a> · <a href="/admin">← painel</a></p>
</body></html>"""


@app.route('/anuncie')
def anuncie():
    """Página pública de vendas (mídia kit + pacotes) — o 'outdoor 24h' pra fechar patrocinador local."""
    wpp = os.environ.get('ANUNCIE_WHATSAPP', '5547999999999')  # SEU número (set no Railway)
    msg = 'Olá! Quero anunciar no Rádio SC News.'
    wa = f"https://wa.me/{wpp}?text={msg.replace(' ', '%20')}"
    return render_template_string(_ANUNCIE_HTML, wa=wa)


_ANUNCIE_HTML = """<!doctype html><html lang=pt-br><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Anuncie no Rádio SC News — o Norte de SC em 1 minuto</title>
<style>
 body{background:#0f0f13;color:#eee;font-family:system-ui,Segoe UI,Arial;margin:0;line-height:1.55}
 .wrap{max-width:840px;margin:0 auto;padding:28px 22px}
 .pill{display:inline-block;background:#e74c3c;color:#fff;padding:4px 14px;border-radius:20px;font-size:13px;font-weight:700}
 h1{font-size:30px;margin:14px 0 6px;line-height:1.15}
 .sub{color:#9a9cab;font-size:16px;margin-bottom:24px}
 .stats{display:flex;flex-wrap:wrap;gap:14px;margin:18px 0 28px}
 .stat{background:#181a22;border:1px solid #262838;border-radius:14px;padding:16px 20px;flex:1;min-width:150px;text-align:center}
 .stat b{display:block;font-size:28px;color:#f5a623} .stat span{font-size:13px;color:#9a9cab}
 h2{font-size:20px;margin:30px 0 14px}
 .planos{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}
 .plano{background:#181a22;border:1px solid #262838;border-radius:16px;padding:22px}
 .plano.dest{border-color:#f5a623;box-shadow:0 0 0 1px #f5a623}
 .plano h3{margin:0 0 4px;font-size:18px} .plano .preco{font-size:30px;font-weight:800;color:#27ae60;margin:6px 0 12px}
 .plano .preco small{font-size:14px;color:#9a9cab;font-weight:400}
 .plano ul{list-style:none;padding:0;margin:0;font-size:14px} .plano li{padding:5px 0;border-bottom:1px solid #20222e}
 .plano li:before{content:"✓ ";color:#27ae60;font-weight:700}
 .cta{display:block;text-align:center;background:#27ae60;color:#fff;text-decoration:none;font-weight:800;font-size:18px;padding:16px;border-radius:14px;margin:30px 0 10px}
 .obs{color:#6f7180;font-size:13px;text-align:center}
</style></head><body><div class=wrap>
<span class=pill>📻 Rádio SC News</span>
<h1>Coloque sua marca na frente do Vale.</h1>
<div class=sub>O portal que o Norte de SC acompanha todo dia — Jaraguá do Sul · Schroeder · Guaramirim · Joinville · Corupá.</div>

<div class=stats>
 <div class=stat><b>+113 mil</b><span>visualizações por mês</span></div>
 <div class=stat><b>Norte de SC</b><span>público 100% local</span></div>
 <div class=stat><b>Diário</b><span>notícia, agenda e bom dia</span></div>
</div>

<h2>Escolha seu plano</h2>
<div class=planos>
 <div class=plano>
  <h3>🥉 Selo Patrocinador</h3>
  <div class=preco>R$ 197<small>/mês</small></div>
  <ul><li>Sua marca no "Bom dia, Vale" todo dia</li><li>Menção na legenda</li><li>Logo no rodapé</li></ul>
 </div>
 <div class="plano dest">
  <h3>🥈 Parceiro do Vale</h3>
  <div class=preco>R$ 397<small>/mês</small></div>
  <ul><li>Tudo do Selo</li><li>2 publiposts no mês</li><li>1 story por semana</li><li>Rotação de destaque</li></ul>
 </div>
 <div class=plano>
  <h3>🥇 Apresentador</h3>
  <div class=preco>R$ 697<small>/mês</small></div>
  <ul><li>Tudo do Parceiro</li><li>Publipost toda semana</li><li>"Agenda do Vale apresentada por você"</li><li>Prioridade total</li></ul>
 </div>
</div>

<a class=cta href="{{wa}}">📲 Quero anunciar — falar agora</a>
<div class=obs>Valores de lançamento. Pacotes personalizados sob consulta.</div>
</div></body></html>"""


@app.route('/admin/agenda', methods=['GET', 'POST'])
@login_required
def admin_agenda():
    """Cadastro da Agenda do Vale (festa de igreja, escola, show, feira...)."""
    import agenda
    msg = ""
    if request.method == 'POST':
        acao = request.form.get('acao')
        try:
            if acao == 'add':
                tit = (request.form.get('titulo') or '').strip()
                data = (request.form.get('data') or '').strip()
                if tit and data:
                    agenda.add_evento(tit, data, request.form.get('hora', ''),
                                      request.form.get('local', ''), request.form.get('cidade', ''))
                    msg = f"✅ Evento '{tit}' cadastrado!"
                else:
                    msg = "⚠️ Informe pelo menos título e data."
            elif acao == 'remove':
                agenda.remove_evento(request.form.get('id'))
                msg = "🗑️ Evento removido."
        except Exception as e:
            logger.error(f"admin_agenda: {e}")
            msg = f"erro: {e}"
    try:
        lista = agenda.list_eventos()
        proximos = len(agenda.eventos_proximos())
    except Exception:
        lista, proximos = [], 0
    return render_template_string(_AGENDA_HTML, lista=lista, msg=msg, proximos=proximos)


_AGENDA_HTML = """<!doctype html><html lang=pt-br><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Agenda do Vale · Rádio SC News</title>
<style>
 body{background:#11121a;color:#eee;font-family:system-ui,Segoe UI,Arial;margin:0;padding:24px;line-height:1.5}
 h1{font-size:20px} h2{font-size:15px;margin:18px 0 8px;color:#cfd0db}
 input{background:#181a22;border:1px solid #2a2c3c;color:#eee;border-radius:8px;padding:10px;margin:4px 0;width:100%;max-width:440px;box-sizing:border-box}
 button{background:#e74c3c;color:#fff;border:0;border-radius:8px;padding:9px 16px;cursor:pointer;font-weight:700}
 .msg{background:#16321f;border:1px solid #2e7d4e;border-radius:8px;padding:10px;margin:10px 0}
 table{border-collapse:collapse;width:100%;max-width:820px;margin-top:8px}
 td,th{border-bottom:1px solid #262838;padding:8px 10px;text-align:left;font-size:14px}
 a{color:#f5c518} .card{background:#181a22;border:1px solid #262838;border-radius:12px;padding:16px;max-width:480px}
 .sub{color:#9a9cab;font-size:13px}
</style></head><body>
<h1>📅 Agenda do Vale</h1>
<p class=sub>Festa de igreja, evento de escola, show, feira, missa, jogo... O motor monta o carrossel "Agenda do Vale" e posta toda quinta 12h. Conteúdo útil + patrocinável.</p>
{% if msg %}<div class=msg>{{msg}}</div>{% endif %}
<p>⏭️ Eventos nos próximos 10 dias: <b>{{proximos}}</b></p>

<div class=card>
 <h2>Cadastrar evento</h2>
 <form method=post>
  <input type=hidden name=acao value=add>
  <input name=titulo placeholder="Título (ex: Festa Junina da Igreja Matriz)" required><br>
  <input name=data type=date required><br>
  <input name=hora placeholder="Hora (ex: 19h)"><br>
  <input name=cidade placeholder="Cidade (ex: Schroeder)"><br>
  <input name=local placeholder="Local (ex: Salão Paroquial)"><br>
  <button type=submit>Cadastrar evento</button>
 </form>
</div>

<h2>Eventos cadastrados ({{lista|length}})</h2>
<table>
 <tr><th>Data</th><th>Hora</th><th>Evento</th><th>Cidade</th><th></th></tr>
 {% for e in lista %}
 <tr>
  <td>{{e.data_evento}}</td><td>{{e.hora or ''}}</td>
  <td>{{e.titulo}}</td><td>{{e.cidade or ''}}</td>
  <td><form method=post style="display:inline" onsubmit="return confirm('Remover?')">
   <input type=hidden name=acao value=remove><input type=hidden name=id value={{e.id}}>
   <button type=submit>remover</button></form></td>
 </tr>
 {% endfor %}
</table>
<p style="margin-top:22px"><a href="/admin/saude">→ saúde</a> · <a href="/admin/patrocinadores">→ parceiros</a> · <a href="/admin">← painel</a></p>
</body></html>"""


@app.route('/admin/collect', methods=['POST'])
@login_required
def admin_collect():
    """Coleta manual de notícias."""
    try:
        from scraper import collect_all
        total = collect_all()
        return jsonify({'success': True, 'new_news': total,
                        'message': f'{total} novas notícias coletadas.'})
    except Exception as e:
        logger.error(f"Erro na coleta: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/coletar-agora')
def api_coletar_agora():
    """Coleta emergencial de notícias — apenas com token de admin."""
    token = request.args.get('token', '')
    if token != _admin_pw_env:
        return jsonify({'error': 'unauthorized'}), 403
    try:
        from scraper import collect_all
        total = collect_all()
        conn = get_db()
        count = conn.execute('SELECT COUNT(*) FROM news WHERE active=1').fetchone()[0]
        conn.close()
        logger.info(f"Coleta emergencial via API: {total} novas, {count} total.")
        return jsonify({'success': True, 'novas': total, 'total_ativo': count})
    except Exception as e:
        logger.error(f"Erro na coleta emergencial: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/social-testar')
def api_social_testar():
    """Dispara um post de TESTE nas redes (IG+FB), ignorando a trava SOCIAL_AUTOPOST.
    Protegido por token de admin.
    Uso:  /api/social-testar?token=SENHA           -> posta a proxima noticia
          /api/social-testar?token=SENHA&tipo=bomdia -> posta o Bom dia Vale
    """
    token = request.args.get('token', '')
    if token != _admin_pw_env:
        return jsonify({'error': 'unauthorized'}), 403
    tipo = request.args.get('tipo', 'noticia')
    try:
        if tipo == 'bomdia':
            import bom_dia
            bom_dia.run(post=True)
            return jsonify({'success': True, 'tipo': 'bomdia',
                            'message': 'Bom dia Vale postado no IG+FB.'})
        if tipo == 'reel':
            # Reels demora pra processar no IG (pode passar do timeout do gunicorn).
            # Roda em segundo plano e responde na hora.
            import threading, reels

            def _job():
                try:
                    r = reels.run_reel(post=True, limit=1)
                    logger.info(f"🎬 Reels: postadas={r['postadas']} erros={r['erros']} seguradas={r.get('seguradas')}")
                except Exception as e:
                    logger.error(f"🎬 Reels falhou: {e}")

            threading.Thread(target=_job, daemon=True).start()
            return jsonify({'success': True, 'tipo': 'reel',
                            'status': 'gerando em segundo plano — aparece no Instagram em 1-3 min. '
                                      'Veja os logs do Railway para o resultado.'})
        import distribuidor
        if tipo == 'urgente':
            r = distribuidor.run_urgent(post=True, limit=1)
            return jsonify({'success': True, 'tipo': 'urgente',
                            'postadas': r['postadas'], 'erros': r['erros'],
                            'seguradas': r.get('seguradas', [])})
        r = distribuidor.run_once(post=True, limit=1)
        return jsonify({'success': True, 'tipo': 'noticia',
                        'postadas': r['postadas'], 'erros': r['erros'],
                        'seguradas': r.get('seguradas', [])})
    except Exception as e:
        logger.error(f"Erro no teste social: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/sponsor/<acao>')
def api_sponsor(acao):
    """Gestão do Selo Patrocinador (Bom dia, Vale). Protegido por token de admin.
       /api/sponsor/list?token=SENHA
       /api/sponsor/add?token=SENHA&name=Padaria%20X&logo=https://.../logo.png&phone=47999990000
       /api/sponsor/remove?token=SENHA&id=3
       /api/sponsor/toggle?token=SENHA&id=3&active=0
    """
    if request.args.get('token', '') != _admin_pw_env:
        return jsonify({'error': 'unauthorized'}), 403
    try:
        import sponsors as sp
        if acao == 'add':
            name = (request.args.get('name') or '').strip()
            if not name:
                return jsonify({'success': False, 'error': 'name obrigatorio'}), 400
            sid = sp.add_sponsor(name, request.args.get('logo', ''),
                                 request.args.get('phone', ''),
                                 request.args.get('instagram', ''))
            return jsonify({'success': True, 'id': sid, 'sponsors': sp.list_sponsors()})
        if acao == 'remove':
            sp.remove_sponsor(request.args.get('id'))
            return jsonify({'success': True, 'sponsors': sp.list_sponsors()})
        if acao == 'toggle':
            sp.set_active(request.args.get('id'), request.args.get('active', '1'))
            return jsonify({'success': True, 'sponsors': sp.list_sponsors()})
        # default: list
        return jsonify({'success': True, 'hoje': sp.sponsor_of_the_day(),
                        'sponsors': sp.list_sponsors()})
    except Exception as e:
        logger.error(f"Erro no sponsor/{acao}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/limpar-duplicadas')
def api_limpar_duplicadas():
    """Segura as noticias duplicadas que ja estao na fila (linhas repetidas do
    mesmo fato vindas de antes do dedup). Mantem 1 de cada cluster.
       /api/limpar-duplicadas?token=SENHA"""
    if request.args.get('token', '') != _admin_pw_env:
        return jsonify({'error': 'unauthorized'}), 403
    try:
        import distribuidor as d
        conn = d.get_db()
        d.ensure_column(conn)
        rows = conn.execute(
            "SELECT id, title FROM news WHERE active=1 "
            "AND (social_posted_at IS NULL OR social_posted_at='') "
            "AND (social_hold IS NULL OR social_hold='') "
            "ORDER BY datetime(published_at) DESC"
        ).fetchall()
        from datetime import datetime as _dt
        stamp = _dt.now().isoformat(timespec='seconds')
        kept, held = [], 0
        for r in rows:
            dup = None
            for k in kept:
                if d._overlap(r['title'] or '', k['title'] or '') >= 0.6:
                    dup = k['id']
                    break
            if dup:
                conn.execute("UPDATE news SET social_hold=? WHERE id=?",
                             (f"duplicada de #{dup} @ {stamp}", r['id']))
                held += 1
            else:
                kept.append(r)
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'duplicadas_seguradas': held,
                        'noticias_unicas_na_fila': len(kept)})
    except Exception as e:
        logger.error(f"Erro limpar-duplicadas: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/marca-testar')
def api_marca_testar():
    """Posta um conteúdo de teste de uma MARCA (Despachante/4kitem/DL). Em 2º plano.
       /api/marca-testar?token=SENHA&brand=despachante"""
    if request.args.get('token', '') != _admin_pw_env:
        return jsonify({'error': 'unauthorized'}), 403
    brand = request.args.get('brand', 'despachante')
    try:
        import threading, marcas
        if brand not in marcas.BRANDS:
            return jsonify({'success': False, 'error': f'marca {brand} nao existe',
                            'disponiveis': list(marcas.BRANDS)}), 400

        def _job():
            try:
                marcas.run(brand, post=True)
                logger.info(f"🏷️ Marca {brand}: postado.")
            except Exception as e:
                logger.error(f"🏷️ Marca {brand} falhou: {e}")

        threading.Thread(target=_job, daemon=True).start()
        return jsonify({'success': True, 'brand': brand,
                        'status': 'gerando e postando em segundo plano — veja o Instagram em ~1 min.'})
    except Exception as e:
        logger.error(f"Erro marca-testar: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/canal/done')
def canal_done():
    """Marca uma noticia como 'ja postada no Canal do WhatsApp'."""
    if request.args.get('token', '') != _admin_pw_env:
        return jsonify({'error': 'unauthorized'}), 403
    try:
        import distribuidor, sqlite3
        from datetime import datetime as _dt
        conn = distribuidor.get_db()
        distribuidor.ensure_column(conn)
        conn.execute("UPDATE news SET channel_posted_at=? WHERE id=?",
                     (_dt.now().isoformat(timespec='seconds'), request.args.get('id')))
        conn.commit()
        conn.close()
        return redirect(f"/canal?token={request.args.get('token')}")
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/canal')
def canal_central():
    """Central do Canal: mensagens prontas (texto + midia) p/ colar no Canal do WhatsApp.
       Acesso: /canal?token=SENHA"""
    import html as _html
    if request.args.get('token', '') != _admin_pw_env:
        return "<h3>Acesso negado</h3>", 403
    token = request.args.get('token')
    import distribuidor
    conn = distribuidor.get_db()
    distribuidor.ensure_column(conn)
    pend = conn.execute(
        "SELECT id, title, city, zap_text, social_media FROM news "
        "WHERE zap_text IS NOT NULL AND zap_text!='' "
        "AND (channel_posted_at IS NULL OR channel_posted_at='') "
        "ORDER BY social_posted_at DESC LIMIT 25"
    ).fetchall()
    feitos = conn.execute(
        "SELECT COUNT(*) FROM news WHERE channel_posted_at IS NOT NULL AND channel_posted_at!=''"
    ).fetchone()[0]
    conn.close()

    canal_url = distribuidor.WHATSAPP_CHANNEL
    cards = []

    # card fixo do Bom dia, Vale (se gerado hoje)
    try:
        import json, os as _os
        bj = _os.path.join("static", "social", "bomdia_latest.json")
        if _os.path.exists(bj):
            with open(bj, encoding="utf-8") as f:
                bd = json.load(f)
            bzap = _html.escape(bd.get("zap", ""))
            bmedia = bd.get("media", "")
            cards.append(f"""
            <div class="card" style="border-color:#f5c518">
              <div class="cidade">☀️ BOM DIA, VALE — {_html.escape(bd.get('data',''))}</div>
              <div class="media"><img src="{bmedia}" style="max-width:100%;border-radius:10px" onerror="this.style.display='none'"></div>
              <textarea id="tbd" readonly>{bzap}</textarea>
              <div class="row">
                <button class="btn" onclick="copiar('bd')">📋 Copiar texto</button>
                <a class="btn ghost" href="{bmedia}" download target="_blank">⬇️ Baixar mídia</a>
              </div>
            </div>""")
    except Exception:
        pass

    for r in pend:
        zap = _html.escape(r["zap_text"] or "")
        media = r["social_media"] or ""
        is_video = media.lower().endswith(".mp4")
        thumb = (f'<video src="{media}" controls style="max-width:100%;border-radius:10px"></video>'
                 if is_video else
                 f'<img src="{media}" style="max-width:100%;border-radius:10px" '
                 f'onerror="this.style.display=\'none\'">')
        if is_video:
            thumb += ('<div style="color:#a8aab4;font-size:13px;margin-top:6px">'
                      '🎵 Este vídeo serve pro <b>Canal do WhatsApp</b> E pro <b>TikTok</b> '
                      '— baixe e poste nos dois.</div>')
        baixar = (f'<a class="btn ghost" href="{media}" download target="_blank">⬇️ Baixar '
                  f'{"(Canal + TikTok)" if is_video else "mídia"}</a>') if media else ""
        cards.append(f"""
        <div class="card">
          <div class="cidade">📍 {_html.escape(r['city'] or '')}</div>
          <h3>{_html.escape(r['title'] or '')}</h3>
          <div class="media">{thumb}</div>
          <textarea id="t{r['id']}" readonly>{zap}</textarea>
          <div class="row">
            <button class="btn" onclick="copiar({r['id']})">📋 Copiar texto</button>
            {baixar}
            <a class="btn done" href="/canal/done?token={token}&id={r['id']}">✅ Já postei</a>
          </div>
        </div>""")

    body = "".join(cards) or '<p class="vazio">🎉 Tudo postado no Canal! Nada pendente.</p>'
    pagina = f"""<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Central do Canal — Rádio SC News</title>
    <style>
      :root{{--red:#e74c3c;--gold:#f5c518;--bg:#111218;--card:#1b1d26;--muted:#a8aab4}}
      *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:#eee;
        font-family:-apple-system,Segoe UI,Roboto,sans-serif;padding:16px;max-width:680px;margin:auto}}
      header{{position:sticky;top:0;background:var(--bg);padding:10px 0 14px;border-bottom:1px solid #2a2d3a}}
      h1{{font-size:20px;margin:0}} .sub{{color:var(--muted);font-size:13px;margin-top:4px}}
      .abrir{{display:inline-block;margin-top:10px;background:#25D366;color:#053;
        padding:10px 14px;border-radius:10px;text-decoration:none;font-weight:700}}
      .card{{background:var(--card);border-radius:14px;padding:14px;margin:14px 0;border:1px solid #2a2d3a}}
      .cidade{{color:var(--gold);font-size:13px;font-weight:700}}
      h3{{font-size:16px;margin:6px 0 10px}}
      textarea{{width:100%;min-height:130px;background:#0d0e13;color:#eee;border:1px solid #2a2d3a;
        border-radius:10px;padding:10px;font-size:14px;resize:vertical}}
      .media{{margin:6px 0 10px}} .row{{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}}
      .btn{{background:var(--red);color:#fff;border:0;padding:11px 14px;border-radius:10px;
        font-weight:700;cursor:pointer;text-decoration:none;font-size:14px;display:inline-block}}
      .btn.ghost{{background:#2a2d3a}} .btn.done{{background:#2e7d32}}
      .vazio{{text-align:center;color:var(--muted);padding:40px}}
      .ok{{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#2e7d32;
        color:#fff;padding:12px 18px;border-radius:10px;opacity:0;transition:.3s;pointer-events:none}}
      .ok.show{{opacity:1}}
    </style></head><body>
    <header>
      <h1>📲 Central do Canal</h1>
      <div class="sub">Copie o texto → abra o Canal → cole + anexe a mídia. ({len(pend)} pendente(s) · {feitos} já enviados)</div>
      <a class="abrir" href="{canal_url}" target="_blank">➡️ Abrir o Canal do WhatsApp</a>
    </header>
    {body}
    <div class="ok" id="ok">✅ Texto copiado!</div>
    <script>
      function copiar(id){{
        var t=document.getElementById('t'+id);
        navigator.clipboard.writeText(t.value).then(function(){{
          var o=document.getElementById('ok'); o.classList.add('show');
          setTimeout(function(){{o.classList.remove('show')}},1500);
        }});
      }}
    </script></body></html>"""
    return pagina


@app.route('/revisar/aprovar')
def revisar_aprovar():
    """Aprova e POSTA uma materia segurada (roda em segundo plano)."""
    if request.args.get('token', '') != _admin_pw_env:
        return jsonify({'error': 'unauthorized'}), 403
    nid = request.args.get('id')
    try:
        import threading, distribuidor

        def _job():
            try:
                r = distribuidor.post_specific(nid)
                logger.info(f"✅ Revisao: materia {nid} aprovada -> {r}")
            except Exception as e:
                logger.error(f"Revisao aprovar {nid} falhou: {e}")

        threading.Thread(target=_job, daemon=True).start()
        return redirect(f"/revisar?token={request.args.get('token')}&msg=aprovada")
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/revisar/descartar')
def revisar_descartar():
    """Descarta uma materia segurada (nao posta, sai da fila)."""
    if request.args.get('token', '') != _admin_pw_env:
        return jsonify({'error': 'unauthorized'}), 403
    try:
        import distribuidor
        from datetime import datetime as _dt
        conn = distribuidor.get_db()
        distribuidor.ensure_column(conn)
        conn.execute("UPDATE news SET social_hold=? WHERE id=?",
                     (f"descartada @ {_dt.now().isoformat(timespec='seconds')}",
                      request.args.get('id')))
        conn.commit()
        conn.close()
        return redirect(f"/revisar?token={request.args.get('token')}&msg=descartada")
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/revisar')
def revisar_fila():
    """Fila de Revisao: materias seguradas pelo filtro editorial (tema sensivel).
       Acesso: /revisar?token=SENHA"""
    import html as _html
    if request.args.get('token', '') != _admin_pw_env:
        return "<h3>Acesso negado</h3>", 403
    token = request.args.get('token')
    import distribuidor
    conn = distribuidor.get_db()
    distribuidor.ensure_column(conn)
    rows = conn.execute(
        "SELECT id, title, city, summary, image_url, social_hold FROM news "
        "WHERE social_hold LIKE 'sensivel%' "
        "AND (social_posted_at IS NULL OR social_posted_at='') "
        "ORDER BY datetime(published_at) DESC LIMIT 40"
    ).fetchall()
    conn.close()

    cards = []
    for r in rows:
        motivo = _html.escape((r["social_hold"] or "").replace("sensivel:", "").split("@")[0].strip())
        img = (f'<img src="{r["image_url"]}" style="max-width:100%;border-radius:10px" '
               f'onerror="this.style.display=\'none\'">' if r["image_url"] else "")
        resumo = _html.escape((r["summary"] or "")[:240])
        cards.append(f"""
        <div class="card">
          <div class="tag">⚠️ segurada — termo: <b>{motivo}</b></div>
          <div class="cidade">📍 {_html.escape(r['city'] or '')}</div>
          <h3>{_html.escape(r['title'] or '')}</h3>
          <div class="media">{img}</div>
          <p class="resumo">{resumo}</p>
          <div class="row">
            <a class="btn ok" href="/revisar/aprovar?token={token}&id={r['id']}"
               onclick="return confirm('Aprovar e POSTAR esta materia no Instagram e Facebook?')">✅ Aprovar e postar</a>
            <a class="btn no" href="/revisar/descartar?token={token}&id={r['id']}"
               onclick="return confirm('Descartar? Nao sera postada.')">🗑️ Descartar</a>
          </div>
        </div>""")

    body = "".join(cards) or '<p class="vazio">🎉 Nada na fila. Nenhuma matéria segurada pendente.</p>'
    msg = request.args.get('msg', '')
    aviso = ''
    if msg == 'aprovada':
        aviso = '<div class="flash">✅ Aprovada! Postando em segundo plano (aparece em ~1 min).</div>'
    elif msg == 'descartada':
        aviso = '<div class="flash">🗑️ Descartada.</div>'

    pagina = f"""<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Fila de Revisão — Rádio SC News</title>
    <style>
      :root{{--red:#e74c3c;--gold:#f5c518;--bg:#111218;--card:#1b1d26;--muted:#a8aab4}}
      *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:#eee;
        font-family:-apple-system,Segoe UI,Roboto,sans-serif;padding:16px;max-width:680px;margin:auto}}
      header{{position:sticky;top:0;background:var(--bg);padding:10px 0 14px;border-bottom:1px solid #2a2d3a;z-index:5}}
      h1{{font-size:20px;margin:0}} .sub{{color:var(--muted);font-size:13px;margin-top:4px}}
      .card{{background:var(--card);border-radius:14px;padding:14px;margin:14px 0;border:1px solid #3a2a2a}}
      .tag{{color:#ff9; font-size:13px}} .cidade{{color:var(--gold);font-size:13px;font-weight:700;margin-top:6px}}
      h3{{font-size:16px;margin:6px 0 10px}} .resumo{{color:var(--muted);font-size:14px}}
      .media{{margin:6px 0 10px}} .row{{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}}
      .btn{{color:#fff;border:0;padding:12px 14px;border-radius:10px;font-weight:700;
        cursor:pointer;text-decoration:none;font-size:14px;display:inline-block}}
      .btn.ok{{background:#2e7d32}} .btn.no{{background:#555}}
      .vazio{{text-align:center;color:var(--muted);padding:40px}}
      .flash{{background:#2e7d32;padding:10px 14px;border-radius:10px;margin:10px 0}}
    </style></head><body>
    <header>
      <h1>🗂️ Fila de Revisão</h1>
      <div class="sub">Matérias seguradas pelo filtro (tema sensível). Aprove ou descarte. ({len(rows)} na fila)</div>
    </header>
    {aviso}
    {body}
    </body></html>"""
    return pagina


@app.route('/admin/fix_sports', methods=['POST'])
@login_required
def admin_fix_sports():
    """Recategoriza como esporte notícias de fontes esportivas mal categorizadas."""
    SPORT_SOURCES = ('GE Futebol', 'GE Brasileirão', 'Gazeta Esportiva', 'Lance!')
    placeholders = ','.join('?' * len(SPORT_SOURCES))
    conn = get_db()
    result = conn.execute(
        f"UPDATE news SET category='esporte' WHERE source IN ({placeholders}) AND category != 'esporte'",
        SPORT_SOURCES
    )
    fixed = result.rowcount
    conn.commit()
    conn.close()
    logger.info(f"fix_sports: {fixed} notícias recategorizadas como esporte.")
    return jsonify({'success': True, 'fixed': fixed, 'message': f'{fixed} notícias corrigidas para esporte.'})


@app.route('/admin/generate_audio/<int:news_id>', methods=['POST'])
@login_required
def admin_generate_audio(news_id):
    """Gera áudio para uma notícia específica."""
    conn = get_db()
    news = conn.execute('SELECT * FROM news WHERE id=?', (news_id,)).fetchone()
    conn.close()
    
    if not news:
        return jsonify({'success': False, 'message': 'Notícia não encontrada.'}), 404
    
    try:
        from tts_engine import generate_audio
        audio_file = generate_audio(
            title=news['title'],
            summary=news['summary'] or '',
            source=news['source'],
            city=news['city'],
            news_id=news_id,
            category=news['category']
        )
        if audio_file:
            conn = get_db()
            conn.execute('UPDATE news SET audio_file=? WHERE id=?', (audio_file, news_id))
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'audio_file': audio_file})
        else:
            return jsonify({'success': False, 'message': 'Falha ao gerar áudio.'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/admin/clear_audio_cache', methods=['POST'])
@login_required
def admin_clear_audio_cache():
    """Apaga todos os áudios gerados e limpa o campo audio_file no banco.
    Use isso para forçar regerar com novas vozes."""
    conn = get_db()
    news_with_audio = conn.execute(
        'SELECT id, audio_file FROM news WHERE audio_file IS NOT NULL'
    ).fetchall()
    deleted_files = 0
    for row in news_with_audio:
        filepath = os.path.join(AUDIO_DIR, row['audio_file'])
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                deleted_files += 1
            except Exception:
                pass
    conn.execute('UPDATE news SET audio_file = NULL WHERE audio_file IS NOT NULL')
    conn.commit()
    conn.close()
    logger.info(f"Cache de áudio limpo: {deleted_files} arquivos removidos.")
    return jsonify({'success': True, 'deleted_files': deleted_files,
                    'message': f'{deleted_files} arquivos de áudio removidos. Novos áudios serão gerados com as vozes atuais.'})


@app.route('/admin/generate_all_audio', methods=['POST'])
@login_required
def admin_generate_all_audio():
    """Gera áudio para todas as notícias sem áudio."""
    conn = get_db()
    pending = conn.execute(
        'SELECT * FROM news WHERE audio_file IS NULL AND active=1 ORDER BY priority DESC, published_at DESC LIMIT 20'
    ).fetchall()
    conn.close()

    from tts_engine import generate_audio
    generated = 0
    for news in pending:
        try:
            audio_file = generate_audio(
                title=news['title'],
                summary=news['summary'] or '',
                source=news['source'],
                city=news['city'],
                news_id=news['id'],
                category=news['category']
            )
            if audio_file:
                conn = get_db()
                conn.execute('UPDATE news SET audio_file=? WHERE id=?', (audio_file, news['id']))
                conn.commit()
                conn.close()
                generated += 1
        except Exception as e:
            logger.error(f"Erro ao gerar áudio para notícia {news['id']}: {e}")

    return jsonify({'success': True, 'generated': generated, 'pending': len(pending)})


@app.route('/admin/news/create', methods=['POST'])
@login_required
def admin_create_news():
    """Cria notícia manualmente."""
    data = request.form
    title   = data.get('title', '').strip()
    summary = data.get('summary', '').strip()
    source  = data.get('source', 'Redação').strip()
    city    = data.get('city', 'Schroeder').strip()
    category = data.get('category', 'geral').strip()
    link    = data.get('link', '').strip()

    if not title:
        return jsonify({'success': False, 'message': 'Título obrigatório.'}), 400

    # Upload de imagem opcional
    admin_image = None
    if 'image' in request.files:
        f = request.files['image']
        if f and f.filename and allowed_file(f.filename):
            fname = secure_filename(f.filename)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S_')
            fname = ts + fname
            f.save(os.path.join(UPLOAD_DIR, fname))
            admin_image = fname

    conn = get_db()
    cur = conn.execute('''
        INSERT INTO news (title, summary, link, source, city, category,
                          admin_image, priority, published_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
    ''', (title, summary, link or None, source, city, category,
          admin_image, datetime.now().isoformat(), datetime.now().isoformat()))
    news_id = cur.lastrowid
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'news_id': news_id})


@app.route('/admin/news/delete/<int:news_id>', methods=['POST'])
@login_required
def admin_delete_news(news_id):
    conn = get_db()
    conn.execute('UPDATE news SET active=0 WHERE id=?', (news_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/admin/news/upload_image/<int:news_id>', methods=['POST'])
@login_required
def admin_upload_image(news_id):
    """Faz upload de imagem para uma notícia existente."""
    if 'image' not in request.files:
        return jsonify({'success': False, 'message': 'Nenhuma imagem enviada.'}), 400
    
    f = request.files['image']
    if not f or not f.filename or not allowed_file(f.filename):
        return jsonify({'success': False, 'message': 'Arquivo inválido.'}), 400

    fname = secure_filename(f.filename)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S_')
    fname = f'news_{news_id}_{ts}{fname}'
    f.save(os.path.join(UPLOAD_DIR, fname))

    conn = get_db()
    conn.execute('UPDATE news SET admin_image=? WHERE id=?', (fname, news_id))
    conn.execute('INSERT INTO media (filename, type, news_id) VALUES (?, "image", ?)',
                 (fname, news_id))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'filename': fname, 'url': f'/uploads/{fname}'})


# ──────────────────────────────────────────────
# Rotas Admin — Propagandas
# ──────────────────────────────────────────────
@app.route('/admin/ads/create', methods=['POST'])
@login_required
def admin_create_ad():
    data  = request.form
    title = data.get('title', '').strip()
    text  = data.get('text', '').strip()
    link  = data.get('link', '').strip()

    if not title:
        return jsonify({'success': False, 'message': 'Título obrigatório.'}), 400

    image = None
    if 'image' in request.files:
        f = request.files['image']
        if f and f.filename and allowed_file(f.filename):
            fname = secure_filename(f.filename)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S_ad_')
            fname = ts + fname
            f.save(os.path.join(UPLOAD_DIR, fname))
            image = fname

    conn = get_db()
    cur = conn.execute('''
        INSERT INTO ads (title, text, image, link, active, show_in_feed, created_at)
        VALUES (?, ?, ?, ?, 1, 1, ?)
    ''', (title, text, image, link or None, datetime.now().isoformat()))
    ad_id = cur.lastrowid
    conn.commit()
    conn.close()

    # Gerar áudio da propaganda (se tiver texto)
    if text:
        try:
            from tts_engine import generate_audio_for_ad
            audio = generate_audio_for_ad(f"{title}. {text}", ad_id)
            if audio:
                conn = get_db()
                conn.execute('UPDATE ads SET audio_file=? WHERE id=?', (audio, ad_id))
                conn.commit()
                conn.close()
        except Exception as e:
            logger.warning(f"Não foi possível gerar áudio da propaganda: {e}")

    return jsonify({'success': True, 'ad_id': ad_id})


@app.route('/admin/ads/toggle/<int:ad_id>', methods=['POST'])
@login_required
def admin_toggle_ad(ad_id):
    conn = get_db()
    ad = conn.execute('SELECT active FROM ads WHERE id=?', (ad_id,)).fetchone()
    if not ad:
        conn.close()
        return jsonify({'success': False}), 404
    new_state = 0 if ad['active'] else 1
    conn.execute('UPDATE ads SET active=? WHERE id=?', (new_state, ad_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'active': new_state})


@app.route('/admin/ads/delete/<int:ad_id>', methods=['POST'])
@login_required
def admin_delete_ad(ad_id):
    conn = get_db()
    conn.execute('DELETE FROM ads WHERE id=?', (ad_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/admin/media/upload', methods=['POST'])
@login_required
def admin_upload_media():
    """Upload de mídia avulsa (sem notícia vinculada)."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Nenhum arquivo.'}), 400
    
    f = request.files['file']
    caption = request.form.get('caption', '')
    
    if not f or not f.filename or not allowed_file(f.filename):
        return jsonify({'success': False, 'message': 'Arquivo inválido.'}), 400

    fname = secure_filename(f.filename)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S_')
    fname = ts + fname
    f.save(os.path.join(UPLOAD_DIR, fname))

    conn = get_db()
    conn.execute(
        'INSERT INTO media (filename, type, caption) VALUES (?, "image", ?)',
        (fname, caption)
    )
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'filename': fname, 'url': f'/uploads/{fname}'})


@app.route('/admin/media/delete/<int:media_id>', methods=['POST'])
@login_required
def admin_delete_media(media_id):
    conn = get_db()
    media = conn.execute('SELECT filename FROM media WHERE id=?', (media_id,)).fetchone()
    if media:
        filepath = os.path.join(UPLOAD_DIR, media['filename'])
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass
        conn.execute('DELETE FROM media WHERE id=?', (media_id,))
        conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/admin/scheduler_status')
@login_required
def admin_scheduler_status():
    from scheduler import get_scheduler_status
    return jsonify(get_scheduler_status())


# ──────────────────────────────────────────────
# Inicialização
# ──────────────────────────────────────────────
def background_startup():
    """Coleta inicial e scheduler rodam em background para não atrasar o start."""
    import time
    time.sleep(3)  # aguarda o servidor subir
    try:
        from scheduler import start_scheduler
        start_scheduler(interval_minutes=60)
    except Exception as e:
        logger.warning(f"Scheduler não iniciado: {e}")

    try:
        conn = get_db()
        count = conn.execute('SELECT COUNT(*) FROM news WHERE active=1').fetchone()[0]
        conn.close()
        if count < 10:
            logger.info(f"Banco com {count} notícias ativas — fazendo coleta automática de emergência...")
            from scraper import collect_all
            total = collect_all()
            logger.info(f"Coleta de emergência: {total} novas notícias coletadas.")
        else:
            logger.info(f"Banco OK: {count} notícias ativas.")
    except Exception as e:
        logger.warning(f"Coleta inicial falhou: {e}")

    # Live-check is handled by the APScheduler job in scheduler.py (every 10 minutes)


# ── YouTube Channels ──────────────────────────────────────────
# Canais pré-configurados semeados na primeira inicialização
CURATED_YT_CHANNELS = [
    # Economia — os mais vistos do Brasil
    {'name': 'Primo Rico',          'channel_id': 'UCT4nDeU5pv1XIGySbSK-GgA', 'category': 'economia', 'sort_order': 1},
    {'name': 'Bruno Perini',        'channel_id': 'UCCE-jo1GvBJqyj1b287h7jA', 'category': 'economia', 'sort_order': 2},
    {'name': 'Investidor Sardinha', 'channel_id': 'UCM3vJxmuJJkk1r0yzFI9eZg', 'category': 'economia', 'sort_order': 3},
    {'name': 'Empiricus',           'channel_id': 'UCu79AeVqrq42vmSIp1OHyfA', 'category': 'economia', 'sort_order': 4},
    {'name': 'Ancapsu',             'channel_id': 'UCLTWPE7XrHEe8m_xAmNbQ-Q', 'category': 'economia', 'sort_order': 5},
    # Política — direita + neutro, ano eleitoral 2026
    {'name': 'Nikolas Ferreira',    'channel_id': 'UCxI9vN6UbxmBt8VIvUKtJaA', 'category': 'politica', 'sort_order': 6},
    {'name': 'Romeu Zema',          'channel_id': 'UCBY16QLJLEUEjwzc-V09tKg', 'category': 'politica', 'sort_order': 7},
    {'name': 'Os Pingos nos Is',    'channel_id': 'UCzjtGnD7qqeaHW3nvDVrjQA', 'category': 'politica', 'sort_order': 8},
    {'name': 'Jovem Pan News',      'channel_id': 'UCP391YRAjSOdM_bwievgaZA', 'category': 'politica', 'sort_order': 9},
    {'name': 'CNN Brasil',          'channel_id': 'UCvdwhh_fDyWccR42-rReZLw', 'category': 'politica', 'sort_order': 10},
    # Notícias
    {'name': 'Record News',         'channel_id': 'UCuiLR4p6wQ3xLEm15pEn1Xw', 'category': 'noticias', 'sort_order': 11},
    {'name': 'Brasil Paralelo',     'channel_id': 'UCKDjjeeBmdaiicey2nImISw',  'category': 'noticias', 'sort_order': 12},
    {'name': 'Portal R7',           'channel_id': 'UCIwRd7CNbYcTUp-VCtMqkDw', 'category': 'noticias', 'sort_order': 13},
    # Regional Norte de SC
    {'name': 'Jornal Razão',        'channel_id': 'UCLS4wwx81rvrCCVCyr52GCQ', 'category': 'noticias', 'sort_order': 14},
    # Gospel / Fé
    {'name': 'Frei Gilson',         'channel_id': 'UCbh6_TmFnAJLI56aAQeD3qw', 'category': 'gospel',   'sort_order': 15},
]

_yt_videos_cache = {'data': None, 'ts': 0}
YT_CACHE_TTL = 900  # 15 minutos


def seed_youtube_channels():
    """Semeia canais curados se a tabela estiver vazia; aplica migrações se já existe."""
    conn = get_db()
    count = conn.execute('SELECT COUNT(*) FROM youtube_channels').fetchone()[0]
    if count == 0:
        for ch in CURATED_YT_CHANNELS:
            try:
                conn.execute('''
                    INSERT OR IGNORE INTO youtube_channels
                    (name, channel_id, category, active, sort_order, created_at)
                    VALUES (?, ?, ?, 1, ?, ?)
                ''', (ch['name'], ch['channel_id'], ch['category'],
                      ch['sort_order'], datetime.now().isoformat()))
            except Exception:
                pass
        conn.commit()
        logger.info(f"YouTube: {len(CURATED_YT_CHANNELS)} canais pré-configurados inseridos.")
    else:
        # ── Migrações cumulativas ──────────────────────────────────────────
        changes = 0

        # 1. Remove canais problemáticos/substituídos
        to_remove = [
            'UCmArkwjUI8VRHudOjEsVCUw',  # Paulo Kogos → Empiricus
            'UCkR6xPOHhpjq3wnFchVI4sg',  # Eduardo Bolsonaro (RSS quebrado)
            'UCb9T91q727Ld4c3lqq3w6Xw',  # Instituto Mises Brasil (83K subs)
            'UC8hGUtfEgvvnp6IaHSAg1OQ',  # Jair Bolsonaro (inativo desde jul/2025)
        ]
        for cid in to_remove:
            row = conn.execute(
                'SELECT id FROM youtube_channels WHERE channel_id=?', (cid,)
            ).fetchone()
            if row:
                conn.execute('DELETE FROM youtube_channels WHERE id=?', (row['id'],))
                changes += 1

        # Remove também por nome (cobre canais adicionados manualmente via admin)
        to_remove_by_name = ['Flávio Bolsonaro', 'Flavio Bolsonaro']
        for name in to_remove_by_name:
            conn.execute('DELETE FROM youtube_channels WHERE LOWER(name)=LOWER(?)', (name,))

        # 2. Insere canais novos que não existem ainda
        to_add = [
            ('Primo Rico',          'UCT4nDeU5pv1XIGySbSK-GgA', 'economia', 1),
            ('Bruno Perini',        'UCCE-jo1GvBJqyj1b287h7jA', 'economia', 2),
            ('Investidor Sardinha', 'UCM3vJxmuJJkk1r0yzFI9eZg', 'economia', 3),
            ('Os Pingos nos Is',    'UCzjtGnD7qqeaHW3nvDVrjQA', 'politica', 8),
            ('CNN Brasil',          'UCvdwhh_fDyWccR42-rReZLw',  'politica', 10),
            ('Jornal Razão',        'UCLS4wwx81rvrCCVCyr52GCQ', 'noticias', 14),
            ('Frei Gilson',         'UCbh6_TmFnAJLI56aAQeD3qw', 'gospel',   15),
        ]
        for name, cid, cat, order in to_add:
            exists = conn.execute(
                'SELECT id FROM youtube_channels WHERE channel_id=?', (cid,)
            ).fetchone()
            if not exists:
                conn.execute('''
                    INSERT OR IGNORE INTO youtube_channels
                    (name, channel_id, category, active, sort_order, created_at)
                    VALUES (?, ?, ?, 1, ?, ?)
                ''', (name, cid, cat, order, datetime.now().isoformat()))
                changes += 1

        # 3. Garante sort_orders corretos nos canais existentes
        order_map = {ch['channel_id']: ch['sort_order'] for ch in CURATED_YT_CHANNELS}
        for cid, order in order_map.items():
            conn.execute(
                'UPDATE youtube_channels SET sort_order=? WHERE channel_id=?',
                (order, cid)
            )

        if changes:
            conn.commit()
            logger.info(f"YouTube: {changes} mudança(s) aplicada(s) na migração.")
    conn.close()


def fetch_yt_rss(channel_id, max_videos=5):
    """Busca últimos vídeos de um canal YouTube via RSS (sem API key)."""
    import feedparser, requests as _req
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    _UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
           'AppleWebKit/537.36 (KHTML, like Gecko) '
           'Chrome/124.0.0.0 Safari/537.36')
    try:
        # Fetch com requests primeiro para evitar bloqueio de UA do feedparser
        resp = _req.get(url, headers={'User-Agent': _UA}, timeout=10)
        feed = feedparser.parse(resp.content if resp.status_code == 200 else url)
        videos = []
        for entry in feed.entries[:max_videos]:
            vid_id = getattr(entry, 'yt_videoid', None)
            if not vid_id:
                link = getattr(entry, 'link', '')
                if 'v=' in link:
                    vid_id = link.split('v=')[1].split('&')[0]
            if not vid_id:
                continue
            published = getattr(entry, 'published', '')
            try:
                from datetime import datetime as _dt
                pub = _dt.fromisoformat(published.replace('Z', '+00:00'))
                published_fmt = pub.strftime('%d/%m/%Y')
            except Exception:
                published_fmt = published[:10] if published else ''
            videos.append({
                'video_id': vid_id,
                'title': entry.get('title', ''),
                'published': published,
                'published_fmt': published_fmt,
                'thumbnail': f"https://i.ytimg.com/vi/{vid_id}/mqdefault.jpg",
                'embed_url': f"https://www.youtube.com/embed/{vid_id}?autoplay=1&rel=0",
                'watch_url': f"https://www.youtube.com/watch?v={vid_id}",
            })
        return videos
    except Exception as e:
        logger.warning(f"Erro RSS YouTube {channel_id}: {e}")
        return []


@app.route('/api/youtube-videos')
def api_youtube_videos():
    """Retorna vídeos recentes dos canais YouTube configurados (cache 15 min)."""
    global _yt_videos_cache
    import time as _t
    now = _t.time()
    category = request.args.get('category', '')
    force = request.args.get('force', '')

    if not force and _yt_videos_cache['data'] and now - _yt_videos_cache['ts'] < YT_CACHE_TTL:
        data = _yt_videos_cache['data']
        filtered = [ch for ch in data if ch['category'] == category] if category else data
        return jsonify({'channels': filtered, 'cached': True})

    conn = get_db()
    channels = conn.execute(
        'SELECT * FROM youtube_channels WHERE active=1 ORDER BY sort_order, name'
    ).fetchall()
    conn.close()

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _fetch_one(ch):
        try:
            videos = fetch_yt_rss(ch['channel_id'], max_videos=5)
        except Exception:
            videos = []
        return {
            'id': ch['id'],
            'name': ch['name'],
            'channel_id': ch['channel_id'],
            'category': ch['category'],
            'sort_order': ch['sort_order'] if 'sort_order' in ch.keys() else 0,
            'videos': videos,
        }

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch_one, ch): ch for ch in channels}
        result_map = {}
        for fut in as_completed(futures, timeout=20):
            try:
                item = fut.result()
                result_map[item['id']] = item
            except Exception:
                pass

    # Reconstrói na ordem original
    result = [result_map[ch['id']] for ch in channels if ch['id'] in result_map]

    _yt_videos_cache = {'data': result, 'ts': now}
    filtered = [ch for ch in result if ch['category'] == category] if category else result
    return jsonify({'channels': filtered, 'cached': False})


# ── Serve Service Worker na raiz (escopo total do site) ──
@app.route('/sw.js')
def service_worker():
    return send_from_directory('static', 'sw.js',
                               mimetype='application/javascript')


# ══════════════════════════════════════════════════════════════
# CLASSIFICADOS (Anúncios do público)
# ══════════════════════════════════════════════════════════════
CLASSIFIED_CATEGORIES = {
    'veiculos': {'label': 'Veículos',         'emoji': '🚗'},
    'imoveis':  {'label': 'Imóveis',          'emoji': '🏠'},
    'moveis':   {'label': 'Móveis & Eletros', 'emoji': '🛋️'},
    'empregos': {'label': 'Empregos',         'emoji': '💼'},
    'servicos': {'label': 'Serviços',         'emoji': '🔧'},
    'pets':     {'label': 'Pets',             'emoji': '🐾'},
    'outros':   {'label': 'Outros',           'emoji': '📦'},
}

CLASSIFIED_CITIES = ['Schroeder', 'Jaraguá do Sul', 'Guaramirim',
                     'Joinville', 'Corupá', 'Outra cidade']


def fmt_whatsapp(raw):
    """Limpa número e garante formato 55DDDNNNNNNNNN."""
    digits = ''.join(c for c in (raw or '') if c.isdigit())
    if not digits.startswith('55'):
        digits = '55' + digits
    return digits


@app.route('/api/classifieds')
def api_classifieds():
    """Lista classificados aprovados e não expirados."""
    category = request.args.get('category', '')
    city     = request.args.get('city', '')
    page     = max(1, int(request.args.get('page', 1)))
    per_page = 20
    offset   = (page - 1) * per_page
    now      = datetime.now().isoformat()

    conn   = get_db()
    where  = ["status='approved'", "(expires_at IS NULL OR expires_at > ?)"]
    params = [now]

    if category:
        where.append('category=?'); params.append(category)
    if city:
        where.append('city=?'); params.append(city)

    sql = f'''SELECT * FROM classifieds WHERE {" AND ".join(where)}
              ORDER BY featured DESC, approved_at DESC
              LIMIT ? OFFSET ?'''
    rows  = conn.execute(sql, params + [per_page, offset]).fetchall()
    total = conn.execute(
        f'SELECT COUNT(*) FROM classifieds WHERE {" AND ".join(where)}', params
    ).fetchone()[0]
    conn.close()

    return jsonify({
        'classifieds': [dict(r) for r in rows],
        'total': total,
        'has_more': (offset + per_page) < total,
        'categories': CLASSIFIED_CATEGORIES,
    })


@app.route('/api/classifieds/submit', methods=['POST'])
def api_submit_classified():
    """Submissão pública de classificado."""
    title    = request.form.get('title', '').strip()
    desc     = request.form.get('description', '').strip()
    category = request.form.get('category', 'outros').strip()
    city     = request.form.get('city', 'Schroeder').strip()
    price_s  = request.form.get('price', '').strip()
    negotiab = 1 if request.form.get('price_negotiable') else 0
    name     = request.form.get('contact_name', '').strip()
    phone    = request.form.get('contact_whatsapp', '').strip()
    terms    = 1 if request.form.get('terms_accepted') else 0

    if not title or not name or not phone:
        return jsonify({'success': False, 'message': 'Título, nome e WhatsApp são obrigatórios.'}), 400
    if not terms:
        return jsonify({'success': False, 'message': 'Você precisa aceitar os termos.'}), 400
    if category not in CLASSIFIED_CATEGORIES:
        category = 'outros'
    if city not in CLASSIFIED_CITIES:
        city = 'Outra cidade'

    price = None
    if price_s:
        try:
            price = float(price_s.replace('R$', '').replace('.', '').replace(',', '.').strip())
        except Exception:
            price = None

    # Upload de foto (opcional)
    photo = None
    if 'photo' in request.files:
        f = request.files['photo']
        if f and f.filename and allowed_file(f.filename):
            fname = secure_filename(f.filename)
            ts    = datetime.now().strftime('%Y%m%d_%H%M%S_classified_')
            fname = ts + fname
            f.save(os.path.join(UPLOAD_DIR, fname))
            photo = fname

    wa = fmt_whatsapp(phone)
    conn = get_db()
    cur  = conn.execute('''
        INSERT INTO classifieds
        (title, description, category, price, price_negotiable, city,
         contact_name, contact_whatsapp, photo, status, terms_accepted, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
    ''', (title, desc or None, category, price, negotiab, city,
          name, wa, photo, terms, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    logger.info(f"Classificado #{cur.lastrowid} enviado para moderação: {title}")
    return jsonify({'success': True, 'message': 'Anúncio enviado! Aparecerá após aprovação.'})


@app.route('/api/classifieds/<int:ad_id>/view', methods=['POST'])
def api_classified_view(ad_id):
    """Incrementa contador de visualizações."""
    conn = get_db()
    conn.execute('UPDATE classifieds SET views=views+1 WHERE id=?', (ad_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ── Admin — Classificados ──────────────────────────────────────
@app.route('/admin/classifieds')
@login_required
def admin_list_classifieds():
    status = request.args.get('status', 'pending')
    conn   = get_db()
    rows   = conn.execute(
        'SELECT * FROM classifieds WHERE status=? ORDER BY created_at DESC LIMIT 200',
        (status,)
    ).fetchall()
    counts = {
        'pending':  conn.execute("SELECT COUNT(*) FROM classifieds WHERE status='pending'").fetchone()[0],
        'approved': conn.execute("SELECT COUNT(*) FROM classifieds WHERE status='approved'").fetchone()[0],
        'rejected': conn.execute("SELECT COUNT(*) FROM classifieds WHERE status='rejected'").fetchone()[0],
    }
    conn.close()
    return jsonify({'classifieds': [dict(r) for r in rows], 'counts': counts})


@app.route('/admin/classifieds/<int:ad_id>/approve', methods=['POST'])
@login_required
def admin_approve_classified(ad_id):
    from datetime import timedelta
    now     = datetime.now()
    expires = (now + timedelta(days=30)).isoformat()
    conn    = get_db()
    conn.execute(
        "UPDATE classifieds SET status='approved', approved_at=?, expires_at=? WHERE id=?",
        (now.isoformat(), expires, ad_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Anúncio aprovado por 30 dias.'})


@app.route('/admin/classifieds/<int:ad_id>/reject', methods=['POST'])
@login_required
def admin_reject_classified(ad_id):
    conn = get_db()
    conn.execute("UPDATE classifieds SET status='rejected' WHERE id=?", (ad_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/admin/classifieds/<int:ad_id>/delete', methods=['POST'])
@login_required
def admin_delete_classified(ad_id):
    conn = get_db()
    row  = conn.execute('SELECT photo FROM classifieds WHERE id=?', (ad_id,)).fetchone()
    if row and row['photo']:
        try:
            os.remove(os.path.join(UPLOAD_DIR, row['photo']))
        except Exception:
            pass
    conn.execute('DELETE FROM classifieds WHERE id=?', (ad_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/admin/classifieds/<int:ad_id>/toggle_featured', methods=['POST'])
@login_required
def admin_toggle_featured_classified(ad_id):
    conn = get_db()
    row  = conn.execute('SELECT featured FROM classifieds WHERE id=?', (ad_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'success': False}), 404
    new_val = 0 if row['featured'] else 1
    conn.execute('UPDATE classifieds SET featured=? WHERE id=?', (new_val, ad_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'featured': new_val})


# ── Vagas de Emprego ──────────────────────────────────────────────────────────
JOB_CATEGORIES = {
    'industria':   {'label': 'Indústria',      'emoji': '🏭'},
    'comercio':    {'label': 'Comércio',        'emoji': '🛒'},
    'servicos':    {'label': 'Serviços',        'emoji': '🔧'},
    'saude':       {'label': 'Saúde',           'emoji': '🏥'},
    'construcao':  {'label': 'Construção',      'emoji': '🏗️'},
    'transporte':  {'label': 'Transporte',      'emoji': '🚛'},
    'educacao':    {'label': 'Educação',        'emoji': '📚'},
    'alimentacao': {'label': 'Alimentação',     'emoji': '🍕'},
    'admin':       {'label': 'Administrativo',  'emoji': '👔'},
    'tecnologia':  {'label': 'Tecnologia',      'emoji': '💻'},
    'outros':      {'label': 'Outros',          'emoji': '📦'},
}

JOB_TYPES = {
    'clt':         'CLT',
    'pj':          'PJ',
    'temporario':  'Temporário',
    'estagio':     'Estágio',
    'meio_periodo':'Meio Período',
    'freelance':   'Freelance',
}

JOB_CITIES = ['Schroeder', 'Jaraguá do Sul', 'Guaramirim', 'Joinville', 'Corupá', 'Outra cidade']


@app.route('/api/jobs')
def api_jobs():
    city     = request.args.get('city', '').strip()
    category = request.args.get('category', '').strip()
    page     = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 12))
    offset   = (page - 1) * per_page

    conn = get_db()
    where  = ["status='approved'", "(expires_at IS NULL OR expires_at > datetime('now'))"]
    params = []
    if city:
        where.append('city=?'); params.append(city)
    if category:
        where.append('category=?'); params.append(category)

    sql = f"""
        SELECT * FROM jobs WHERE {' AND '.join(where)}
        ORDER BY featured DESC, approved_at DESC
        LIMIT ? OFFSET ?
    """
    rows = conn.execute(sql, params + [per_page + 1, offset]).fetchall()
    has_more = len(rows) > per_page
    jobs_list = [dict(r) for r in rows[:per_page]]
    conn.close()
    return jsonify({'jobs': jobs_list, 'has_more': has_more, 'page': page})


@app.route('/api/jobs/submit', methods=['POST'])
def api_submit_job():
    data = request.form
    title    = data.get('title', '').strip()
    company  = data.get('company', '').strip()
    whatsapp = data.get('contact_whatsapp', '').strip()
    city     = data.get('city', 'Schroeder').strip()
    category = data.get('category', 'outros').strip()
    job_type = data.get('job_type', 'clt').strip()

    if not title or not company or not whatsapp:
        return jsonify({'success': False, 'error': 'Título, empresa e WhatsApp são obrigatórios.'}), 400
    if category not in JOB_CATEGORIES:
        category = 'outros'
    if job_type not in JOB_TYPES:
        job_type = 'clt'

    from datetime import timedelta
    now = datetime.now().isoformat()
    expires = (datetime.now() + timedelta(days=30)).isoformat()

    conn = get_db()
    conn.execute('''
        INSERT INTO jobs
        (title, company, description, category, job_type, salary, city,
         contact_whatsapp, contact_email, status, created_at, expires_at)
        VALUES (?,?,?,?,?,?,?,?,?,'pending',?,?)
    ''', (
        title, company,
        data.get('description', '').strip(),
        category, job_type,
        data.get('salary', '').strip(),
        city, whatsapp,
        data.get('contact_email', '').strip(),
        now, expires
    ))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Vaga enviada para análise!'})


@app.route('/api/jobs/<int:job_id>/view', methods=['POST'])
def api_job_view(job_id):
    conn = get_db()
    conn.execute('UPDATE jobs SET views = views + 1 WHERE id=?', (job_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ── Admin — Vagas ──────────────────────────────────────────────
@app.route('/admin/jobs')
@login_required
def admin_list_jobs():
    conn  = get_db()
    rows  = conn.execute('SELECT * FROM jobs ORDER BY created_at DESC LIMIT 500').fetchall()
    counts = {
        'pending':  conn.execute("SELECT COUNT(*) FROM jobs WHERE status='pending'").fetchone()[0],
        'approved': conn.execute("SELECT COUNT(*) FROM jobs WHERE status='approved'").fetchone()[0],
        'rejected': conn.execute("SELECT COUNT(*) FROM jobs WHERE status='rejected'").fetchone()[0],
    }
    conn.close()
    return jsonify({'jobs': [dict(r) for r in rows], 'counts': counts})


@app.route('/admin/jobs/<int:job_id>/approve', methods=['POST'])
@login_required
def admin_approve_job(job_id):
    from datetime import timedelta
    now     = datetime.now().isoformat()
    expires = (datetime.now() + timedelta(days=30)).isoformat()
    conn = get_db()
    conn.execute(
        "UPDATE jobs SET status='approved', approved_at=?, expires_at=? WHERE id=?",
        (now, expires, job_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/admin/jobs/<int:job_id>/reject', methods=['POST'])
@login_required
def admin_reject_job(job_id):
    conn = get_db()
    conn.execute("UPDATE jobs SET status='rejected' WHERE id=?", (job_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/admin/jobs/<int:job_id>/delete', methods=['POST'])
@login_required
def admin_delete_job(job_id):
    conn = get_db()
    conn.execute('DELETE FROM jobs WHERE id=?', (job_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/admin/jobs/<int:job_id>/toggle_featured', methods=['POST'])
@login_required
def admin_toggle_featured_job(job_id):
    conn = get_db()
    row  = conn.execute('SELECT featured FROM jobs WHERE id=?', (job_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'success': False}), 404
    new_val = 0 if row['featured'] else 1
    conn.execute('UPDATE jobs SET featured=? WHERE id=?', (new_val, job_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'featured': new_val})


@app.route('/admin/youtube-channels', methods=['GET', 'POST'])
@login_required
def admin_youtube_channels():
    if request.method == 'POST':
        data = request.form
        name       = data.get('name', '').strip()
        channel_id = data.get('channel_id', '').strip()
        category   = data.get('category', 'geral').strip()
        if not name or not channel_id:
            return jsonify({'success': False, 'message': 'Nome e Channel ID obrigatórios.'}), 400
        conn = get_db()
        try:
            cur = conn.execute('''
                INSERT INTO youtube_channels (name, channel_id, category, active, sort_order, created_at)
                VALUES (?, ?, ?, 1,
                    (SELECT COALESCE(MAX(sort_order), 0)+1 FROM youtube_channels),
                    ?)
            ''', (name, channel_id, category, datetime.now().isoformat()))
            conn.commit()
            ch_id = cur.lastrowid
            conn.close()
            _yt_videos_cache['ts'] = 0  # invalida cache
            return jsonify({'success': True, 'id': ch_id})
        except Exception as e:
            conn.close()
            return jsonify({'success': False, 'message': str(e)}), 409
    conn = get_db()
    channels = conn.execute(
        'SELECT * FROM youtube_channels ORDER BY sort_order, name'
    ).fetchall()
    conn.close()
    return jsonify([dict(c) for c in channels])


@app.route('/admin/youtube-channels/<int:ch_id>/delete', methods=['POST'])
@login_required
def admin_delete_youtube_channel(ch_id):
    conn = get_db()
    conn.execute('DELETE FROM youtube_channels WHERE id=?', (ch_id,))
    conn.commit()
    conn.close()
    _yt_videos_cache['ts'] = 0
    return jsonify({'success': True})


@app.route('/admin/youtube-channels/<int:ch_id>/toggle', methods=['POST'])
@login_required
def admin_toggle_youtube_channel(ch_id):
    conn = get_db()
    ch = conn.execute('SELECT active FROM youtube_channels WHERE id=?', (ch_id,)).fetchone()
    if not ch:
        conn.close()
        return jsonify({'success': False}), 404
    new_state = 0 if ch['active'] else 1
    conn.execute('UPDATE youtube_channels SET active=? WHERE id=?', (new_state, ch_id))
    conn.commit()
    conn.close()
    _yt_videos_cache['ts'] = 0
    return jsonify({'success': True, 'active': new_state})



# ── Canais regionais Norte SC para monitorar ao vivo ──────────
MONITORED_CHANNELS_SEED = [
    # ── Futebol / Esportes regionais ──
    {'name': 'JEC Joinville',              'channel_id': 'UCNjIQGJD57ZfC6bEYN_gMvg', 'type': 'esporte', 'city': 'Joinville'},
    {'name': 'Figueirense FC',             'channel_id': 'UCjm7jQS7qD-lH8BV1rNdBSw', 'type': 'esporte', 'city': 'Florianópolis'},
    {'name': 'Chapecoense',                'channel_id': 'UCQGFTlg1bZyV0DQTKE3gFXg', 'type': 'esporte', 'city': 'Chapecó'},
    # ── Missas / Igrejas ──
    {'name': 'Diocese de Joinville',       'channel_id': 'UCeHvIpJLDmTr_kzM3hBFhNg', 'type': 'missa',   'city': 'Joinville'},
    {'name': 'TV Canção Nova',             'channel_id': 'UCCHRwg4F6cjSuhcHAM7GQVA', 'type': 'missa',   'city': 'Nacional'},
    {'name': 'Padre Reginaldo Manzotti',   'channel_id': 'UCaA05__0bOa7EM74VTx3Oew', 'type': 'missa',   'city': 'Nacional'},
    # ── TV / Notícias regionais ──
    {'name': 'NSC Total',                  'channel_id': 'UCMioY9xHh_88u8iMIzJvCUQ', 'type': 'geral',   'city': 'Santa Catarina'},
    {'name': 'SCC SBT Santa Catarina',     'channel_id': 'UCT_J5HN1oCDj3fJd0_iRSUw', 'type': 'geral',   'city': 'Norte de SC'},
    # ── Corridas / Automobilismo (nacionais) ──
    {'name': 'Stock Car Brasil',           'channel_id': 'UCqA-s9GE3aeU5Gv-MBhyp4A', 'type': 'esporte', 'city': 'Nacional'},
    {'name': 'Bandsports (F1/Moto)',        'channel_id': 'UCp3sMXsRchHGIF5QTtIxuKw', 'type': 'esporte', 'city': 'Nacional'},
    {'name': 'Fórmula 4 Brasil',           'channel_id': 'UCH63gpxq4MifoNRuQQpRcOA', 'type': 'esporte', 'city': 'Nacional'},
    # ── Corridas de Rua / Triathlon ──
    {'name': 'World Athletics',            'channel_id': 'UCIHBiAlO32tvPGXMzIR9SFg', 'type': 'esporte', 'city': 'Internacional'},
    {'name': 'Ironman Brasil',             'channel_id': 'UCbbYpDh5rjL_UqkMpfnwuXQ', 'type': 'esporte', 'city': 'Nacional'},
    {'name': 'Run2Play Corridas',          'channel_id': 'UC6o7pqCuN_LFtL4F3k3rxNQ', 'type': 'esporte', 'city': 'Nacional'},
    # ── Eventos / Shows ──
    {'name': 'TV Cultura (shows/eventos)', 'channel_id': 'UCFiGIbHNmkLCBhCABO4JDGA', 'type': 'show',    'city': 'Nacional'},
]


def seed_monitored_channels():
    """Semeia canais regionais para monitoramento ao vivo se a tabela estiver vazia."""
    conn = get_db()
    count = conn.execute('SELECT COUNT(*) FROM monitored_channels').fetchone()[0]
    if count == 0:
        now = datetime.now().isoformat()
        for ch in MONITORED_CHANNELS_SEED:
            try:
                conn.execute('''
                    INSERT OR IGNORE INTO monitored_channels
                    (name, youtube_channel_id, type, city, auto_publish, active, created_at)
                    VALUES (?, ?, ?, ?, 1, 1, ?)
                ''', (ch['name'], ch['channel_id'], ch['type'], ch['city'], now))
            except Exception as e:
                logger.warning(f'seed_monitored_channels: {e}')
        conn.commit()
        logger.info(f'Monitoramento: {len(MONITORED_CHANNELS_SEED)} canais regionais pré-configurados.')
    conn.close()


# ── Inicialização que roda sempre (dev e produção/gunicorn) ──
with app.app_context():
    init_db()
    seed_youtube_channels()
    seed_monitored_channels()

import threading as _threading
_t = _threading.Thread(target=background_startup, daemon=True)
_t.start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
