"""
tts_engine.py — Geração de áudio com voz neural (Microsoft Edge TTS)
Voz: pt-BR-AntonioNeural — narração estilo rádio, natural e fluente
Fallback: gTTS (Google) caso edge-tts falhe
"""
import os
import re
import asyncio
import logging
import hashlib

logger = logging.getLogger(__name__)

AUDIO_DIR = os.environ.get('AUDIO_DIR', 'audio')
os.makedirs(AUDIO_DIR, exist_ok=True)

# Voz principal — António soa como locutor de rádio
VOICE_PRIMARY  = 'pt-BR-AntonioNeural'
# Alternativa feminina natural
VOICE_FEMALE   = 'pt-BR-FranciscaNeural'


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


async def _edge_tts_generate(text, filepath, voice=VOICE_PRIMARY):
    """Gera áudio via edge-tts (voz neural Microsoft)."""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filepath)


def _generate_with_edge_tts(text, filepath, voice=VOICE_PRIMARY):
    """Wrapper síncrono para o edge-tts assíncrono."""
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
    """Fallback: Google TTS."""
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang='pt', slow=False)
        tts.save(filepath)
        return True
    except Exception as e:
        logger.warning(f"gTTS falhou: {e}")
        return False


def generate_audio(title, summary, source=None, city=None, news_id=None):
    """
    Gera áudio MP3 para uma notícia.
    Usa edge-tts (voz neural) com fallback para gTTS.
    Retorna o nome do arquivo ou None em caso de erro.
    """
    script = build_news_script(title, summary, source, city)

    filename = f"news_{news_id}.mp3" if news_id else f"news_{hashlib.md5(script.encode()).hexdigest()[:12]}.mp3"
    filepath = os.path.join(AUDIO_DIR, filename)

    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        logger.info(f"Áudio já existe: {filename}")
        return filename

    # Tenta edge-tts primeiro (voz de rádio)
    if _generate_with_edge_tts(script, filepath):
        size = os.path.getsize(filepath)
        if size > 1000:
            logger.info(f"Áudio neural gerado: {filename} ({size} bytes)")
            return filename
        os.remove(filepath)

    # Fallback: gTTS
    if _generate_with_gtts(script, filepath):
        size = os.path.getsize(filepath)
        if size > 1000:
            logger.info(f"Áudio gTTS (fallback): {filename} ({size} bytes)")
            return filename

    logger.error(f"Falha total ao gerar áudio: {filename}")
    if os.path.exists(filepath):
        os.remove(filepath)
    return None


def generate_audio_for_ad(text, ad_id):
    """Gera áudio para propaganda com voz feminina."""
    clean = clean_text_for_tts(text)
    script = f"Publicidade. {clean}"

    filename = f"ad_{ad_id}.mp3"
    filepath = os.path.join(AUDIO_DIR, filename)

    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        return filename

    if _generate_with_edge_tts(script, filepath, voice=VOICE_FEMALE):
        if os.path.getsize(filepath) > 1000:
            return filename
        os.remove(filepath)

    if _generate_with_gtts(script, filepath):
        if os.path.getsize(filepath) > 1000:
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
