# -*- coding: utf-8 -*-
"""
nanobanana.py — Geração de IMAGEM IA de ALTA QUALIDADE p/ posts SEM foto (Rádio SC News).
Só preenche o buraco quando NÃO há foto real E não achou nada no acervo. Não publica.

🎯 META: foto EDITORIAL profissional ("nível Globo"), NÃO ilustração vetorial.
   O teste antigo ficou horrível por 2 motivos: modelo fraco (2.5-flash-image) e prompt de
   "ilustração flat". Aqui: modelo TOP (gemini-3-pro-image / imagen-4) + prompt de fotojornalismo.

REGRAS (guarda-corpos — NÃO mexer sem pensar):
  - Só gera quando NÃO há foto real boa nem imagem no acervo (decisão de quem chama).
  - Imagem é ATMOSFÉRICA/temática (contexto do assunto), NUNCA a cena literal de um fato real,
    NUNCA rosto reconhecível, NUNCA crime/acidente/vítima. Carimba "Arte IA" na capa (honestidade).
  - Categoria sensível (policial) OU sensivel=True -> NÃO gera (devolve None).
  - Cap diário (NANOBANANA_LIMITE_DIA) pra travar o custo.

MODELOS (env NANOBANANA_MODEL):
  - gemini-3-pro-image   -> TOP, 4K nativo, ~$0.134/img (padrão aqui)
  - imagen-4.0-ultra-generate-001 -> foto-realista especialista, ~$0.06/img (mais barato)
  - gemini-2.5-flash-image -> barato mas FRACO (~$0.039) — não recomendado
⚠️ Exige BILLING ativo no projeto Google da chave (imagem não roda no free tier -> 429).
"""
import os
import sys
import base64
from datetime import datetime
from io import BytesIO

import requests

# Console Windows (cp1252) quebra em emoji nos logs — força UTF-8 (igual distribuidor.py).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
NB_MODEL = (os.environ.get("NANOBANANA_MODEL", "gemini-3-pro-image") or "gemini-3-pro-image").strip()
NB_LIMITE_DIA = int(os.environ.get("NANOBANANA_LIMITE_DIA", "10"))   # cap diário (custo controlado)
LIGADO = os.environ.get("NANOBANANA_ON", "0").strip() == "1"         # trava-mestra ON/OFF (default OFF)
W, H = 1080, 1350

# Categorias onde NÃO se gera imagem IA (evita simular cena de fato real/sensível)
SENSIVEIS = {"policial"}

