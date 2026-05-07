"""
tts_engine.py — Geração de áudio com ElevenLabs (primário) + edge-tts (fallback)
Voz ElevenLabs: locutor de rádio profissional em português BR
"""
import os
import re
import asyncio
import logging
import hashlib
import requests

logger = logging.getLogger(__name__)

AUDIO_DIR = os.environ.get('AUDIO_DIR', 'audio')
os.makedirs(AUDIO_DIR, exist_ok=True)

ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY', '')
ELEVENLABS_VOICE_ID = os.environ.get('ELEVENLABS_VOICE_ID', 'ZYCQDYoXnl78dNdU6JeG')

VOICE_EDGE_PRIMARY = 'pt-BR-AntonioNeural'
VOICE_EDGE_FEMALE  = 'pt-BR-FranciscaNeural'

# Configurações de voz por categoria (usa sempre a voz configurada no Railway)
# Variar stability/style cria percepção de "locução diferente" sem precisar de IDs extras
VOICE_SETTINGS_BY_CATEGORY = {
    'esporte': {
        'stability': 0.35,        # mais variação = mais ânimo
        'similarity_boost': 0.75,
        'style': 0.65,            # mais expressivo — narrador esportivo
        'use_speaker_boost': True,
    },
    'policial': {
        'stability': 0.60,        # mais firme, sério
        'similarity_boost': 0.85,
        'style': 0.20,
        'use_speaker_boost': True,
    },
    'saude': {
        'stability': 0.75,        # calmo, tranquilizador
        'similarity_boost': 0.80,
        'style': 0.15,
        'use_speaker_boost': True,
    },
    'clima': {
        'stability': 0.70,
        'similarity_boost': 0.80,
        'style': 0.20,
        'use_speaker_boost': True,
    },
    'politica': {
        'stability': 0.65,
        'similarity_boost': 0.85,
        'style': 0.25,
        'use_speaker_boost': True,
    },
    'economia': {
        'stability': 0.68,
        'similarity_boost': 0.82,
        'style': 0.22,
        'use_speaker_boost': True,
    },
    # padrão para geral/local/cultura
    '_default': {
        'stability': 0.55,
        'similarity_boost': 0.80,
        'style': 0.30,
        'use_speaker_boost': True,
    },
}


def get_voice_settings(category):
    """Retorna as configurações de voz para a categoria da notícia."""
    cat = (category or '').lower()
    return VOICE_SETTINGS_BY_CATEGORY.get(cat, VOICE_SETTINGS_BY_CATEGORY['_default'])


def clean_text_for_tts(text):
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[#@*_\[\]{}|\\^~`]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > 3000:
        text = text[:3000] + '...'
    return text


def build_news_script(title, summary, source=None, city=None):
    parts = []
    if city and city not in ('Santa Catarina', 'geral'):
        parts.append(f"Notícia de {city}.")
    else:
        parts.append("Notícia de Santa Catarina.")
    parts.append(clean_text_for_tts(title) + '.')
    if summary:
        clean_summary = clean_text_for_tts(summary)
        if clean_summary and clean_summary.lower() != clean_text_for_tts(title).lower():
            parts.append(clean_summary)
    if source:
        parts.append(f"Fonte: {source}.")
    return ' '.join(parts)


def _generate_with_elevenlabs(text, filepath, voice_id=None, voice_settings=None):
    """Gera áudio via ElevenLabs API — usa sempre a voz configurada no Railway."""
    api_key = ELEVENLABS_API_KEY
    if not api_key:
        return False

    vid = voice_id or ELEVENLABS_VOICE_ID
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}"

    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    settings = voice_settings or VOICE_SETTINGS_BY_CATEGORY['_default']
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": settings,
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(resp.content)
            return True
        else:
            logger.warning(f"ElevenLabs erro {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        logger.warning(f"ElevenLabs falhou: {e}")
        return False


async def _edge_tts_generate(text, filepath, voice=VOICE_EDGE_PRIMARY):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filepath)


def _generate_with_edge_tts(text, filepath, voice=VOICE_EDGE_PRIMARY):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_edge_tts_generate(text, filepath, voice))
        loop.close()
        return True
    except Exception as e:
        logger.warning(f"edge-tts falhou: {e}")
        return False


def _generate_with_gtts(text, filepath):
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang='pt', slow=False)
        tts.save(filepath)
        return True
    except Exception as e:
        logger.warning(f"gTTS falhou: {e}")
        return False


def generate_audio(title, summary, source=None, city=None, news_id=None, category=None):
    """
    Gera áudio MP3 para uma notícia.
    Voz selecionada automaticamente pela categoria.
    Ordem: ElevenLabs → edge-tts → gTTS
    """
    script = build_news_script(title, summary, source, city)

    filename = f"news_{news_id}.mp3" if news_id else f"news_{hashlib.md5(script.encode()).hexdigest()[:12]}.mp3"
    filepath = os.path.join(AUDIO_DIR, filename)

    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        logger.info(f"Áudio já existe: {filename}")
        return filename

    # 1. ElevenLabs — mesma voz configurada, settings variam por categoria
    settings = get_voice_settings(category)
    if ELEVENLABS_API_KEY and _generate_with_elevenlabs(script, filepath, voice_settings=settings):
        if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
            logger.info(f"Áudio ElevenLabs (cat={category}, stability={settings['stability']}, style={settings['style']}): {filename}")
            return filename
        if os.path.exists(filepath):
            os.remove(filepath)

    # 2. Edge TTS (fallback neural)
    if _generate_with_edge_tts(script, filepath):
        if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
            logger.info(f"Áudio edge-tts (fallback): {filename}")
            return filename
        if os.path.exists(filepath):
            os.remove(filepath)

    # 3. gTTS (último recurso)
    if _generate_with_gtts(script, filepath):
        if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
            logger.info(f"Áudio gTTS (fallback): {filename}")
            return filename

    logger.error(f"Falha total ao gerar áudio: {filename}")
    if os.path.exists(filepath):
        os.remove(filepath)
    return None


def generate_audio_for_ad(text, ad_id):
    """Gera áudio para propaganda."""
    clean = clean_text_for_tts(text)
    script = f"Publicidade. {clean}"

    filename = f"ad_{ad_id}.mp3"
    filepath = os.path.join(AUDIO_DIR, filename)

    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        return filename

    if ELEVENLABS_API_KEY and _generate_with_elevenlabs(script, filepath):
        if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
            return filename
        if os.path.exists(filepath):
            os.remove(filepath)

    if _generate_with_edge_tts(script, filepath, voice=VOICE_EDGE_FEMALE):
        if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
            return filename
        if os.path.exists(filepath):
            os.remove(filepath)

    if _generate_with_gtts(script, filepath):
        if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
            return filename

    return None


if __name__ == '__main__':
    f = generate_audio(
        title="Acidente na BR-280 causa congestionamento em Jaraguá do Sul",
        summary="Um acidente envolvendo dois veículos foi registrado na manhã desta quarta-feira na BR-280, no trecho de Jaraguá do Sul. O trânsito ficou lento por aproximadamente duas horas.",
        source="ND Mais",
        city="Jaraguá do Sul",
        news_id=0
    )
    print(f"Áudio gerado: {f}")
