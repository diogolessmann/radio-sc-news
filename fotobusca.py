# -*- coding: utf-8 -*-
"""
fotobusca.py — Foto REAL para posts sem imagem.
Quando uma notícia (geralmente local) não tem foto, procura no banco a MESMA notícia
(de outra fonte/portal — G1, ND, etc.) que TENHA foto, e devolve essa foto + a fonte
(pra creditar). Reusa o dedup por sobreposição de palavras (mesmo fato, fontes diferentes).

Melhor que imagem IA pra notícia: foto REAL, do evento real, relevante.
Trava-mestra: FOTOBUSCA_ON (default LIGADO — é grátis e seguro; desliga com =0).
Atribuição: quem usa a foto deve creditar a fonte ("Foto: <portal>").
"""
import os
import re
import sqlite3
import unicodedata

DB_PATH = os.environ.get("DB_PATH", "radio_sc.db")
LIGADO = os.environ.get("FOTOBUSCA_ON", "1").strip() != "0"

_STOP = set((
    "de da do das dos a o e os as um uma uns umas no na nos nas ao aos que com por "
    "para pra apos sobre entre ate sem sob desde como mais menos muito pouco urgente "
    "video veja confira saiba assista foto fotos imagem imagens noticia em foi sao "
    "ser tem ter dois tres anos ano hoje agora cidade regiao apos"
).split())


def _strip(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _keys(text):
    t = _strip(text)
    return {w[:5] for w in re.findall(r"[a-z0-9]+", t) if len(w) >= 3 and w not in _STOP}


def _overlap(a, b):
    ka, kb = _keys(a), _keys(b)
    if not ka or not kb:
        return 0.0
    return len(ka & kb) / min(len(ka), len(kb))


def achar_foto(titulo, news_id, thresh=0.62):
    """Procura a MESMA notícia (de outra fonte) que TENHA foto.
    Matching ESTRITO (foto errada é pior que sem foto): ambos os títulos com >=4
    palavras-chave, interseção >=3, score >= thresh. Devolve (image_url, fonte) ou (None, None)."""
    if not LIGADO or not titulo:
        return None, None
    base = _keys(titulo)
    if len(base) < 4:          # título curto demais -> não dá pra casar com segurança
        return None, None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT title, image_url, source FROM news "
            "WHERE image_url IS NOT NULL AND image_url != '' AND id != ? "
            "AND created_at > datetime('now','-3 days') "
            "ORDER BY datetime(published_at) DESC LIMIT 300",
            (news_id,),
        ).fetchall()
        conn.close()
    except Exception:
        return None, None
    best, best_score = None, thresh
    for r in rows:
        cand = _keys(r["title"])
        if len(cand) < 4:                       # título genérico/seção (ex: "Joinville e Norte de SC")
            continue
        inter = len(base & cand)
        if inter < 3:                           # poucos termos em comum -> não é o mesmo fato
            continue
        s = inter / min(len(base), len(cand))
        if s >= best_score:
            best, best_score = r, s
    if best:
        return best["image_url"], best["source"]
    return None, None
