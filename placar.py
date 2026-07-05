# -*- coding: utf-8 -*-
"""
placar.py — A CAMADA DE INTELIGÊNCIA (Rádio SC News).

Fase 1 do "motor que aprende": lê o resultado REAL de cada post (post_insights, coletado pelo
insights.py) e cruza com os ATRIBUTOS da notícia (tema, cidade, formato, horário) pra descobrir
O QUE O VALE MAIS SALVA E COMPARTILHA. Não decide nada ainda — só mostra o padrão (o dono e,
depois, o distribuidor aprendem com isso).

Nota (placar):
  saved e shares são o ouro de 2026. A nota normaliza pelo ALCANCE (pontos por 1.000 de reach),
  pra não premiar só post que já teve sorte de alcance. Posts com alcance ínfimo (<20) viram ruído
  e ficam de fora.

Uso: placar.painel()  -> dict pronto pro /admin/placar
"""
import os
import sqlite3
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "radio_sc.db")

_REACH_MIN = 20          # piso de alcance pra entrar no placar (abaixo disso é ruído)
_W_SAVED, _W_SHARES, _W_COMMENTS = 3.0, 4.0, 2.0   # pesos (share > save > comentário)


def _db():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def _score(r):
    """Nota de qualidade do post: (saves, shares, comentários ponderados) por 1.000 de alcance."""
    reach = r["reach"] or 0
    if reach < _REACH_MIN:
        return None
    pts = (r["saved"] or 0) * _W_SAVED + (r["shares"] or 0) * _W_SHARES + (r["comments"] or 0) * _W_COMMENTS
    return pts / reach * 1000.0


def _formato(r):
    return "Reels" if (r["plays"] or 0) and r["plays"] > 0 else "Carrossel"


def _hora(r):
    try:
        return f"{datetime.fromisoformat(r['social_posted_at']).hour:02d}h"
    except Exception:
        return None


def _cidade(r):
    """Cidade REAL do post: detecta pelo TÍTULO (o campo city vem genérico 'Santa Catarina' mesmo
    quando a notícia é de uma cidade -> Jaraguá aparecia subcontada). Mesmo critério da imagem/
    legenda (gi._cidade_real). Sem cidade no título, cai no campo city."""
    try:
        import genericbg
        c = genericbg.cidade_no_titulo(r["title_own"] or r["title"] or "")
        if c:
            return c
    except Exception:
        pass
    return r["city"] or "(sem cidade)"


def _agg(scored, keyfn, minimo=2):
    """Agrega a lista [(row, score)] por uma dimensão. Ignora grupos com poucos posts (ruído)."""
    buckets = {}
    for r, sc in scored:
        k = keyfn(r)
        if not k:
            continue
        b = buckets.setdefault(k, {"n": 0, "reach": 0, "saves": 0, "shares": 0, "score": 0.0})
        b["n"] += 1
        b["reach"] += r["reach"] or 0
        b["saves"] += r["saved"] or 0
        b["shares"] += r["shares"] or 0
        b["score"] += sc
    out = []
    for k, b in buckets.items():
        if b["n"] < minimo:
            continue
        out.append({
            "nome": k, "n": b["n"],
            "reach_medio": round(b["reach"] / b["n"]),
            "saves_medio": round(b["saves"] / b["n"], 1),
            "shares_medio": round(b["shares"] / b["n"], 1),
            "score": round(b["score"] / b["n"], 1),
        })
    return sorted(out, key=lambda x: -x["score"])


def painel(dias=90):
    """Foto do que funciona: rankings por tema, cidade, formato e horário + top posts + resumo."""
    conn = _db()
    try:
        rows = conn.execute(
            """SELECT n.id, n.title, n.title_own, n.category, n.city, n.social_posted_at,
                      p.reach, p.saved, p.shares, p.comments, p.plays
               FROM post_insights p JOIN news n ON n.id = p.news_id
               WHERE p.reach IS NOT NULL AND p.reach > 0""").fetchall()
    except Exception:
        conn.close()
        return {"tem_dado": False, "n_posts": 0}
    conn.close()

    scored = [(r, s) for r in rows if (s := _score(r)) is not None]
    if not scored:
        return {"tem_dado": False, "n_posts": len(rows)}

    # top posts (os campeões de verdade)
    top = sorted(scored, key=lambda x: -x[1])[:6]
    top_posts = [{
        "titulo": (r["title_own"] or r["title"] or "")[:70],
        "cidade": _cidade(r), "categoria": r["category"], "formato": _formato(r),
        "reach": r["reach"] or 0, "saves": r["saved"] or 0, "shares": r["shares"] or 0,
        "score": round(sc, 1),
    } for r, sc in top]

    por_categoria = _agg(scored, lambda r: (r["category"] or "outros").lower())
    por_cidade = _agg(scored, _cidade)      # cidade REAL (pelo título), não o campo cru
    por_formato = _agg(scored, _formato, minimo=1)
    por_hora = _agg(scored, _hora, minimo=1)

    def _top(lst):
        return lst[0]["nome"] if lst else None

    resumo = {
        "tema": _top(por_categoria), "cidade": _top(por_cidade),
        "formato": _top(por_formato), "hora": _top(por_hora),
    }
    return {
        "tem_dado": True, "n_posts": len(scored),
        "por_categoria": por_categoria, "por_cidade": por_cidade,
        "por_formato": por_formato, "por_hora": por_hora,
        "top_posts": top_posts, "resumo": resumo,
        "gerado_em": datetime.now().strftime("%d/%m %H:%M"),
    }


def pesos(dias=90):
    """Pesos NORMALIZADOS (0..1) por tema e cidade — o que o motor (Fase 2) consulta pra dar
    bônus de prioridade ao que mais rende. Devolve {} se ainda não há dado (aí o motor não mexe)."""
    p = painel(dias)
    if not p.get("tem_dado"):
        return {}

    def _norm(lst):
        if not lst:
            return {}
        mx = max((x["score"] for x in lst), default=0) or 1.0
        return {x["nome"]: round(x["score"] / mx, 3) for x in lst}

    return {"categoria": _norm(p.get("por_categoria")), "cidade": _norm(p.get("por_cidade"))}


if __name__ == "__main__":
    import json
    print(json.dumps(painel(), ensure_ascii=False, indent=2))
    print("PESOS:", json.dumps(pesos(), ensure_ascii=False))
