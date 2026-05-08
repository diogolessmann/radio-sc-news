"""
app.py — Backend principal Flask
Rádio SC News — Portal de notícias com áudio e painel admin
"""
import os
import re as _re
import sqlite3
import hashlib
import logging
import unicodedata
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, render_template, request, jsonify,
                   redirect, url_for, session, send_from_directory,
                   flash, abort)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# ──────────────────────────────────────────────
# Configurações
# ──────────────────────────────────────────────
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'radio-sc-secret-2024-xk91')

DB_PATH       = os.environ.get('DB_PATH', 'radio_sc.db')
AUDIO_DIR     = os.environ.get('AUDIO_DIR', 'audio')
UPLOAD_DIR    = os.environ.get('UPLOAD_DIR', 'uploads')
ADMIN_PASSWORD_PLAIN = os.environ.get('ADMIN_PASSWORD', 'julia181014')

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

        CREATE TABLE IF NOT EXISTS agenda_businesses (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            slug          TEXT NOT NULL UNIQUE,
            owner_name    TEXT NOT NULL,
            phone         TEXT NOT NULL,
            email         TEXT,
            business_type TEXT DEFAULT 'outros',
            description   TEXT,
            address       TEXT,
            password_hash TEXT NOT NULL,
            active        INTEGER DEFAULT 1,
            created_at    TEXT,
            trial_ends    TEXT
        );

        CREATE TABLE IF NOT EXISTS agenda_services (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id      INTEGER NOT NULL,
            name             TEXT NOT NULL,
            duration_minutes INTEGER DEFAULT 60,
            price            REAL DEFAULT 0,
            active           INTEGER DEFAULT 1,
            created_at       TEXT
        );

        CREATE TABLE IF NOT EXISTS agenda_availability (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            weekday     INTEGER NOT NULL,
            start_time  TEXT NOT NULL,
            end_time    TEXT NOT NULL,
            active      INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS agenda_appointments (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id      INTEGER NOT NULL,
            service_id       INTEGER,
            customer_name    TEXT NOT NULL,
            customer_phone   TEXT NOT NULL,
            customer_notes   TEXT,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            status           TEXT DEFAULT 'pending',
            created_at       TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_agenda_biz_slug ON agenda_businesses(slug);
        CREATE INDEX IF NOT EXISTS idx_agenda_appt_biz  ON agenda_appointments(business_id);
        CREATE INDEX IF NOT EXISTS idx_agenda_appt_date ON agenda_appointments(appointment_date);
        CREATE INDEX IF NOT EXISTS idx_agenda_appt_status ON agenda_appointments(status);
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

@app.route('/api/transmissions')
def api_transmissions():
    """Retorna transmissões ao vivo agora + agenda dos próximos 10 dias."""
    from datetime import timedelta
    conn = get_db()
    now = datetime.now()
    ten_days = (now + timedelta(days=10)).isoformat()

    live = conn.execute(
        'SELECT * FROM transmissions WHERE active=1 AND is_live=1 ORDER BY created_at DESC'
    ).fetchall()

    scheduled = conn.execute(
        '''SELECT * FROM transmissions
           WHERE active=1 AND is_live=0
             AND scheduled_at IS NOT NULL
             AND scheduled_at >= ?
             AND scheduled_at <= ?
           ORDER BY scheduled_at ASC''',
        (now.isoformat(), ten_days)
    ).fetchall()

    conn.close()
    return jsonify({
        'live': [dict(r) for r in live],
        'scheduled': [dict(r) for r in scheduled],
    })


@app.route('/api/transmissions/live')
def api_transmissions_live():
    """Retorna apenas as transmissões ao vivo agora."""
    conn = get_db()
    live = conn.execute(
        'SELECT * FROM transmissions WHERE active=1 AND is_live=1 ORDER BY created_at DESC'
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in live])


# ──────────────────────────────────────────────
# Rotas Admin — Transmissões
# ──────────────────────────────────────────────
TYPE_EMOJIS = {
    'esporte': '⚽', 'missa': '🕯️', 'camara': '🏛️',
    'show': '🎵', 'tv': '📺', 'geral': '📡',
}

@app.route('/admin/transmissions', methods=['GET', 'POST'])
@login_required
def admin_transmissions():
    if request.method == 'POST':
        data = request.form
        title = data.get('title', '').strip()
        if not title:
            return jsonify({'success': False, 'message': 'Título obrigatório.'}), 400

        t_type       = data.get('type', 'geral').strip()
        description  = data.get('description', '').strip()
        stream_url   = data.get('stream_url', '').strip()
        yt_channel   = data.get('youtube_channel_id', '').strip()
        yt_video     = data.get('youtube_video_id', '').strip()
        scheduled_at = data.get('scheduled_at', '').strip()
        duration     = int(data.get('duration_minutes', 90) or 90)
        is_recurring = 1 if data.get('is_recurring') else 0
        recur_days   = data.get('recurrence_days', '').strip()
        city         = data.get('city', 'Região').strip()
        thumbnail    = data.get('thumbnail_url', '').strip()

        conn = get_db()
        cur = conn.execute('''
            INSERT INTO transmissions
            (title, type, description, stream_url, youtube_channel_id, youtube_video_id,
             scheduled_at, duration_minutes, is_recurring, recurrence_days,
             thumbnail_url, city, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        ''', (title, t_type, description or None, stream_url or None,
              yt_channel or None, yt_video or None, scheduled_at or None,
              duration, is_recurring, recur_days or None,
              thumbnail or None, city, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'id': cur.lastrowid})

    conn = get_db()
    transmissions = conn.execute(
        'SELECT * FROM transmissions ORDER BY created_at DESC LIMIT 100'
    ).fetchall()
    conn.close()
    return jsonify([dict(t) for t in transmissions])


@app.route('/admin/transmissions/<int:t_id>/delete', methods=['POST'])
@login_required
def admin_delete_transmission(t_id):
    conn = get_db()
    conn.execute('DELETE FROM transmissions WHERE id=?', (t_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/admin/transmissions/<int:t_id>/toggle_live', methods=['POST'])
@login_required
def admin_toggle_live(t_id):
    conn = get_db()
    t = conn.execute('SELECT is_live FROM transmissions WHERE id=?', (t_id,)).fetchone()
    if not t:
        conn.close()
        return jsonify({'success': False, 'message': 'Não encontrado.'}), 404
    new_state = 0 if t['is_live'] else 1
    conn.execute('UPDATE transmissions SET is_live=? WHERE id=?', (new_state, t_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'is_live': new_state})


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


@app.route('/manifest.json')
def manifest():
    from flask import send_from_directory
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')


@app.route('/api/news')
def api_news():
    """Feed de notícias paginado com filtros."""
    page     = max(1, int(request.args.get('page', 1)))
    per_page = min(20, int(request.args.get('per_page', 10)))
    city     = request.args.get('city', '')
    category = request.args.get('category', '')
    region   = request.args.get('region', '')
    search   = request.args.get('q', '')
    offset   = (page - 1) * per_page

    NORTE_SC_CITIES = ('Schroeder', 'Joinville', 'Jaraguá do Sul', 'Guaramirim', 'Corupá', 'Norte de SC')

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
        if pwd == ADMIN_PASSWORD_PLAIN:
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
    conn.close()
    return render_template('admin.html', news=news, media=media, ads=ads, stats=stats)


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
        count = conn.execute('SELECT COUNT(*) FROM news').fetchone()[0]
        conn.close()
        if count == 0:
            logger.info("Banco vazio — fazendo coleta inicial em background...")
            from scraper import collect_all
            collect_all()
    except Exception as e:
        logger.warning(f"Coleta inicial falhou: {e}")

    # Thread de verificação de transmissões ao vivo (a cada 10 minutos)
    def live_check_loop():
        import time as _t
        while True:
            try:
                from stream_checker import update_live_status
                update_live_status(DB_PATH)
            except Exception as e:
                logger.warning(f"Live check falhou: {e}")
            _t.sleep(600)  # 10 minutos

    live_thread = _threading.Thread(target=live_check_loop, daemon=True)
    live_thread.start()
    logger.info("Thread de verificação de transmissões ao vivo iniciada.")


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
    import feedparser
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    try:
        feed = feedparser.parse(url)
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

    result = []
    for ch in channels:
        videos = fetch_yt_rss(ch['channel_id'], max_videos=5)
        result.append({
            'id': ch['id'],
            'name': ch['name'],
            'channel_id': ch['channel_id'],
            'category': ch['category'],
            'videos': videos,
        })

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
    where  = ["status='approved'", "datetime('now') < expires_at"]
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
    rows  = conn.execute('SELECT * FROM jobs ORDER BY created_at DESC').fetchall()
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


# ══════════════════════════════════════════════════════════════
#  AGENDA SC — SaaS de Agendamento Online
# ══════════════════════════════════════════════════════════════

BUSINESS_TYPES = {
    'barbearia':   '💈 Barbearia',
    'salao':       '💇 Salão de Beleza',
    'estetica':    '💅 Estética / Spa',
    'clinica':     '🏥 Clínica Médica',
    'dentista':    '🦷 Dentista / Ortodontia',
    'psicologia':  '🧠 Psicologia / Terapia',
    'nutricao':    '🥗 Nutricionista',
    'fisioterapia':'🦵 Fisioterapia',
    'pet':         '🐾 Pet Shop / Veterinário',
    'academia':    '💪 Academia / Personal Trainer',
    'mecanica':    '🔧 Mecânica / Oficina',
    'advocacia':   '⚖️ Advocacia / Contabilidade',
    'consultoria': '📊 Consultoria / Coaching',
    'fotografia':  '📷 Fotografia / Estúdio',
    'tatuagem':    '🖊️ Tatuagem / Piercing',
    'outros':      '🏢 Outro',
}

WEEKDAY_NAMES = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']


def _slugify(text):
    text = unicodedata.normalize('NFD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = text.lower().strip()
    text = _re.sub(r'[^\w\s-]', '', text)
    text = _re.sub(r'[\s_-]+', '-', text)
    return text[:50]


def _agenda_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('agenda_business_id'):
            return redirect('/agenda/entrar')
        return f(*args, **kwargs)
    return decorated


def _get_slots(business_id, date_str, service_duration):
    """Gera horários disponíveis para uma data e duração de serviço."""
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        weekday = dt.weekday()
    except Exception:
        return []

    conn = get_db()
    avail = conn.execute(
        'SELECT start_time, end_time FROM agenda_availability WHERE business_id=? AND weekday=? AND active=1',
        (business_id, weekday)
    ).fetchone()
    if not avail:
        conn.close()
        return []

    booked = conn.execute('''
        SELECT a.appointment_time, COALESCE(s.duration_minutes, 60) as duration_minutes
        FROM agenda_appointments a
        LEFT JOIN agenda_services s ON a.service_id = s.id
        WHERE a.business_id=? AND a.appointment_date=? AND a.status != 'cancelled'
    ''', (business_id, date_str)).fetchall()
    conn.close()

    slots = []
    start = datetime.strptime(avail['start_time'], '%H:%M')
    end   = datetime.strptime(avail['end_time'],   '%H:%M')
    now   = datetime.now()
    current = start

    while current + timedelta(minutes=service_duration) <= end:
        slot_str = current.strftime('%H:%M')
        # Pula slots no passado para hoje
        if dt.date() == now.date() and current.replace(year=now.year, month=now.month, day=now.day) <= now:
            current += timedelta(minutes=30)
            continue
        # Verifica conflito
        conflict = False
        s_end = current + timedelta(minutes=service_duration)
        for b in booked:
            b_start = datetime.strptime(b['appointment_time'], '%H:%M')
            b_end   = b_start + timedelta(minutes=b['duration_minutes'])
            if not (s_end <= b_start or current >= b_end):
                conflict = True
                break
        if not conflict:
            slots.append(slot_str)
        current += timedelta(minutes=30)

    return slots


# ── Landing Page ──────────────────────────────────────────────
@app.route('/agenda')
def agenda_landing():
    return render_template('agenda_landing.html')


# ── Cadastro ──────────────────────────────────────────────────
@app.route('/agenda/cadastro', methods=['GET', 'POST'])
def agenda_cadastro():
    error = None
    if request.method == 'POST':
        name          = request.form.get('name', '').strip()
        owner_name    = request.form.get('owner_name', '').strip()
        phone         = request.form.get('phone', '').strip()
        email         = request.form.get('email', '').strip()
        business_type = request.form.get('business_type', 'outros')
        password      = request.form.get('password', '').strip()

        if not all([name, owner_name, phone, password]):
            error = 'Preencha todos os campos obrigatórios.'
        elif len(password) < 6:
            error = 'A senha precisa ter pelo menos 6 caracteres.'
        else:
            slug = _slugify(name) or 'negocio'
            conn = get_db()
            base_slug, counter = slug, 1
            while conn.execute('SELECT id FROM agenda_businesses WHERE slug=?', (slug,)).fetchone():
                slug = f'{base_slug}-{counter}'; counter += 1
            trial_ends = (datetime.now() + timedelta(days=30)).isoformat()
            try:
                conn.execute('''
                    INSERT INTO agenda_businesses
                    (name, slug, owner_name, phone, email, business_type, password_hash, active, created_at, trial_ends)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                ''', (name, slug, owner_name, phone, email, business_type,
                      generate_password_hash(password), datetime.now().isoformat(), trial_ends))
                conn.commit()
                biz = conn.execute('SELECT * FROM agenda_businesses WHERE slug=?', (slug,)).fetchone()
                conn.close()
                session['agenda_business_id']   = biz['id']
                session['agenda_business_slug'] = biz['slug']
                session['agenda_business_name'] = biz['name']
                return redirect('/agenda/painel')
            except Exception as e:
                conn.close()
                logger.error(f'Agenda cadastro error: {e}')
                error = 'Erro ao cadastrar. Tente novamente.'

    return render_template('agenda_cadastro.html', error=error, business_types=BUSINESS_TYPES)


# ── Login ─────────────────────────────────────────────────────
@app.route('/agenda/entrar', methods=['GET', 'POST'])
def agenda_entrar():
    error = None
    if request.method == 'POST':
        phone    = request.form.get('phone', '').strip()
        password = request.form.get('password', '').strip()
        conn = get_db()
        biz = conn.execute(
            'SELECT * FROM agenda_businesses WHERE phone=? AND active=1', (phone,)
        ).fetchone()
        conn.close()
        if biz and check_password_hash(biz['password_hash'], password):
            session['agenda_business_id']   = biz['id']
            session['agenda_business_slug'] = biz['slug']
            session['agenda_business_name'] = biz['name']
            return redirect('/agenda/painel')
        error = 'Telefone ou senha incorretos.'
    return render_template('agenda_login.html', error=error)


# ── Logout ────────────────────────────────────────────────────
@app.route('/agenda/sair')
def agenda_sair():
    for k in ('agenda_business_id', 'agenda_business_slug', 'agenda_business_name'):
        session.pop(k, None)
    return redirect('/agenda')


# ── Painel ────────────────────────────────────────────────────
@app.route('/agenda/painel')
@_agenda_login_required
def agenda_painel():
    biz_id = session['agenda_business_id']
    conn   = get_db()
    biz    = dict(conn.execute('SELECT * FROM agenda_businesses WHERE id=?', (biz_id,)).fetchone())
    services = [dict(r) for r in conn.execute(
        'SELECT * FROM agenda_services WHERE business_id=? AND active=1 ORDER BY name', (biz_id,)
    ).fetchall()]
    availability = [dict(r) for r in conn.execute(
        'SELECT * FROM agenda_availability WHERE business_id=? ORDER BY weekday', (biz_id,)
    ).fetchall()]
    today = datetime.now().strftime('%Y-%m-%d')
    appointments = [dict(r) for r in conn.execute('''
        SELECT a.*, COALESCE(s.name, 'Serviço') as service_name,
               COALESCE(s.duration_minutes, 60) as duration_minutes,
               COALESCE(s.price, 0) as price
        FROM agenda_appointments a
        LEFT JOIN agenda_services s ON a.service_id = s.id
        WHERE a.business_id=? AND a.appointment_date >= ?
        ORDER BY a.appointment_date, a.appointment_time
    ''', (biz_id, today)).fetchall()]
    conn.close()
    return render_template('agenda_painel.html',
                           biz=biz, services=services,
                           availability=availability,
                           appointments=appointments,
                           today=today,
                           weekday_names=WEEKDAY_NAMES,
                           business_types=BUSINESS_TYPES)


# ── Adicionar serviço ─────────────────────────────────────────
@app.route('/agenda/painel/servico/add', methods=['POST'])
@_agenda_login_required
def agenda_add_service():
    biz_id   = session['agenda_business_id']
    name     = request.form.get('name', '').strip()
    duration = request.form.get('duration', '60')
    price    = request.form.get('price', '0').replace(',', '.')
    if not name:
        return jsonify({'success': False, 'error': 'Nome obrigatório'})
    try:
        conn = get_db()
        cur = conn.execute('''
            INSERT INTO agenda_services (business_id, name, duration_minutes, price, active, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
        ''', (biz_id, name, int(duration), float(price or 0), datetime.now().isoformat()))
        conn.commit()
        svc_id = cur.lastrowid
        conn.close()
        return jsonify({'success': True, 'id': svc_id, 'name': name,
                        'duration': int(duration), 'price': float(price or 0)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ── Remover serviço ───────────────────────────────────────────
@app.route('/agenda/painel/servico/<int:svc_id>/delete', methods=['POST'])
@_agenda_login_required
def agenda_delete_service(svc_id):
    biz_id = session['agenda_business_id']
    conn = get_db()
    conn.execute('UPDATE agenda_services SET active=0 WHERE id=? AND business_id=?', (svc_id, biz_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ── Salvar disponibilidade ────────────────────────────────────
@app.route('/agenda/painel/horario/save', methods=['POST'])
@_agenda_login_required
def agenda_save_horario():
    biz_id = session['agenda_business_id']
    data   = request.get_json() or {}
    conn   = get_db()
    conn.execute('DELETE FROM agenda_availability WHERE business_id=?', (biz_id,))
    for item in data.get('availability', []):
        wday = item.get('weekday')
        s    = item.get('start_time', '')
        e    = item.get('end_time', '')
        if wday is not None and s and e:
            conn.execute('''
                INSERT INTO agenda_availability (business_id, weekday, start_time, end_time, active)
                VALUES (?, ?, ?, ?, 1)
            ''', (biz_id, wday, s, e))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ── Ações em agendamentos ─────────────────────────────────────
@app.route('/agenda/painel/agendamento/<int:appt_id>/<action>', methods=['POST'])
@_agenda_login_required
def agenda_appt_action(appt_id, action):
    biz_id = session['agenda_business_id']
    status_map = {'confirmar': 'confirmed', 'cancelar': 'cancelled', 'concluir': 'done'}
    new_status = status_map.get(action)
    if not new_status:
        return jsonify({'success': False, 'error': 'Ação inválida'})
    conn = get_db()
    conn.execute('UPDATE agenda_appointments SET status=? WHERE id=? AND business_id=?',
                 (new_status, appt_id, biz_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'status': new_status})


# ── Página pública de agendamento ─────────────────────────────
@app.route('/agendar/<slug>')
def agenda_booking(slug):
    conn = get_db()
    biz = conn.execute(
        'SELECT * FROM agenda_businesses WHERE slug=? AND active=1', (slug,)
    ).fetchone()
    if not biz:
        conn.close()
        abort(404)
    services = [dict(r) for r in conn.execute(
        'SELECT * FROM agenda_services WHERE business_id=? AND active=1 ORDER BY name', (biz['id'],)
    ).fetchall()]
    conn.close()
    return render_template('agenda_booking.html', biz=dict(biz), services=services)


# ── API: slots disponíveis ────────────────────────────────────
@app.route('/api/agenda/slots/<slug>')
def api_agenda_slots(slug):
    date_str   = request.args.get('date', '')
    service_id = request.args.get('service_id', '')
    conn = get_db()
    biz = conn.execute('SELECT id FROM agenda_businesses WHERE slug=? AND active=1', (slug,)).fetchone()
    if not biz:
        conn.close()
        return jsonify({'slots': []})
    duration = 60
    if service_id:
        svc = conn.execute('SELECT duration_minutes FROM agenda_services WHERE id=? AND business_id=? AND active=1',
                           (service_id, biz['id'])).fetchone()
        if svc:
            duration = svc['duration_minutes']
    conn.close()
    return jsonify({'slots': _get_slots(biz['id'], date_str, duration)})


# ── API: criar agendamento ────────────────────────────────────
@app.route('/api/agenda/book/<slug>', methods=['POST'])
def api_agenda_book(slug):
    data           = request.get_json() or {}
    customer_name  = data.get('customer_name', '').strip()
    customer_phone = data.get('customer_phone', '').strip()
    service_id     = data.get('service_id')
    appt_date      = data.get('date', '').strip()
    appt_time      = data.get('time', '').strip()
    notes          = data.get('notes', '').strip()

    if not all([customer_name, customer_phone, appt_date, appt_time]):
        return jsonify({'success': False, 'error': 'Preencha todos os campos obrigatórios.'})

    conn = get_db()
    biz = conn.execute('SELECT * FROM agenda_businesses WHERE slug=? AND active=1', (slug,)).fetchone()
    if not biz:
        conn.close()
        return jsonify({'success': False, 'error': 'Negócio não encontrado.'})

    duration = 60
    if service_id:
        svc = conn.execute('SELECT duration_minutes FROM agenda_services WHERE id=? AND business_id=? AND active=1',
                           (service_id, biz['id'])).fetchone()
        if svc:
            duration = svc['duration_minutes']

    slots = _get_slots(biz['id'], appt_date, duration)
    if appt_time not in slots:
        conn.close()
        return jsonify({'success': False, 'error': 'Horário não disponível. Por favor, escolha outro.'})

    conn.execute('''
        INSERT INTO agenda_appointments
        (business_id, service_id, customer_name, customer_phone, customer_notes,
         appointment_date, appointment_time, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
    ''', (biz['id'], service_id or None, customer_name, customer_phone, notes,
          appt_date, appt_time, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'business_name': biz['name'], 'business_phone': biz['phone']})


# ── Inicialização que roda sempre (dev e produção/gunicorn) ──
with app.app_context():
    init_db()
    seed_youtube_channels()

import threading as _threading
_t = _threading.Thread(target=background_startup, daemon=True)
_t.start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
