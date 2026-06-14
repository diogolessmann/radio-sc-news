# -*- coding: utf-8 -*-
"""
nanobanana.py — Geração SELETIVA de imagem IA (Gemini "Nano Banana") p/ posts SEM foto.
Rádio SC News — só preenche o buraco quando falta imagem boa. Não publica.

REGRAS (guardrail):
  - Só gera quando NÃO há foto real boa (decisão de quem chama).
  - Imagem é ILUSTRATIVA/temática (estilo editorial), NUNCA "foto" realista de fato real.
  - Categorias sensíveis (policial/acidente) -> NÃO gera (devolve None) p/ não simular cena.
  - Cap diário (default 3/dia) pra controlar custo/cota durante o teste.

API (descoberta jun/2026): POST v1beta/models/<modelo>:generateContent?key=...
  body = {"contents":[{"parts":[{"text": prompt}]}]}  (SEM generationConfig)
  resposta: parts[].inline_data.data (base64 PNG)
⚠️ Exige BILLING ativado no projeto Google da chave (senão 429). Texto roda no free tier;
   imagem não. Ative o billing no Google AI Studio/Cloud pra usar.
"""
import os
import base64
from datetime import datetime
from io import BytesIO

import requests

GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
# gemini-2.5-flash-image = barato (~$0.039). p/ mais bonito: gemini-3-pro-image
NB_MODEL = os.environ.get("NANOBANANA_MODEL", "gemini-2.5-flash-image").strip()
NB_LIMITE_DIA = int(os.environ.get("NANOBANANA_LIMITE_DIA", "2"))   # cap diário (teste: 1-2/dia)
LIGADO = os.environ.get("NANOBANANA_ON", "0").strip() == "1"        # trava-mestra ON/OFF (default OFF)
W, H = 1080, 1350

# Categorias onde NÃO se gera imagem IA (evita simular cena de fato real)
SENSIVEIS = {"policial"}

# Tema visual por categoria (vira a "ideia" da ilustração)
TEMA = {
    "saude":    "health and care symbols (stethoscope, heart, medical cross)",
    "politica": "civic theme, public administration, town hall building silhouette",
    "economia": "local economy, commerce, growth chart, coins (abstract)",
    "esporte":  "amateur football, stadium lights, sport energy",
    "clima":    "weather scene, clouds, rain or sun over hills",
    "cultura":  "community festival, music and celebration, lights",
    "local":    "small town in a green valley in southern Brazil, hills, cozy",
    "geral":    "small town in a green valley in southern Brazil, community life",
}


def disponivel():
    return bool(GEMINI_API_KEY)


def deve_gerar(categoria):
    """True se PODE gerar imagem IA p/ essa categoria (não sensível)."""
    return (categoria or "geral") not in SENSIVEIS


# ---- cap diário -------------------------------------------------------------
def _contador_path():
    d = os.path.join("static", "redacao")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f".nb_{datetime.now():%Y%m%d}.count")


def restante_hoje():
    p = _contador_path()
    usados = 0
    if os.path.exists(p):
        try:
            usados = int(open(p).read().strip() or "0")
        except Exception:
            usados = 0
    return max(0, NB_LIMITE_DIA - usados)


def _incrementa():
    p = _contador_path()
    usados = 0
    if os.path.exists(p):
        try:
            usados = int(open(p).read().strip() or "0")
        except Exception:
            usados = 0
    open(p, "w").write(str(usados + 1))


# ---- prompt (contextual + guardrail) ---------------------------------------
def montar_prompt(titulo, categoria, cidade):
    tema = TEMA.get((categoria or "geral"), TEMA["geral"])
    cidade = cidade or "Norte de Santa Catarina"
    return (
        "Editorial news illustration for a local Brazilian news brand. "
        f"Theme: {tema}. Context: {cidade}, southern Brazil. "
        "Modern flat vector / editorial graphic style, clean and professional. "
        "Dark navy background (#111218) with subtle red and gold accents. "
        "IMPORTANT: this is a stylized ILLUSTRATION, NOT a photograph, NOT a realistic "
        "depiction of any real event or real people. No text, no words, no logos. "
        "Vertical 4:5 composition, leave the lower third darker for caption overlay."
    )


# ---- geração ----------------------------------------------------------------
def _chamar(prompt, model=None):
    """Chama a API de imagem. Devolve PIL.Image ou levanta erro com o motivo."""
    if not GEMINI_API_KEY:
        raise RuntimeError("Sem GEMINI_API_KEY")
    model = model or NB_MODEL
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={GEMINI_API_KEY}")
    r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=120)
    if r.status_code == 429:
        raise RuntimeError("BILLING: cota/billing de imagem não ativado no projeto Google (429). "
                           "Ative o billing no Google AI Studio/Cloud.")
    r.raise_for_status()
    for p in r.json()["candidates"][0]["content"]["parts"]:
        inld = p.get("inline_data") or p.get("inlineData")
        if inld and inld.get("data"):
            from PIL import Image
            return Image.open(BytesIO(base64.b64decode(inld["data"]))).convert("RGB")
    raise RuntimeError("API não devolveu imagem (só texto?)")


def _cover(img):
    """Redimensiona/corta a imagem da IA p/ 1080x1350 (cobre o card)."""
    iw, ih = img.size
    scale = max(W / iw, H / ih)
    img = img.resize((int(iw * scale), int(ih * scale)))
    iw, ih = img.size
    return img.crop(((iw - W) // 2, (ih - H) // 2, (iw - W) // 2 + W, (ih - H) // 2 + H))


def gerar_capa(titulo, categoria, cidade, outdir):
    """Gera a imagem de fundo (1080x1350) p/ uma notícia SEM foto.
    Devolve o caminho do PNG, ou None se: categoria sensível, cap diário estourado,
    sem chave, ou erro (billing). NUNCA quebra o fluxo — quem chama usa o card normal se None."""
    if not LIGADO or not disponivel() or not deve_gerar(categoria) or restante_hoje() <= 0:
        return None
    try:
        img = _cover(_chamar(montar_prompt(titulo, categoria, cidade)))
        os.makedirs(outdir, exist_ok=True)
        path = os.path.join(outdir, "nb_fundo.png")
        img.save(path, quality=92)
        _incrementa()
        return path
    except Exception as e:
        print(f"[nanobanana] não gerou ({e}) — usa card normal")
        return None
