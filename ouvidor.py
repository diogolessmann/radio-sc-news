# -*- coding: utf-8 -*-
"""👂 OUVIDOR — o leitor corrigiu, o dono sabe em minutos (22/ago/2026).

O caso Antídio foi descoberto POR ACASO: leitores já corrigiam nos comentários e o
dono viu tarde. O Ouvidor varre os comentários dos posts recentes (Graph API, mesmo
token do Inspetor) caçando SINAL DE CORREÇÃO ("tá errado", "não foi", "na verdade",
"mentira", "fake") e manda o alerta no zap do Vigia com o post + o comentário.

Roda a cada 2h no scheduler. Já-avisados ficam em DATA_DIR/ouvidor_visto.json
(nunca zapa o mesmo comentário 2x). Trava OUVIDOR_ON (default ligado). Fail-safe.
"""
import json
import logging
import os
import re

import requests

logger = logging.getLogger(__name__)

META_TOKEN = (os.environ.get("META_PAGE_TOKEN") or "").strip()
GRAPH = "https://graph.facebook.com/v21.0"
DATA_DIR = os.environ.get("DATA_DIR", ".")
VISTO_PATH = os.path.join(DATA_DIR, "ouvidor_visto.json")

# sinal de leitor CORRIGINDO (não de leitor bravo genérico — xingamento não é pauta)
_ALARME = re.compile(
    r"t[áa] errad|est[áa] errad|informa[çc][ãa]o errada|n[ãa]o foi (?:em|o|a|isso)|"
    r"na verdade|mentira|fake|not[íi]cia falsa|incorret|equivocad|corrig|"
    r"n[ãa]o [ée] (?:prefeito|verdade)|foi prefeito de|checa (?:a|essa)|fonte\?", re.I)


def ativo():
    return bool(META_TOKEN) and os.environ.get("OUVIDOR_ON", "1").strip() != "0"


def _visto():
    try:
        return set(json.load(open(VISTO_PATH, encoding="utf-8")))
    except Exception:
        return set()


def _salvar_visto(ids):
    try:
        json.dump(sorted(ids)[-2000:], open(VISTO_PATH, "w", encoding="utf-8"))
    except Exception:
        pass


def _comentarios(media_id):
    try:
        r = requests.get(f"{GRAPH}/{media_id}/comments",
                         params={"fields": "id,text,username,timestamp", "limit": 50,
                                 "access_token": META_TOKEN}, timeout=25)
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception as e:
        logger.warning(f"👂 comments falhou p/ {media_id}: {e}")
        return []


def run(enviar=True, horas=48):
    """Varre os posts das últimas N horas; comentário com cara de correção -> zap."""
    if not ativo():
        return {"ok": False, "motivo": "sem token ou OUVIDOR_ON=0"}
    import distribuidor as dist
    conn = dist.get_db()
    posts = conn.execute(
        "SELECT id, title_own, title, ig_media_id, ig_permalink FROM news "
        "WHERE ig_media_id IS NOT NULL AND ig_media_id != '' "
        "AND replace(social_posted_at,'T',' ') >= datetime('now', ?) "
        "ORDER BY social_posted_at DESC LIMIT 60", (f"-{horas} hours",)).fetchall()
    conn.close()

    visto = _visto()
    alertas = []
    for p in posts:
        for cm in _comentarios(p["ig_media_id"]):
            cid = cm.get("id")
            txt = (cm.get("text") or "").strip()
            if not cid or cid in visto or not txt:
                continue
            visto.add(cid)
            if _ALARME.search(txt):
                alertas.append(
                    f"👂 *LEITOR APONTOU ERRO*\n"
                    f"📰 {(p['title_own'] or p['title'] or '')[:80]}\n"
                    f"💬 @{cm.get('username','?')}: \"{txt[:200]}\"\n"
                    f"👉 {p['ig_permalink'] or ''}")
    _salvar_visto(visto)

    if alertas and enviar:
        try:
            import vigia
            vigia.send_zap("\n\n".join(alertas[:5]) +
                           ("\n\n(+ mais alertas no próximo ciclo)" if len(alertas) > 5 else ""))
        except Exception as e:
            logger.error(f"👂 zap falhou: {e}")
    logger.info(f"👂 Ouvidor: {len(posts)} posts varridos, {len(alertas)} alerta(s)")
    return {"ok": True, "posts": len(posts), "alertas": len(alertas)}
