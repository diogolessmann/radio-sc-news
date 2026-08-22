# -*- coding: utf-8 -*-
"""📚 AULA AUTOMÁTICA — o motor afia a própria manchete (22/ago/2026).

Fecha o ciclo que faltava: o placar MEDE, mas quem escrevia a lição no prompt do
redator era humano (as fórmulas de 20/ago ficaram congeladas). Agora, toda segunda,
este job lê o desempenho REAL dos últimos 14 dias (post_insights) e escreve a
AULA DA SEMANA em DATA_DIR/aula_semana.txt — e o cerebro anexa essa aula viva ao
prompt de TODA reescrita. Publica -> mede -> aprende -> escreve melhor, sozinho.

Determinístico (sem IA — é estatística virando texto), fail-open (sem dado = sem
aula = prompt igual ao de sempre). Trava AULA_ON (default ligado).
"""
import logging
import os
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("DB_PATH", "radio_sc.db")
DATA_DIR = os.environ.get("DATA_DIR", ".")
AULA_PATH = os.path.join(DATA_DIR, "aula_semana.txt")


def _views(r):
    return max(r["plays"] or 0, r["reach"] or 0)


def gerar(dias=14):
    """Escreve a aula da semana a partir do desempenho real. Devolve o texto (ou None)."""
    if os.environ.get("AULA_ON", "1").strip() == "0":
        return None
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT n.title_own, n.title, n.category, n.city, p.reach, p.plays
               FROM post_insights p JOIN news n ON n.id = p.news_id
               WHERE replace(n.social_posted_at,'T',' ') >= datetime('now', ?)
                 AND p.reach IS NOT NULL AND p.reach > 0""", (f"-{dias} days",)).fetchall()
    except Exception as e:
        conn.close()
        logger.info(f"📚 aula sem dado ({e})")
        return None
    conn.close()
    if len(rows) < 8:                       # amostra magra = lição enviesada, melhor calar
        logger.info(f"📚 aula: só {len(rows)} posts medidos — sem aula esta semana")
        return None

    posts = sorted(rows, key=_views, reverse=True)
    cats = {}
    for r in posts:
        cats.setdefault((r["category"] or "geral").lower(), []).append(_views(r))
    medias = sorted(((c, sum(v) // len(v), len(v)) for c, v in cats.items() if len(v) >= 2),
                    key=lambda x: -x[1])

    def _fmt(n):
        return f"{n:,}".replace(",", ".")

    L = [f"AULA DA SEMANA (dados reais do NOSSO público, {datetime.now().strftime('%d/%m')}, "
         f"{len(posts)} posts medidos):"]
    for i, r in enumerate(posts[:3], 1):
        t = (r["title_own"] or r["title"] or "")[:80]
        L.append(f"- Campeã {i}: \"{t}\" ({_fmt(_views(r))} views) — imite a PEGADA desta manchete.")
    if medias:
        top = " · ".join(f"{c} ({_fmt(m)} médias)" for c, m, _ in medias[:3])
        L.append(f"- Temas rendendo: {top}.")
        if len(medias) > 3:
            fraco = medias[-1]
            L.append(f"- Rendendo POUCO: {fraco[0]} ({_fmt(fraco[1])} médias) — se o fato for "
                     f"desse tema, o gancho precisa trabalhar dobrado.")
    L.append("Quando o fato permitir, escolha a fórmula que está rendendo AGORA.")
    texto = "\n".join(L)

    try:
        with open(AULA_PATH, "w", encoding="utf-8") as f:
            f.write(texto)
        logger.info(f"📚 aula da semana escrita ({len(posts)} posts na base)")
    except Exception as e:
        logger.error(f"📚 aula não salvou: {e}")
    return texto


def ler():
    """Aula atual pro prompt (cache por mtime no cerebro). '' se não existe/desligada."""
    if os.environ.get("AULA_ON", "1").strip() == "0":
        return ""
    try:
        with open(AULA_PATH, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""
