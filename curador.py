# -*- coding: utf-8 -*-
"""
curador.py — 🎨 O EDITOR DE FOTOGRAFIA IA (ideia do dono, 07 e 13/jul).

O motor era CEGO: casava palavra do título com nome de arquivo (regex→slug). O curador
substitui o chute por ENTENDIMENTO: uma IA barata (Gemini Flash)
  1) LÊ a notícia (título+resumo) e o CATÁLOGO do acervo (slugs disponíveis)
  2) DECIDE: usar a imagem X do acervo · gerar uma nova sob medida · ou card de marca
  3) (opcional) OLHA a imagem escolhida e confirma que combina com a manchete

Travas:
  CURADOR_ON         default 1 (precisa GEMINI_API_KEY; sem chave = no-op)
  CURADOR_VE_IMAGEM  default 1 (nível 2: visão confere a imagem escolhida)
  CURADOR_MODEL      default gemini-2.5-flash (rápido/barato)

SEGURANÇA (mesmas regras da casa):
  - FAIL-SAFE total: qualquer falha → None → o fluxo antigo (regex) decide. Zero regressão.
  - Notícia SENSÍVEL (crime/morte/acidente c/ vítima): curador pode USAR imagem neutra do
    acervo ou CARD — NUNCA manda gerar (não se fabrica cena de tragédia). O nanobanana
    ainda tem a própria trava (cinto e suspensório).
  - A cena gerada é ATMOSFÉRICA do TEMA, nunca a cena literal do fato (regra no prompt).
"""
import json
import os
import re
import sys

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
MODEL = (os.environ.get("CURADOR_MODEL", "gemini-2.5-flash") or "gemini-2.5-flash").strip()


def ativo():
    return os.environ.get("CURADOR_ON", "1").strip() != "0" and bool(GEMINI_API_KEY)


def _ve_imagem():
    return os.environ.get("CURADOR_VE_IMAGEM", "1").strip() != "0"


# ---------------------------------------------------------------- API helpers
def _gemini(parts, max_tokens=220, timeout=25):
    """Chamada Gemini com thinking off (2.5). Devolve texto ou None (fail-safe)."""
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{MODEL}:generateContent?key={GEMINI_API_KEY}")
    cfg = {"temperature": 0.0, "maxOutputTokens": max_tokens}
    tentativas = [
        {"contents": [{"parts": parts}],
         "generationConfig": {**cfg, "thinkingConfig": {"thinkingBudget": 0}}},
        {"contents": [{"parts": parts}], "generationConfig": cfg},
    ]
    for body in tentativas:
        try:
            r = requests.post(url, headers={"Content-Type": "application/json"},
                              json=body, timeout=timeout)
            r.raise_for_status()
            cand = (r.json().get("candidates") or [{}])[0]
            if cand.get("finishReason") == "MAX_TOKENS":
                continue
            txt = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []))
            if txt.strip():
                return txt.strip()
        except Exception as e:
            print(f"[curador] gemini falhou ({e})")
            break
    return None


def _jpeg_b64(path):
    import base64
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return None


# ---------------------------------------------------------------- catálogo
def catalogo():
    """Slugs disponíveis no arsenal fixo (static/bg) + acervo IA (volume), sem -N/extensão."""
    import genericbg as g
    slugs = set()
    for root in (g.BG_DIR, g.IA_BG_DIR):
        if not os.path.isdir(root):
            continue
        for f in os.listdir(root):
            base, ext = os.path.splitext(f)
            if ext.lower() not in g.EXTS:
                continue
            slugs.add(re.sub(r"-\d+$", "", base))
    return sorted(slugs)


