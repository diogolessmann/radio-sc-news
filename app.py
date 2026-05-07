"""
app.py — Backend principal Flask
Rádio SC News — Portal de notícias com áudio e painel admin
"""
import os
import sqlite3
import hashlib
import logging
from datetime import datetime
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


# ── Inicialização que roda sempre (dev e produção/gunicorn) ──
with app.app_context():
    init_db()

import threading as _threading
_t = _threading.Thread(target=background_startup, daemon=True)
_t.start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
