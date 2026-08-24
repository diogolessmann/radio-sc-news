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
def _aula_viva():
    """📚 AULA DA SEMANA (22/ago): lição escrita toda segunda pelo aula.py com o desempenho
    REAL — o redator aprende com as views sozinho. Vazio se não há aula (prompt como sempre)."""
    try:
        import aula
        txt = aula.ler()
        return f"\n{txt}\n" if txt else ""
    except Exception:
        return ""


def _cicatrizes():
    """🩹 IMUNIDADE ADQUIRIDA (22/ago): erros que o jornal JÁ cometeu, destilados em regras
    permanentes pelo cicatriz.py — o prompt carrega a memória do que já doeu."""
    try:
        import cicatriz
        txt = cicatriz.ler()
        return f"\n{txt}\n" if txt else ""
    except Exception:
        return ""


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
        "- TÍTULO = escolha a fórmula que MELHOR encaixa no fato (ranking real de views do "
        "nosso perfil — 20/ago):\n"
        "  1) 🚨 ALERTA-VIZINHO (a fórmula dos nossos VIRAIS — 236 MIL, 220 MIL, 100 MIL views): "
        "quando for ALERTA REAL de fonte oficial (INMET, Defesa Civil, MetSul, boletim de saúde, "
        "interdição), o título segue o molde 'ATENÇÃO, [ALVO]! [AMEAÇA COM NÚMERO] [JANELA DE "
        "TEMPO]' — ex.: 'ATENÇÃO, VALE! Ciclone traz 100mm e frio de 0°C nas próximas 72h', "
        "'ATENÇÃO, MOTORISTA: saída de Garuva fecha segunda por 90 dias'. O ALVO chama quem o "
        "fato atinge (VALE/VIZINHOS/MOTORISTA/PAIS). O corpo FECHA com um comando de proteção "
        "('prepare', 'abasteça', 'fique ligado') — quem encaminha pro grupo da família está "
        "obedecendo o comando. NUNCA invente alerta: sem fonte oficial, sem fórmula.\n"
        "  1b) COMANDO direto ao leitor: 'PREPARE O CASACO...' fez 36 MIL. Se o fato pede ação "
        "(frio, prazo, inscrição), mande o leitor AGIR no título.\n"
        "  2) FESTA/BENEFÍCIO GRATUITO: festa local fez 16.900. Se tem festa, show, entrada "
        "gratuita, vaga, dinheiro ou prêmio — o BENEFÍCIO vai NO título (e 'GRATUITO' em caixa "
        "alta quando for verdade).\n"
        "  3) NÚMERO CONCRETO: '1.226 vagas', '5 dias de festa', 'R$ 2 milhões'. Número no "
        "título segura o scroll (vagas WEG fez 5.060).\n"
        "  4) PERTENCIMENTO: a cidade no título ('Morador de Schroeder, atenção', 'Só quem é "
        "de Guaramirim...').\n"
        "  5) FOFOCA CONTIDA (ocorrência): conta O QUE aconteceu sem nome/endereço — curiosidade "
        "sem exposição.\n"
        "  6) PERGUNTA que o leitor quer responder nos comentários.\n"
        "- Curto, sem ponto final, SEM clickbait mentiroso (mantém a credibilidade).\n"
        "- PROIBIDO título morno de assessoria ('Empresa realiza ação...', 'Prefeitura promove "
        "evento...') — esse formato fez 227 views enquanto festa fez 16.900. Sempre reescreva "
        "pro ângulo do LEITOR: o que ELE ganha, sente ou precisa fazer.\n"
        + _aula_viva() + _cicatrizes() +
        "- A 1ª linha do CORPO é o SOCO: a informação mais importante primeiro, sem enrolar.\n"
        "- Tom de vizinho bem informado, com a emoção certa (orgulho na conquista, atenção no "
        "alerta). SEM sensacionalismo. NÃO invente NADA (principalmente números e datas).\n"
        "- ⏰ DATAS (fix 20/ago — a Thais pegou 'abre HOJE' num evento de sábado): PROIBIDO "
        "escrever 'hoje', 'amanhã' ou 'ontem' — a matéria pode ir ao ar em outro dia. SEMPRE "
        "o dia da semana + data do texto original: 'neste sábado (22)', 'na quinta-feira (21)'. "
        "Se o texto original só diz 'hoje' sem data, escreva o fato SEM âncora de tempo.\n"
        "- 🏛️ CARGOS (fix 22/ago — saiu 'Antídio foi prefeito de Guaramirim', ele foi prefeito "
        "de JARAGUÁ DO SUL): PROIBIDO atribuir cargo político (prefeito, vereador, deputado de "
        "tal cidade) que não esteja LITERALMENTE no texto original. Nunca deduza o cargo pela "
        "cidade da matéria. FATOS VERIFICADOS (ago/2026): prefeito de Jaraguá do Sul = Jair "
        "Franzner · Guaramirim = Adriano Zimmermann · Schroeder = Jair Bridaroli · Corupá = "
        "Eddy Eipper · Joinville = Rejane Gambin (assumiu em 2026 com a renúncia de Adriano "
        "Silva) · Antídio Lunelli = EX-prefeito de Jaraguá do Sul, hoje candidato ao Senado. "
        "Se o texto original contradisser esta lista, siga o texto e não acrescente nada.\n"
        "- NEUTRALIDADE EM TEMA DIVISIVO: se for política, projeto de lei, câmara/vereadores, "
        "religião em lei ou pauta de costumes — tom 100% INFORMATIVO. PROIBIDO celebrar, lamentar "
        "ou opinar ('que orgulho', 'boa notícia', 'vitória'). O jornal relata; quem opina é o "
        "leitor." + atrib + hint +
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
