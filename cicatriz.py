# -*- coding: utf-8 -*-
"""🩹 CICATRIZES — imunidade adquirida do motor (22/ago/2026).

A AULA ensina o que RENDE; a CICATRIZ ensina o que já DOEU. Cada erro que o
checador pegou, que o leitor segurou ou que humano corrigiu vira uma regra
permanente de 1 linha em DATA_DIR/cicatrizes.txt — e o cerebro anexa o bloco
"NUNCA repita" ao prompt de toda reescrita. O motor coleciona anticorpos sozinho:
daqui meses, o prompt carrega a memória de tudo que já saiu errado e foi curado.

Toda segunda 07h20 o job lê as pegas novas do checador_log.jsonl (desde o último
marco) e DESTILA em regras generalizadas via IA (o motivo cru "disse que Antídio
foi prefeito de Guaramirim" vira "nunca deduza cargo político pela cidade").
IA fora do ar = semana pulada, o log espera. Máx 15 cicatrizes no prompt (as mais
antigas são as fundadoras — quando encher, a IA consolida as parecidas).
"""
import json
import logging
import os
import re
from datetime import datetime

logger = logging.getLogger(__name__)

DATA_DIR = os.environ.get("DATA_DIR", ".")
CIC_PATH = os.path.join(DATA_DIR, "cicatrizes.txt")
MARCO_PATH = os.path.join(DATA_DIR, "cicatriz_marco.txt")
MAX_CICATRIZES = 15

# As feridas fundadoras — os 4 erros reais que já publicamos e curamos no código.
_SEMENTES = [
    "NUNCA deduza cargo político pela cidade da matéria (já publicamos 'Antídio prefeito de "
    "Guaramirim' — ele foi prefeito de Jaraguá do Sul; leitores corrigiram nos comentários).",
    "NUNCA escreva 'hoje', 'amanhã' ou 'ontem' — o post pode ir ao ar em outro dia (já saiu "
    "'abre HOJE' num evento que era sábado).",
    "NUNCA deixe meta-fala de assistente na resposta ('Atenção:', 'segue o texto', 'como "
    "IA') — já publicamos o prompt vazado uma vez.",
    "NUNCA trate prazo/edital/concurso de ano passado como atual (já publicamos concurso de "
    "2025 requentado por site caça-clique como se fosse aberto).",
]


def _carregar():
    try:
        with open(CIC_PATH, encoding="utf-8") as f:
            return [l.strip() for l in f if l.strip()]
    except FileNotFoundError:
        _salvar(_SEMENTES)
        return list(_SEMENTES)
    except Exception:
        return []


def _salvar(linhas):
    try:
        with open(CIC_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(linhas[:MAX_CICATRIZES * 2]) + "\n")
    except Exception as e:
        logger.error(f"🩹 não salvou cicatrizes: {e}")


def _chave(txt):
    return re.sub(r"\W+", "", (txt or "").lower())[:70]


# 🚧 Trava do dono (22/ago: "cuidar pra ele não confundir e não repetir pra nunca mais
# postar"): cicatriz proíbe ERRO DE ESCRITA, jamais um ASSUNTO. Regra com cara de censura
# de tema ("nunca fale de/poste sobre/cubra X") é INVÁLIDA e não entra.
_CENSURA = re.compile(
    r"(?i)nunca\s+(fale|falar|poste|postar|publique|publicar|cubra|cobrir|mencione|"
    r"mencionar|cite|citar|escreva\s+sobre|noticie|divulgue)\b")


def _e_censura(licao):
    return bool(_CENSURA.search(licao or ""))


