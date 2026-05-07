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

# Vozes por categoria — ElevenLabs
VOICES_GENERAL  = [
    'ZYCQDYoXnl78dNdU6JeG',  # voz original
    'xNGAXaCH8MaasNuo7Hr7',  # masculina notícia
    'czvzJwIVS2asEKnthV40',  # masculina comunicação
]
VOICES_FEMALE   = [
    'RGymW84CSmfVugnA5tvA',  # feminina 1
    '7eUAxNOneHxqfyRS77mW',  # feminina 2
]
VOICE_FOOTBALL  = 'YU8EsJtXFMyKMxYtheDk'  # narrador esportivo animado


def get_voice_for_category(category):
    """Retorna o Voice ID adequado para a categoria da notícia."""
    import random
    cat = (category or '').lower()
    if cat == 'esporte':
        return VOICE_FOOTBALL
    if cat == 'breaking':
        return random.choice(VOICES_FEMALE)
    if cat in ('clima', 'saude'):
        return random.choice(VOICES_FEMALE)
    return random.choice(VOICES_GENERAL)


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


def _generate_with_elevenlabs(text, filepath, voice_id=None):
    """Gera áudio via ElevenLabs API — voz de locutor profissional."""
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
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.55,
            "similarity_boost": 0.80,
            "style": 0.30,
            "use_speaker_boost": True,
        },
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

    # 1. ElevenLabs — voz selecionada pela categoria
    voice_id = get_voice_for_category(category)
    if ELEVENLABS_API_KEY and _generate_with_elevenlabs(script, filepath, voice_id=voice_id):
        if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
            logger.info(f"Áudio ElevenLabs ({category}) gerado: {filename}")
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
