# -*- coding: utf-8 -*-
"""
visao_imagem.py — 👁️ A IA que OLHA a foto (camada anti-Chapecó).

O motor é CEGO: ele casa o NOME do arquivo com a palavra do título, nunca vê o pixel.
Aqui uma IA barata (Gemini Flash) OLHA a foto REAL da fonte ANTES de publicar e diz se
tem rosto/corpo/sangue/criança — coisas que o filtro de TEXTO não pega (foi o buraco do
incidente de Chapecó: matéria de crime + foto do rosto da vítima que o texto não revelava).

Uso:  motivo = foto_perigosa(img)      # img: caminho | URL | bytes | PIL.Image
      if motivo: ... não usa a foto ...

Travas:
  VISAO_IA_ON     default LIGADO (precisa de GEMINI_API_KEY; sem chave, no-op silencioso)
  VISAO_IA_MODEL  default gemini-2.5-flash (barato, ~centavos por imagem)

SEGURANÇA:
  - FAIL-OPEN de SISTEMA: se a IA estiver fora do ar / sem chave / erro -> devolve None
    (NÃO trava o post; o regex de texto + a allowlist de categoria seguem protegendo).
  - CAUTELA de CONTEÚDO: "na dúvida, PERIGOSA" (barra a foto, usa a NOSSA imagem).
  - Ela só DERRUBA uma foto de fonte para uma imagem NOSSA (arsenal/Street View).
    Nunca introduz uma imagem nova nem publica nada — impossível piorar a segurança.
"""
import base64
import io
import os

import requests

GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
VISAO_MODEL = (os.environ.get("VISAO_IA_MODEL", "gemini-2.5-flash") or "gemini-2.5-flash").strip()


def ativo():
    return os.environ.get("VISAO_IA_ON", "1").strip() != "0" and bool(GEMINI_API_KEY)


_PROMPT = (
    "Você é o filtro de segurança de imagem de um jornal. Esta foto PODE ser publicada numa "
    "notícia. Responda APENAS com uma palavra: PERIGOSA ou OK.\n\n"
    "Responda PERIGOSA se a imagem mostrar QUALQUER um destes:\n"
    "- rosto humano reconhecível de pessoa comum (NÃO é autoridade/artista em ato público);\n"
    "- pessoa presa, algemada, detida ou sendo abordada pela polícia;\n"
    "- corpo, cadáver, pessoa ferida ou vítima de acidente;\n"
    "- sangue, ferimento, violência ou sofrimento humano;\n"
    "- criança ou adolescente identificável;\n"
    "- nudez ou conteúdo constrangedor.\n\n"
    "Responda OK se for: paisagem, prédio, rua, mapa, veículo SEM vítima, objeto, comida, "
    "clima/tempo, animal, plantação, esporte com atletas na quadra/campo, multidão distante "
    "sem rosto em foco, ou autoridade/figura pública em evento oficial.\n\n"
    "Na dúvida, responda PERIGOSA. Responda só UMA palavra."
)


def _to_jpeg_b64(img):
    """Aceita caminho | URL | bytes | PIL.Image e devolve (base64, mime) ou (None, None)."""
    data = None
    try:
        if hasattr(img, "save"):                      # PIL.Image
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=80)
            data = buf.getvalue()
        elif isinstance(img, (bytes, bytearray)):
            data = bytes(img)
        elif isinstance(img, str) and img.lower().startswith("http"):
            r = requests.get(img, timeout=20)
            r.raise_for_status()
            data = r.content
        elif isinstance(img, str) and os.path.exists(img):
            with open(img, "rb") as f:
                data = f.read()
    except Exception:
        return None, None
    if not data:
        return None, None
    return base64.b64encode(data).decode("ascii"), "image/jpeg"


def foto_perigosa(img):
    """Devolve um motivo (str curta) se a IA achar a foto PERIGOSA; None se OK / sem chave / erro.
    FAIL-OPEN: qualquer falha -> None (não trava o post; as outras travas seguem valendo)."""
    if not ativo():
        return None
    b64, mime = _to_jpeg_b64(img)
    if not b64:
        return None
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{VISAO_MODEL}:generateContent?key={GEMINI_API_KEY}")
    parts = [{"text": _PROMPT}, {"inline_data": {"mime_type": mime, "data": b64}}]
    cfg = {"temperature": 0.0, "maxOutputTokens": 10}
    # 2.5 é "thinking" e come o orçamento pensando -> desliga; se o modelo não suportar, refaz sem.
    tentativas = [
        {"contents": [{"parts": parts}], "generationConfig": {**cfg, "thinkingConfig": {"thinkingBudget": 0}}},
        {"contents": [{"parts": parts}], "generationConfig": cfg},
    ]
    for body in tentativas:
        try:
            r = requests.post(url, headers={"Content-Type": "application/json"}, json=body, timeout=30)
            r.raise_for_status()
            cand = (r.json().get("candidates") or [{}])[0]
            if cand.get("finishReason") == "MAX_TOKENS":
                continue                                   # pensou demais -> tenta sem thinking
            txt = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []))
            txt = txt.strip().upper()
            if "PERIGOSA" in txt:
                return "visao_ia: rosto/corpo/cena sensivel"
            if "OK" in txt:
                return None                                # veredito claro: liberada
        except Exception as e:
            print(f"[visao_imagem] falhou (fail-open, nao trava o post): {e}")
            break
    return None