def registrar(licao):
    """Grava uma cicatriz nova (1 linha, começando com NUNCA...). Dedup por conteúdo."""
    licao = re.sub(r"\s+", " ", (licao or "")).strip().rstrip(".") + "."
    if len(licao) < 20:
        return False
    if _e_censura(licao):
        logger.warning(f"🩹 REJEITADA (censura de assunto, não erro de escrita): {licao[:80]}")
        return False
    atuais = _carregar()
    vistos = {_chave(l) for l in atuais}
    if _chave(licao) in vistos:
        return False
    atuais.append(licao)
    _salvar(atuais)
    logger.info(f"🩹 cicatriz nova: {licao[:80]}")
    return True


def ler():
    """Bloco pro prompt do redator. '' se desligado/vazio."""
    if os.environ.get("CICATRIZ_ON", "1").strip() == "0":
        return ""
    linhas = _carregar()[:MAX_CICATRIZES]
    if not linhas:
        return ""
    return ("CICATRIZES (erros de ESCRITA que este jornal JÁ cometeu — NUNCA repita nenhum; "
            "atenção: estas regras corrigem COMO escrever, NÃO proíbem nenhum assunto — "
            "continue cobrindo todos os temas normalmente):\n"
            + "\n".join(f"- {l}" for l in linhas))


def _marco():
    try:
        return open(MARCO_PATH, encoding="utf-8").read().strip()
    except Exception:
        return ""


def aprender_do_log():
    """Segunda 07h20: destila as pegas da semana (checador/leitor) em regras novas."""
    if os.environ.get("CICATRIZ_ON", "1").strip() == "0":
        return 0
    log_path = os.path.join(DATA_DIR, "checador_log.jsonl")
    marco = _marco()
    motivos = []
    try:
        with open(log_path, encoding="utf-8") as f:
            for linha in f:
                try:
                    ev = json.loads(linha)
                except Exception:
                    continue
                if marco and ev.get("quando", "") <= marco:
                    continue
                if ev.get("evento") in ("pega", "descartada", "leitor_segurou") and ev.get("detalhe"):
                    motivos.append(ev["detalhe"])
    except FileNotFoundError:
        return 0
    if not motivos:
        logger.info("🩹 semana sem pega nova — imunidade em dia")
        return 0

    atuais = _carregar()
    try:
        import cerebro
        out = cerebro.completar(
            "Você mantém a lista de LIÇÕES PERMANENTES de um jornal. Abaixo, os erros que o "
            "revisor pegou esta semana (motivos crus) e as lições que JÁ existem. Destile os "
            "erros novos em NO MÁXIMO 3 regras GENERALIZADAS de 1 linha cada, começando com "
            "'NUNCA'. Generalize (o caso vira a regra: 'disse que fulano foi prefeito de X' -> "
            "'NUNCA deduza cargo pela cidade'). REGRA DE OURO: a lição proíbe um ERRO DE "
            "ESCRITA (o que não afirmar, como não redigir) — JAMAIS proíbe um assunto, pessoa "
            "ou tema ('nunca fale de X' é INVÁLIDA; o jornal continua cobrindo tudo). NÃO "
            "repita lição que já existe. Se nada é novo, responda só: NADA.\n\nLIÇÕES EXISTENTES:\n"
            + "\n".join(f"- {l}" for l in atuais[:MAX_CICATRIZES])
            + "\n\nERROS DA SEMANA:\n" + "\n".join(f"- {m}" for m in motivos[:20]))
        if not out or re.match(r"(?i)^\s*nada\b", out.strip()):
            novas = 0
        else:
            novas = sum(1 for l in out.splitlines()
                        if re.match(r"(?i)^\s*[-•]?\s*nunca\b", l.strip())
                        and registrar(re.sub(r"^\s*[-•]\s*", "", l.strip())))
    except Exception as e:
        logger.warning(f"🩹 destilação falhou ({e}) — o log espera a próxima segunda")
        return 0

    try:
        open(MARCO_PATH, "w", encoding="utf-8").write(datetime.now().isoformat()[:19])
    except Exception:
        pass
    logger.info(f"🩹 imunização semanal: {len(motivos)} pega(s) analisada(s), {novas} regra(s) nova(s)")
    return novas
