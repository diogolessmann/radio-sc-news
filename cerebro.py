# -*- coding: utf-8 -*-
"""
cerebro.py — Roteador de IA HÍBRIDO ("central de cérebros") da Rádio SC News.

Fala com os 3 cérebros via HTTP puro (requests) — NÃO precisa instalar SDK nenhum:
  ⚡ GROQ    (grátis)   — motor de volume        env: GROQ_API_KEY  / GROQ_MODEL
  👁️ GEMINI  (pago)     — padrão, bom PT-BR       env: GEMINI_API_KEY / GEMINI_MODEL
  🧠 CLAUDE  (premium)  — escalonamento/qualidade env: ANTHROPIC_API_KEY / CLAUDE_MODEL

Roteamento (brain="auto"): tenta Gemini → Groq → fallback local (sempre responde).
Claude só entra quando pedido explicitamente (brain="claude") — é a faixa premium.
Se um cérebro falha/sem chave, cai pro próximo sozinho (resiliência).
"""
import os
import re

import requests

# ----------------------------------------------------------------- chaves/config
def _env(name, default=""):
    v = os.environ.get(name)
    return (v.strip() if v else default)

GROQ_API_KEY = _env("GROQ_API_KEY")
GROQ_MODEL = _env("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

GEMINI_API_KEY = _env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY")
GEMINI_MODEL = _env("GEMINI_MODEL", "gemini-2.5-flash")  # modelo atual; troque via env se quiser

ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY")
CLAUDE_MODEL = _env("CLAUDE_MODEL", "claude-opus-4-8")  # p/ economizar: claude-haiku-4-5


def _mask(msg):
    """Tira chave/token de mensagens de erro antes de logar (a chave vinha na URL ?key=...)."""
    s = str(msg)
    s = re.sub(r"(key=)[\w.\-]+", r"\1***", s)
    s = re.sub(r"(Bearer\s+)[\w.\-]+", r"\1***", s)
    s = re.sub(r"(AIza|sk-|gsk_)[\w.\-]+", r"\1***", s)
    return s


def disponiveis():
    """Quais cérebros têm chave configurada (a UI usa pra mostrar os botões)."""
    return {"gemini": bool(GEMINI_API_KEY), "groq": bool(GROQ_API_KEY),
            "claude": bool(ANTHROPIC_API_KEY)}


# ----------------------------------------------------------------- prompt comum
def _build_prompt(bruto, cidade, fonte, titulo_hint):
    atrib = (f" Atribua a informação à fonte: {fonte}." if fonte else
             " Se for afirmação de um único lado (político/partidário), deixe claro que é "
             "segundo a fonte.")
    hint = f" Sugestão de manchete (pode melhorar): {titulo_hint}." if titulo_hint else ""
    return (
        "Você é editor da Rádio SC News (Norte de SC). Reescreva como A NOSSA notícia em português "
        "do Brasil, estilo TIKTOK: CURTA, direta e que SEGURA O SCROLL. A pessoa lê em ~10 segundos "
        "e JÁ ENTENDE tudo, sem clicar em nada.\n"
        "REGRAS DE GANCHO (pra render no Instagram):\n"
        "- TÍTULO = um gancho forte e ESPECÍFICO. Pode ser pergunta, número concreto, ou alerta "
        "local citando a cidade (ex.: 'Morador de Schroeder, atenção'). Curto, sem ponto final, "
        "SEM clickbait mentiroso (mantém a credibilidade).\n"
        "- A 1ª linha do CORPO é o SOCO: a informação mais importante primeiro, sem enrolar.\n"
        "- Tom de vizinho bem informado, com a emoção certa (orgulho na conquista, atenção no "
        "alerta). SEM sensacionalismo. NÃO invente NADA (principalmente números e datas)." + atrib + hint +
        " Responda EXATAMENTE neste formato:\n"
        "TITULO: <gancho forte e curto, sem ponto final>\n"
        "CORPO: <NO MÁXIMO 5 linhas curtas, 1 frase punchy por linha; a 1ª linha é o fato principal>\n\n"
        f"CIDADE: {cidade}\nINFORMAÇÃO BRUTA:\n{bruto}"
    )


def _parse(txt):
    m = re.search(r"(?is)titulo:\s*(.+?)\s*corpo:\s*(.+)$", txt or "")
    if m:
        return m.group(1).strip().strip('"'), m.group(2).strip().strip('"')
    return None


# ----------------------------------------------------------------- backends (HTTP)
def _groq(prompt):
    if not GROQ_API_KEY:
        return None
    try:
        r = requests.post(GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": GROQ_MODEL, "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.4, "max_tokens": 360}, timeout=30)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[cerebro] Groq falhou: {_mask(e)}")
        return None