# CENA foto-realista por categoria (contexto atmosférico do assunto — NUNCA o fato específico)
TEMA = {
    "saude":    "A modern, clean Brazilian public health clinic or hospital exterior in soft daylight.",
    "politica": "A civic public building / town hall of a small Brazilian town, flags, calm daylight.",
    "economia": "A busy small-town Brazilian commercial street with local shops, warm daylight.",
    "esporte":  "An amateur football pitch under stadium floodlights at dusk, empty, dramatic sky.",
    "clima":    "Dramatic weather over green rolling hills — heavy storm clouds or golden sunlight breaking through.",
    "cultura":  "A Brazilian community street festival at night, warm string lights, festive glow, crowd seen from behind.",
    "turismo":  "A scenic natural landmark of southern Brazil — a waterfall or viewpoint in lush green hills.",
    "local":    "An aerial view of a cozy small town nestled in a green valley with hills, southern Brazil, golden hour.",
    "geral":    "An aerial view of a small town in a green valley in southern Brazil, community life, warm light.",
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


# ---- prompt (fotografia editorial profissional + guarda-corpos) -------------
def montar_prompt(titulo, categoria, cidade):
    cena = TEMA.get((categoria or "geral"), TEMA["geral"])
    cidade = cidade or "Norte de Santa Catarina, Brazil"
    return (
        f"Professional editorial news photograph. {cena} "
        f"Location vibe: {cidade}, a green valley region in southern Brazil. "
        "STYLE: high-end photojournalism, shot on a full-frame camera with a 35mm lens, "
        "natural cinematic lighting, golden hour, shallow depth of field, tack-sharp focus, "
        "high dynamic range, rich professional color grading, ultra-detailed, 4K, "
        "magazine cover quality, photorealistic. "
        "STRICT RULES: absolutely no text, no words, no letters, no captions, no logos, no watermark. "
        "No recognizable human faces (people, if any, only distant or seen from behind). "
        "Do NOT depict any specific crime, arrest, accident, violence, injury, blood, body or victim — "
        "this is a GENERIC atmospheric context image, never a real event or real person. "
        "Vertical 4:5 composition, keep the lower third slightly darker for a caption overlay."
    )


# ---- geração ----------------------------------------------------------------
def _extrai_imagem(resp_json):
    for cand in resp_json.get("candidates", []):
        for p in (cand.get("content") or {}).get("parts", []):
            inld = p.get("inline_data") or p.get("inlineData")
            if inld and inld.get("data"):
                from PIL import Image
                return Image.open(BytesIO(base64.b64decode(inld["data"]))).convert("RGB")
    return None


def _chamar(prompt, model=None):
    """Chama a API de imagem. Devolve PIL.Image ou levanta erro com o motivo.
    Tenta 2 formatos de body (modelos novos pedem responseModalities IMAGE)."""
    if not GEMINI_API_KEY:
        raise RuntimeError("Sem GEMINI_API_KEY")
    model = model or NB_MODEL
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={GEMINI_API_KEY}")
    parts = [{"parts": [{"text": prompt}]}]
    # 4K OFF por padrão (fix da revisão independente): o pipeline REDUZ tudo pra 1080x1350 em
    # _cover() e o Instagram recomprime — 4K custa +79% ($0.24 vs $0.134) por pixels jogados
    # fora. A qualidade vem do MODELO (gemini-3-pro), não do flag. Religa com NANOBANANA_4K=1.
    q4k = os.environ.get("NANOBANANA_4K", "0").strip() == "1" and "gemini-3" in (model or "")
    bodies = []
    if q4k:
        bodies.append({"contents": parts, "generationConfig": {
            "responseModalities": ["IMAGE"], "imageConfig": {"imageSize": "4K", "aspectRatio": "4:5"}}})
    bodies += [
        {"contents": parts, "generationConfig": {"responseModalities": ["IMAGE"]}},
        {"contents": parts},
    ]
    ultimo = None
    for body in bodies:
        r = requests.post(url, json=body, timeout=120)
        if r.status_code == 429:
            raise RuntimeError("BILLING: cota/billing de imagem não ativado no projeto Google (429). "
                               "Ative o billing no Google AI Studio/Cloud.")
        if r.status_code == 400:      # body inválido p/ esse modelo -> tenta o próximo formato
            ultimo = r.text[:200]
            continue
        r.raise_for_status()
        img = _extrai_imagem(r.json())
        if img:
            return img
        ultimo = "sem inline_data na resposta"
    raise RuntimeError(f"API não devolveu imagem ({ultimo})")


def _cover(img):
    """Redimensiona/corta a imagem da IA p/ 1080x1350 (cobre o card)."""
    iw, ih = img.size
    scale = max(W / iw, H / ih)
    img = img.resize((int(iw * scale), int(ih * scale)))
    iw, ih = img.size
    return img.crop(((iw - W) // 2, (ih - H) // 2, (iw - W) // 2 + W, (ih - H) // 2 + H))


def _salvar_no_acervo(img, titulo, categoria):
    """💾 Salva a imagem gerada no ACERVO IA (volume) sob o slug da situação, p/ REUSO futuro:
    gera 1x, o genericbg reusa de graça nas próximas. Devolve o caminho salvo (ou None).
    1 imagem por slug = economia máxima (não sobrescreve; se já existe, o genericbg já teria pego)."""
    try:
        import genericbg
        slug = genericbg.slug_alvo(titulo, categoria)
        d = genericbg.IA_BG_DIR
        os.makedirs(d, exist_ok=True)
        base = os.path.join(d, slug + ".jpg")
        if not os.path.exists(base):
            img.save(base, quality=95)
            print(f"[nanobanana] 💾 salvo no acervo IA p/ REUSO: {slug}.jpg (volume)")
        return base
    except Exception as e:
        print(f"[nanobanana] não salvou no acervo ({e})")
        return None


def gerar_capa(titulo, categoria, cidade, outdir, sensivel=False):
    """Gera a imagem de fundo (1080x1350) p/ uma notícia SEM foto e SEM acervo.
    Devolve o caminho do PNG, ou None se: OFF, sensível, categoria sensível, cap estourado,
    sem chave, ou erro (billing). NUNCA quebra o fluxo — quem chama usa o card se None.
    A imagem é SALVA no acervo IA (volume) sob o slug -> reuso grátis nas próximas."""
    if (not LIGADO or not disponivel() or sensivel
            or not deve_gerar(categoria) or restante_hoje() <= 0):
        return None
    try:
        img = _cover(_chamar(montar_prompt(titulo, categoria, cidade)))
        _incrementa()
        print(f"[nanobanana] 🎨 imagem IA gerada ({NB_MODEL}) p/ '{(titulo or '')[:40]}'")
        acervo = _salvar_no_acervo(img, titulo, categoria)   # 💾 reuso futuro
        if acervo:
            return acervo
        os.makedirs(outdir, exist_ok=True)
        path = os.path.join(outdir, "nb_fundo.png")
        img.save(path, quality=95)
        return path
    except Exception as e:
        print(f"[nanobanana] não gerou ({e}) — usa card normal")
        return None
