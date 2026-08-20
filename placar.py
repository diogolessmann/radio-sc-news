# -*- coding: utf-8 -*-
"""🏆 PLACAR — o motor aprende com as views SOZINHO (20/ago/2026).

Diretiva do dono: "dos números de views é pra você aprender o que tá bombando" —
até hoje ele mandava PRINT por print. Este job puxa as views reais de cada post
da semana direto da Graph API, ranqueia campeões e fracassos, tira a AULA
(média por categoria) e manda o boletim no zap (mesma Evolution do Vigia).

Histórico acumulado em DATA_DIR/placar_historico.json — é a memória que depois
alimenta o afinamento das fórmulas de manchete no cérebro.

Roda toda segunda 07h45 (antes do compilado de vagas — o dono acorda com o placar).
"""
import json
import logging
import os
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

META_TOKEN = (os.environ.get("META_PAGE_TOKEN") or "").strip()
GRAPH = "https://graph.facebook.com/v21.0"
DATA_DIR = os.environ.get("DATA_DIR", ".")
HIST = os.path.join(DATA_DIR, "placar_historico.json")


def _views(media_id):
    """Views do post (métrica 'views' v21+; fallback reach). None se a API negar tudo."""
    for metricas in ("views,reach,likes,comments,shares,saved", "reach,total_interactions"):
        try:
            r = requests.get(f"{GRAPH}/{media_id}/insights",
                             params={"metric": metricas, "access_token": META_TOKEN}, timeout=25)
            if r.status_code != 200:
                continue
            vals = {d["name"]: (d.get("values") or [{}])[0].get("value") or 0
                    for d in r.json().get("data", [])}
            v = vals.get("views") or vals.get("reach") or 0
            return {"views": int(v), "likes": int(vals.get("likes") or 0),
                    "shares": int(vals.get("shares") or 0), "saves": int(vals.get("saved") or 0)}
        except Exception as e:
            logger.warning(f"🏆 insights falhou p/ {media_id}: {e}")
    return None


def coletar(conn, dias=7):
    rows = conn.execute(
        "SELECT id, title_own, title, city, category, ig_media_id, ig_permalink "
        "FROM news WHERE ig_media_id IS NOT NULL AND ig_media_id != '' "
        "AND replace(social_posted_at,'T',' ') >= datetime('now', ?) "
        "ORDER BY social_posted_at DESC LIMIT 120", (f"-{dias} days",)).fetchall()
    posts = []
    for r in rows:
        m = _views(r["ig_media_id"])
        if m is None:
            continue
        posts.append({"id": r["id"], "titulo": (r["title_own"] or r["title"] or "")[:90],
                      "cidade": r["city"] or "", "categoria": r["category"] or "geral",
                      "link": r["ig_permalink"] or "", **m})
    return posts


def _boletim(posts):
    posts.sort(key=lambda p: p["views"], reverse=True)
    top, flop = posts[:5], [p for p in posts[-5:] if p not in posts[:5]]
    # aula: média por categoria (o que a audiência está premiando ESTA semana)
    cats = {}
    for p in posts:
        cats.setdefault(p["categoria"], []).append(p["views"])
    aula = sorted(((c, sum(v) // len(v), len(v)) for c, v in cats.items()),
                  key=lambda x: x[1], reverse=True)
    L = [f"🏆 *PLACAR DA SEMANA* — {len(posts)} posts medidos", "", "*CAMPEÕES:*"]
    for i, p in enumerate(top, 1):
        L.append(f"{i}º {p['views']:,} views — {p['titulo']} ({p['cidade']})".replace(",", "."))
    if flop:
        L += ["", "*💤 FICARAM PRA TRÁS:*"]
        for p in flop:
            L.append(f"• {p['views']} views — {p['titulo'][:60]}")
    L += ["", "*📚 AULA (média por categoria):*"]
    for c, m, n in aula[:6]:
        L.append(f"• {c}: {m:,} views médias ({n} posts)".replace(",", "."))
    if top:
        L += ["", f"👉 Campeão: {top[0]['link']}"]
    return "\n".join(L)


def run(enviar=True, dias=7):
    if not META_TOKEN:
        return {"ok": False, "motivo": "sem META_PAGE_TOKEN"}
    import distribuidor as dist
    conn = dist.get_db()
    posts = coletar(conn, dias)
    conn.close()
    if not posts:
        return {"ok": False, "motivo": "nenhum post com media_id na janela"}
    # memória: acumula a semana no histórico (alimenta o afinamento das fórmulas depois)
    try:
        hist = []
        if os.path.exists(HIST):
            hist = json.load(open(HIST, encoding="utf-8"))
        hist.append({"semana": datetime.now().strftime("%Y-%m-%d"), "posts": posts})
        json.dump(hist[-26:], open(HIST, "w", encoding="utf-8"), ensure_ascii=False)
    except Exception as e:
        logger.warning(f"🏆 histórico falhou: {e}")
    rel = _boletim(posts)
    if enviar:
        try:
            import vigia
            vigia.send_zap(rel)
        except Exception as e:
            logger.error(f"🏆 zap falhou: {e}")
    logger.info(f"🏆 Placar: {len(posts)} posts medidos, campeão {posts[0]['views']} views")
    return {"ok": True, "medidos": len(posts), "campeao": posts[0]["titulo"]}