# ---------------------------------------------------------------- nível 1: decidir
def escolher(news, sensivel=False):
    """LÊ a notícia + catálogo e decide o fundo. Devolve dict
    {"acao": "usar"|"gerar"|"card", "slug": str|None, "cena": str|None} ou None (fail-safe)."""
    if not ativo():
        return None
    slugs = catalogo()
    if not slugs:
        return None
    titulo = (news["title_own"] if _has(news, "title_own") else None) or news["title"] or ""
    resumo = ((news["resumo_own"] if _has(news, "resumo_own") else None)
              or (news["summary"] if _has(news, "summary") else None) or "")[:400]
    cidade = news["city"] or "Norte de SC"
    regras_gerar = ("" if sensivel else
                    '2) Se NADA do acervo combina e o tema é seguro (SEM crime/morte/vítima): '
                    '{"acao":"gerar","slug":"<slug_novo_curto_minusculo>","cena":"<one-line English '
                    'photo scene of the THEME: atmospheric, no recognizable people, no text, '
                    'NEVER the literal real event>"}\n')
    prompt = (
        "Você é o EDITOR DE FOTOGRAFIA de um portal de notícias local do Norte de Santa Catarina. "
        "Escolha o FUNDO da capa desta notícia.\n\n"
        f"NOTÍCIA: {titulo}\nRESUMO: {resumo}\nCIDADE: {cidade}\n\n"
        f"ACERVO DISPONÍVEL (slugs): {', '.join(slugs)}\n\n"
        "Responda APENAS um JSON:\n"
        '1) Se um slug do acervo combina BEM com o TEMA da notícia: {"acao":"usar","slug":"<slug>"}\n'
        f"{regras_gerar}"
        '3) Se nada serve: {"acao":"card"}\n\n'
        "REGRAS: o fundo é do TEMA, não da cena literal; prefira slug de SITUAÇÃO sobre slug de "
        "cidade; slug de cidade só se a notícia é daquela cidade; ESPORTE pede campo de "
        "jogo/estádio/quadra (NUNCA paisagem rural, trator ou e-sports); combine o CLIMA exato "
        "(frio/geada ≠ tempestade ≠ sol); ANIMAL: a espécie tem que bater — notícia de TARTARUGA "
        "não usa slug de cachorro: prefira \"gerar\" com a espécie certa (ex.: slug tartaruga_marinha, "
        "cena da espécie em ambiente natural, SEM pessoas); TEMA POLICIAL/CRIME: NUNCA slug de "
        "cidade (cidade_*) nem de prédio público (prefeitura/camara/escola/igreja) — lugar "
        "identificável associado a crime é risco jurídico; use \"policial\"/\"seguranca\" ou \"card\"; "
        "em dúvida, \"card\". Só o JSON."
    )
    txt = _gemini([{"text": prompt}])
    if not txt:
        return None
    txt = re.sub(r"^```(json)?|```$", "", txt.strip(), flags=re.MULTILINE).strip()
    try:
        dec = json.loads(txt)
    except Exception:
        m = re.search(r"\{.*\}", txt, re.DOTALL)
        if not m:
            return None
        try:
            dec = json.loads(m.group(0))
        except Exception:
            return None
    acao = (dec.get("acao") or "").strip().lower()
    if acao not in ("usar", "gerar", "card"):
        return None
    slug = re.sub(r"[^a-z0-9_]", "", (dec.get("slug") or "").strip().lower())[:30] or None
    if acao == "usar" and (not slug or slug not in slugs):
        return None                                    # escolheu slug que não existe -> fail-safe
    if acao == "gerar" and sensivel:
        acao, slug = "card", None                      # trava dura: sensível nunca gera
    if acao == "usar" and sensivel:
        # 🔴 trava dura (fix 16/jul: câmara de Schroeder ilustrou lavagem de dinheiro): em tema
        # sensível, prédio público/cidade identificável NUNCA — só fundo neutro ou card.
        import genericbg
        if genericbg._slug_proibido_sensivel(slug):
            acao, slug = "card", None
    cena = (dec.get("cena") or "").strip()[:220] or None
    print(f"[curador] 📖 decisão: {acao}" + (f" -> {slug}" if slug else ""))
    return {"acao": acao, "slug": slug, "cena": cena}


# ---------------------------------------------------------------- nível 2: conferir
def combina(img_path, news):
    """OLHA a imagem escolhida e confirma se combina como fundo da manchete.
    True/False; em falha devolve True (fail-open: a escolha do nível 1 vale)."""
    if not ativo() or not _ve_imagem():
        return True
    b64 = _jpeg_b64(img_path)
    if not b64:
        return True
    titulo = (news["title_own"] if _has(news, "title_own") else None) or news["title"] or ""
    parts = [
        {"text": ("Esta imagem serve como FUNDO editorial para esta manchete de notícia local?\n"
                  f"MANCHETE: {titulo}\n\n"
                  "CRITÉRIO (criterioso, não perfeccionista):\n"
                  "- SIM se o ASSUNTO CENTRAL da imagem combina com o TEMA da manchete. O fundo é "
                  "ILUSTRATIVO do tema — NÃO precisa ser a cena nem o indivíduo exato da notícia "
                  "(ex.: foto de um cachorro de rua SERVE para 'cachorro resgatado'; chuva serve "
                  "para alagamento; um estádio serve para futebol).\n"
                  "- NAO se o assunto central da imagem é OUTRO tema: rural/trator NÃO serve para "
                  "futebol; tempestade/raio NÃO serve para frio/geada; e-sports/gamer NÃO serve "
                  "para futebol; e em ANIMAIS a ESPÉCIE precisa bater (cachorro NÃO serve para "
                  "tartaruga, e vice-versa).\n"
                  "Responda APENAS uma palavra: SIM ou NAO.")},
        {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
    ]
    txt = (_gemini(parts, max_tokens=10, timeout=30) or "").upper()
    if "NAO" in txt or "NÃO" in txt:
        print("[curador] 👁️ imagem escolhida NÃO combina — tentando alternativa")
        return False
    return True


def _has(row, key):
    try:
        return row[key] is not None
    except Exception:
        return False
