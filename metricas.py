# -*- coding: utf-8 -*-
"""
metricas.py — Health check do motor (Rádio SC News).
"Sem medir, kaizen é chute." Relatório simples e barato (SQL puro, zero IA, zero dependência)
pra guiar a melhoria: quanto se posta, % com foto, distribuição por cidade/categoria, fila.

Uso: metricas.coletar() -> dict. A rota /admin/saude renderiza isso.
"""
import os
import sqlite3

DB_PATH = os.environ.get("DB_PATH", "radio_sc.db")
NORTE_SC = {"Schroeder", "Joinville", "Jaragua do Sul", "Jaraguá do Sul",
            "Guaramirim", "Corupa", "Corupá", "Norte de SC"}
STOCK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "stock")


def _scalar(conn, sql, args=()):
    return conn.execute(sql, args).fetchone()[0]


def _pct(part, total):
    return round(100 * part / total) if total else 0


def _ensure_cols(conn):
    """Garante as colunas sociais (a PROD pode não ter rodado a migração ainda)."""
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(news)")]
        for c in ("social_posted_at", "social_hold", "ig_media_id", "ig_permalink"):
            if c not in cols:
                conn.execute(f"ALTER TABLE news ADD COLUMN {c} TEXT")
        conn.commit()
    except Exception:
        pass


def coletar(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    _ensure_cols(conn)
    try:
        ativas = _scalar(conn, "SELECT COUNT(*) FROM news WHERE active=1")
        com_foto = _scalar(conn, "SELECT COUNT(*) FROM news WHERE active=1 "
                                 "AND image_url IS NOT NULL AND image_url!=''")
        sem_summary = _scalar(conn, "SELECT COUNT(*) FROM news WHERE active=1 "
                                    "AND (summary IS NULL OR summary='')")

        postados_hoje = _scalar(conn, "SELECT COUNT(*) FROM news WHERE "
                                      "date(social_posted_at)=date('now','localtime')")
        postados_7d = _scalar(conn, "SELECT COUNT(*) FROM news WHERE "
                                    "social_posted_at > datetime('now','-7 days')")
        pendentes = _scalar(conn, "SELECT COUNT(*) FROM news WHERE active=1 "
                                  "AND (social_posted_at IS NULL OR social_posted_at='') "
                                  "AND (social_hold IS NULL OR social_hold='')")
        seguradas = _scalar(conn, "SELECT COUNT(*) FROM news WHERE active=1 "
                                  "AND social_hold IS NOT NULL AND social_hold!=''")

        # distribuição por cidade (top) e foco regional
        cidades = conn.execute(
            "SELECT COALESCE(city,'(sem cidade)') c, COUNT(*) n FROM news WHERE active=1 "
            "GROUP BY c ORDER BY n DESC LIMIT 8").fetchall()
        norte = sum(r["n"] for r in cidades if r["c"] in NORTE_SC)

        categorias = conn.execute(
            "SELECT COALESCE(category,'geral') cat, COUNT(*) n FROM news WHERE active=1 "
            "GROUP BY cat ORDER BY n DESC LIMIT 8").fetchall()

        # fotos de stock regional disponíveis (Fase 3)
        stock = []
        if os.path.isdir(STOCK_DIR):
            stock = [f for f in os.listdir(STOCK_DIR)
                     if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]

        # 🏆 Loop de Insights: top posts por (saves+shares). Tabela pode não existir ainda.
        top_posts, com_insights = [], 0
        try:
            tp = conn.execute(
                "SELECT n.title, n.city, p.reach, p.saved, p.shares, "
                "(COALESCE(p.saved,0)+COALESCE(p.shares,0)) AS score "
                "FROM post_insights p JOIN news n ON n.id=p.news_id "
                "ORDER BY score DESC, p.reach DESC LIMIT 5").fetchall()
            top_posts = [(r["title"], r["city"], r["reach"] or 0, r["saved"] or 0, r["shares"] or 0)
                         for r in tp]
            com_insights = _scalar(conn, "SELECT COUNT(*) FROM post_insights")
        except Exception:
            top_posts, com_insights = [], 0

        return {
            "ativas": ativas,
            "com_foto": com_foto, "pct_foto": _pct(com_foto, ativas),
            "sem_summary": sem_summary, "pct_sem_summary": _pct(sem_summary, ativas),
            "postados_hoje": postados_hoje, "postados_7d": postados_7d,
            "pendentes": pendentes, "seguradas": seguradas,
            "pct_norte": _pct(norte, ativas),
            "cidades": [(r["c"], r["n"], _pct(r["n"], ativas)) for r in cidades],
            "categorias": [(r["cat"], r["n"], _pct(r["n"], ativas)) for r in categorias],
            "stock_fotos": sorted(stock),
            "top_posts": top_posts, "com_insights": com_insights,
        }
    finally:
        conn.close()


if __name__ == "__main__":
    import json
    print(json.dumps(coletar(), indent=2, ensure_ascii=False))
