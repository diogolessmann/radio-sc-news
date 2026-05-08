"""
stream_checker.py — Verificador de transmissões ao vivo no YouTube
Rádio SC News — Sem API key (scrape) ou com API key (YouTube Data API v3)
"""
import os
import re
import logging
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)

YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY', '')


def check_youtube_channel_live(channel_id):
    """
    Verifica se um canal do YouTube está ao vivo.
    Sem API key: faz scrape da página /live do canal.
    Com API key: usa YouTube Data API v3.
    Retorna dict com {is_live, video_id, title, thumbnail_url, embed_url} ou None em caso de erro.
    """
    if YOUTUBE_API_KEY:
        return _check_via_api(channel_id)
    else:
        return _check_via_scrape(channel_id)


def _check_via_api(channel_id):
    """Verifica ao vivo via YouTube Data API v3."""
    try:
        import requests
        url = 'https://www.googleapis.com/youtube/v3/search'
        params = {
            'key': YOUTUBE_API_KEY,
            'channelId': channel_id,
            'part': 'snippet',
            'type': 'video',
            'eventType': 'live',
            'maxResults': 1,
        }
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            logger.warning(f'YouTube API error {r.status_code} for channel {channel_id}')
            return _check_via_scrape(channel_id)

        data = r.json()
        items = data.get('items', [])
        if not items:
            return {'is_live': False, 'video_id': None, 'title': None,
                    'thumbnail_url': None, 'embed_url': None}

        item = items[0]
        video_id = item['id']['videoId']
        snippet = item.get('snippet', {})
        title = snippet.get('title', '')
        thumbnails = snippet.get('thumbnails', {})
        thumb = (thumbnails.get('high') or thumbnails.get('medium') or
                 thumbnails.get('default') or {}).get('url', '')

        return {
            'is_live': True,
            'video_id': video_id,
            'title': title,
            'thumbnail_url': thumb,
            'embed_url': f'https://www.youtube.com/embed/{video_id}?autoplay=1&rel=0',
        }
    except Exception as e:
        logger.warning(f'YouTube API check failed for {channel_id}: {e}')
        return _check_via_scrape(channel_id)


def _check_via_scrape(channel_id):
    """
    Verifica ao vivo via scrape da página /live do canal.
    Segue redirect e extrai video_id do HTML.
    """
    try:
        import requests
        # Tenta pelo ID do canal
        url = f'https://www.youtube.com/channel/{channel_id}/live'
        headers = {
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/124.0.0.0 Safari/537.36'),
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
        }
        r = requests.get(url, timeout=12, allow_redirects=True, headers=headers)
        html = r.text
        final_url = r.url

        # Se o redirect levou para um watch?v= — está ao vivo
        video_id = None
        if 'watch?v=' in final_url:
            video_id = final_url.split('watch?v=')[1].split('&')[0]

        # Fallback: busca no HTML
        if not video_id:
            m = re.search(r'"videoId":"([A-Za-z0-9_-]{11})"', html)
            if m:
                video_id = m.group(1)

        if not video_id:
            return {'is_live': False, 'video_id': None, 'title': None,
                    'thumbnail_url': None, 'embed_url': None}

        # Verifica se realmente está ao vivo (página pode ter vídeos normais)
        is_live = (
            '"isLiveNow":true' in html or
            '"isLive":true' in html or
            '"liveBroadcastContent":"live"' in html or
            'watch?v=' in final_url  # redirect direto = ao vivo
        )

        if not is_live:
            return {'is_live': False, 'video_id': None, 'title': None,
                    'thumbnail_url': None, 'embed_url': None}

        # Extrai título
        title = None
        tm = re.search(r'"title":"([^"]+)"', html)
        if tm:
            title = tm.group(1).encode('utf-8').decode('unicode_escape') if '\\u' in tm.group(1) else tm.group(1)

        thumb = f'https://img.youtube.com/vi/{video_id}/hqdefault.jpg'

        return {
            'is_live': True,
            'video_id': video_id,
            'title': title,
            'thumbnail_url': thumb,
            'embed_url': f'https://www.youtube.com/embed/{video_id}?autoplay=1&rel=0',
        }
    except Exception as e:
        logger.warning(f'Scrape check failed for {channel_id}: {e}')
        return None


def update_live_status(db_path):
    """
    Verifica todos os canais monitorados ativos e atualiza o banco de dados.
    - Atualiza youtube_video_id e is_live nas transmissões vinculadas ao canal.
    - Se auto_publish=1 e canal entrou ao vivo, cria transmissão automaticamente.
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        channels = conn.execute(
            'SELECT * FROM monitored_channels WHERE active=1'
        ).fetchall()

        now_iso = datetime.now().isoformat()

        for ch in channels:
            channel_id = ch['youtube_channel_id']
            if not channel_id:
                continue

            logger.info(f'Verificando canal: {ch["name"]} ({channel_id})')
            result = check_youtube_channel_live(channel_id)

            # Atualiza last_checked
            conn.execute(
                'UPDATE monitored_channels SET last_checked=? WHERE id=?',
                (now_iso, ch['id'])
            )

            if result is None:
                # Erro na verificação — não altera status
                continue

            if result['is_live'] and result['video_id']:
                video_id = result['video_id']
                title = result['title'] or ch['name']
                thumb = result['thumbnail_url']

                # Verifica se já existe transmissão ao vivo para este canal/vídeo
                existing = conn.execute(
                    '''SELECT id FROM transmissions
                       WHERE youtube_channel_id=? AND youtube_video_id=? AND is_live=1''',
                    (channel_id, video_id)
                ).fetchone()

                if not existing:
                    # Marca transmissões antigas do mesmo canal como não ao vivo
                    conn.execute(
                        '''UPDATE transmissions SET is_live=0
                           WHERE youtube_channel_id=? AND is_live=1''',
                        (channel_id,)
                    )

                    if ch['auto_publish']:
                        # Cria nova transmissão automaticamente
                        conn.execute(
                            '''INSERT INTO transmissions
                               (title, type, youtube_channel_id, youtube_video_id,
                                is_live, thumbnail_url, city, active, created_at, scheduled_at)
                               VALUES (?, ?, ?, ?, 1, ?, ?, 1, ?, ?)''',
                            (title, ch['type'] or 'geral', channel_id, video_id,
                             thumb, ch['city'] or 'Região', now_iso, now_iso)
                        )
                        logger.info(f'Nova transmissão ao vivo criada: {title}')
                else:
                    # Atualiza thumbnail se mudou
                    if thumb:
                        conn.execute(
                            'UPDATE transmissions SET thumbnail_url=? WHERE id=?',
                            (thumb, existing['id'])
                        )
            else:
                # Canal não está ao vivo — marca transmissões como não ao vivo
                conn.execute(
                    '''UPDATE transmissions SET is_live=0
                       WHERE youtube_channel_id=? AND is_live=1''',
                    (channel_id,)
                )
                logger.info(f'Canal {ch["name"]} não está ao vivo.')

        conn.commit()
        conn.close()
        logger.info('update_live_status concluído.')
    except Exception as e:
        logger.error(f'Erro em update_live_status: {e}')
