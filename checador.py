# -*- coding: utf-8 -*-
"""🔎 CHECADOR — o fato inventado não vai ao ar (22/ago/2026).

A solução definitiva pro caso Antídio ("prefeito de Guaramirim" — leitor corrigiu nos
comentários): depois que o redator IA reescreve, um SEGUNDO cérebro compara a NOSSA
versão com o texto ORIGINAL e caça fato acrescentado — cargo, nome, número, data,
cidade. Achou invenção → o redator refaz UMA vez sabendo do erro; errou de novo →
descarta a reescrita (o site cai no texto original, que é extrativo e não inventa).

Omissão NUNCA é erro (o estilo "disse mas não falei" omite de propósito) — só
condena o que a nossa versão AFIRMA e o original não sustenta.

Cada pega é registrada em DATA_DIR/checador_log.jsonl — semente do SELO (a máquina
medindo a própria taxa de acerto). Trava CHECADOR_ON (default ligado). Fail-open:
IA do checador fora do ar não segura a esteira (o redator já tem as travas de prompt).
"""
import json
import logging
import os
import re
from datetime import datetime

logger = logging.getLogger(__name__)

DATA_DIR = os.environ.get("DATA_DIR", ".")
LOG_PATH = os.path.join(DATA_DIR, "checador_log.jsonl")


def ativo():
    return os.environ.get("CHECADOR_ON", "1").strip() != "0"


_PROMPT = (
    "Você é o CHECADOR de um jornal. Compare a VERSÃO NOSSA com o TEXTO ORIGINAL e aponte "
    "APENAS fatos que a nossa versão AFIRMA e que o original NÃO sustenta: cargo político "
    "atribuído a alguém, nome, número, valor, data, cidade ou qualquer informação acrescentada. "
    "REGRAS:\n"
    "- OMITIR informação NÃO é erro (a versão é um resumo de propósito).\n"
    "- Reformular com outras palavras NÃO é erro se o fato for o mesmo.\n"
    "- Arredondar número de forma honesta ('mais de 1.200' para 1.226) NÃO é erro.\n"
    "- Só condene INVENÇÃO ou TROCA de fato (ex.: original diz 'ex-prefeito de Jaraguá' e a "
    "versão diz 'prefeito de Guaramirim').\n"
    "Responda EXATAMENTE:\n"
    "OK\n"
    "ou\n"
    "ERRO: <o fato inventado/trocado, em 1 frase>\n\n"
    "TEXTO ORIGINAL:\n{original}\n\nVERSÃO NOSSA:\n{nossa}"
)


def _registrar(evento, titulo, detalhe=""):
    """Memória do SELO: cada pega/refação registrada (jsonl, 1 linha por evento)."""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({"quando": datetime.now().isoformat()[:19], "evento": evento,
                                "titulo": (titulo or "")[:120], "detalhe": detalhe[:300]},
                               ensure_ascii=False) + "\n")
    except Exception:
        pass


def conferir(original, titulo, corpo):
    """Confere a reescrita contra a fonte. Devolve (ok, motivo).
    ok=True quando aprovado OU quando o checador não conseguiu responder (fail-open)."""
    if not ativo() or not (original or "").strip():
        return True, None
    try:
        import cerebro
        nossa = f"{titulo}\n{corpo}"
        out = cerebro.completar(_PROMPT.format(original=original[:4000], nossa=nossa[:2000]))
        if not out:
            return True, None                      # checador mudo -> não segura a esteira
        out = out.strip()
        if re.match(r"(?i)^ok\b", out):
            return True, None
        m = re.search(r"(?i)erro:\s*(.+)", out)
        motivo = (m.group(1).strip() if m else out)[:300]
        return False, motivo
    except Exception as e:
        logger.warning(f"🔎 checador falhou ({e}) — deixando passar (fail-open)")
        return True, None


def reescrita_conferida(gerar, original, titulo_hint=""):
    """Fluxo completo: gera -> confere -> (se errou) regenera 1x avisando o erro -> confere.
    `gerar(aviso)` é um callable que devolve (titulo, corpo) — aviso vai anexado ao bruto.
    Devolve (titulo, corpo) aprovados, ou (None, None) se a IA insistiu no erro."""
    t, c = gerar("")
    if not (t and c):
        return t, c
    ok, motivo = conferir(original, t, c)
    if ok:
        return t, c
    _registrar("pega", t, motivo)
    logger.warning(f"🔎 CHECADOR pegou: {motivo} — refazendo '{(t or '')[:50]}'")
    aviso = (f"\n\n⚠️ ATENÇÃO: a versão anterior INVENTOU o seguinte e foi rejeitada: {motivo}. "
             f"Escreva de novo SEM esse erro — se o texto original não diz, você não diz.")
    t2, c2 = gerar(aviso)
    if t2 and c2:
        ok2, motivo2 = conferir(original, t2, c2)
        if ok2:
            _registrar("refeita_ok", t2)
            return t2, c2
        _registrar("descartada", t2, motivo2 or "")
        logger.error(f"🔎 CHECADOR reprovou 2x — reescrita DESCARTADA: {motivo2}")
    return None, None


def resumo_selo(dias=30):
    """Números pro SELO/placar: quantas o checador pegou, refez e descartou."""
    contagem = {"pega": 0, "refeita_ok": 0, "descartada": 0}
    try:
        corte = datetime.now().isoformat()[:19]
        from datetime import timedelta
        corte = (datetime.now() - timedelta(days=dias)).isoformat()[:19]
        with open(LOG_PATH, encoding="utf-8") as f:
            for linha in f:
                try:
                    ev = json.loads(linha)
                    if ev.get("quando", "") >= corte and ev.get("evento") in contagem:
                        contagem[ev["evento"]] += 1
                except Exception:
                    continue
    except FileNotFoundError:
        pass
    return contagem