def _gemini(prompt, model=None):
    if not GEMINI_API_KEY:
        return None
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model or GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}")
    cfg = {"temperature": 0.4, "maxOutputTokens": 1024}
    # Modelos 2.5 são "thinking" e gastam o orçamento pensando — desliga (é só reescrever).
    # 1ª tentativa com thinking OFF; se o modelo não suportar, refaz sem o campo (modelos 1.5/2.0).
    tentativas = [
        {"contents": [{"parts": [{"text": prompt}]}],
         "generationConfig": {**cfg, "thinkingConfig": {"thinkingBudget": 0}}},
        {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": cfg},
    ]
    for body in tentativas:
        try:
            r = requests.post(url, headers={"Content-Type": "application/json"}, json=body, timeout=40)
            r.raise_for_status()
            cand = (r.json().get("candidates") or [{}])[0]
            # resposta TRUNCADA (estourou tokens — ex: o "thinking" comeu o orçamento) corta a frase
            # no meio (saiu "...100KM/H, GRAN" na capa) -> descarta pra cair no fallback LIMPO (título)
            # em vez de publicar pela metade.
            if cand.get("finishReason") == "MAX_TOKENS":
                continue
            parts = (cand.get("content") or {}).get("parts", [])
            txt = "".join(p.get("text", "") for p in parts).strip()
            if txt:
                return txt
        except Exception as e:
            print(f"[cerebro] Gemini tentativa falhou: {_mask(e)}")
    return None


def _claude(prompt):
    if not ANTHROPIC_API_KEY:
        return None
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": CLAUDE_MODEL, "max_tokens": 500,
                  "messages": [{"role": "user", "content": prompt}]}, timeout=60)
        r.raise_for_status()
        # content é uma lista de blocos; pega o 1º texto
        for b in r.json().get("content", []):
            if b.get("type") == "text":
                return b["text"].strip()
        return None
    except Exception as e:
        print(f"[cerebro] Claude falhou: {_mask(e)}")
        return None


_BACKENDS = {"groq": _groq, "gemini": _gemini, "claude": _claude}


def completar(prompt, brain="auto", model=None):
    """Roteia um PROMPT qualquer pro melhor cérebro e devolve o TEXTO cru.
    auto = Gemini -> Groq. None se nenhum responder (quem chama trata o fallback).
    model (opcional): força um modelo Gemini específico só nesta chamada (ex: premium pago)."""
    ordem = [brain] if brain in _BACKENDS else ["gemini", "groq"]
    for nome in ordem:
        out = _gemini(prompt, model) if (nome == "gemini" and model) else _BACKENDS[nome](prompt)
        if out:
            return out.strip()
    return None


# ----------------------------------------------------------------- roteador
def gerar_texto(bruto, cidade="Schroeder", fonte="", titulo_hint="", brain="auto"):
    """Reescreve no tom da Rádio. Devolve (titulo, corpo, cerebro_usado).
    brain: 'auto' (Gemini→Groq), 'gemini', 'groq', 'claude'. Sempre cai no fallback local."""
    prompt = _build_prompt(bruto, cidade, fonte, titulo_hint)

    if brain == "auto":
        ordem = ["gemini", "groq"]
    elif brain in _BACKENDS:
        ordem = [brain]
    else:
        ordem = ["gemini", "groq"]

    for nome in ordem:
        out = _BACKENDS[nome](prompt)
        parsed = _parse(out) if out else None
        if parsed:
            return parsed[0], parsed[1], nome

    # fallback local (nunca deixa o usuário na mão) — reusa o redator.py
    try:
        import redator
        t, c = redator.redator_local(bruto, titulo_hint, fonte)
        return t, c, "local"
    except Exception:
        # último recurso bruto
        corpo = re.sub(r"\s+", " ", bruto).strip()
        titulo = titulo_hint or corpo[:80]
        return titulo, corpo, "local"
