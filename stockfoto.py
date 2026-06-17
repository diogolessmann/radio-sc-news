# -*- coding: utf-8 -*-
"""
stockfoto.py — Foto REGIONAL de fallback (banco próprio).
Quando nenhuma foto real foi achada (RSS, og:image, gêmea), em vez do card preto entra
uma foto BONITA da própria cidade (Jaraguá, Schroeder, Guaramirim, Joinville...).
Fotos do DONO = 100% legal + cara do Vale.

COMO USAR (o dono põe as fotos):
  Coloque fotos em  static/stock/  nomeadas pela CIDADE (sem acento, minúsculo, hífen):
    schroeder.jpg · jaragua-do-sul.jpg · guaramirim.jpg · joinville.jpg
    sc.jpg  (genérica — usada quando não tem a da cidade)
  Pode ter várias por cidade (schroeder-1.jpg, schroeder-2.jpg...) que rotaciona por dia.

Trava: STOCK_ON (default ligado). Desliga com STOCK_ON=0.
"""
import os
import re
import glob
import unicodedata
from datetime import datetime

STOCK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "stock")
LIGADO = os.environ.get("STOCK_ON", "1").strip() != "0"
EXTS = ("jpg", "jpeg", "png", "webp")


def _slug(cidade):
    s = unicodedata.normalize("NFKD", (cidade or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


# Landmarks por ASSUNTO: foto PRÓPRIA do ponto do Vale (prefeitura, hospital, BR-280...).
# Foto sua = real + local + legal. Procura static/stock/<cidade>-<landmark> e, senão, <landmark>.
_LANDMARKS = [
    (re.compile(r"prefeitura|c[âa]mara|vereador|prefeit[oa]|secretaria municipal", re.I), "prefeitura"),
    (re.compile(r"hospital|\bubs\b|posto de sa[úu]de|pronto.?socorro", re.I), "hospital"),
    (re.compile(r"\bescola|col[ée]gio|creche|educa[çc][ãa]o", re.I), "escola"),
    (re.compile(r"br-?\s?280", re.I), "br280"),
    (re.compile(r"igreja|par[óo]quia|matriz|\bmissa\b|capela", re.I), "igreja"),
    (re.compile(r"\bpra[çc]a\b", re.I), "praca"),
    (re.compile(r"rodovi[áa]ria|terminal", re.I), "rodoviaria"),
]


def achar_landmark(news):
    """Foto própria de um ponto do Vale pelo ASSUNTO da notícia. Procura
    static/stock/<cidade>-<landmark>.<ext> e, senão, o genérico <landmark>.<ext>. None se nada."""
    if not LIGADO or not os.path.isdir(STOCK_DIR):
        return None
    try:
        blob = f"{news['title'] or ''} {news['summary'] or ''}"
        cidade = _slug(news['city'] or "")
    except Exception:
        return None
    yday = datetime.now().timetuple().tm_yday
    for rx, land in _LANDMARKS:
        if rx.search(blob):
            for base in ([f"{cidade}-{land}", land] if cidade else [land]):
                cands = []
                for ext in EXTS:
                    cands += glob.glob(os.path.join(STOCK_DIR, f"{base}.{ext}"))
                    cands += glob.glob(os.path.join(STOCK_DIR, f"{base}-*.{ext}"))
                cands = sorted(cands)
                if cands:
                    return cands[yday % len(cands)]
            break
    return None


def achar_stock(cidade):
    """Devolve o caminho de uma foto regional p/ a cidade (com fallback genérico), ou None."""
    if not LIGADO or not os.path.isdir(STOCK_DIR):
        return None
    yday = datetime.now().timetuple().tm_yday
    for nome in (_slug(cidade), "sc", "geral"):
        if not nome:
            continue
        cands = []
        for ext in EXTS:
            cands += glob.glob(os.path.join(STOCK_DIR, f"{nome}.{ext}"))
            cands += glob.glob(os.path.join(STOCK_DIR, f"{nome}-*.{ext}"))
        cands = sorted(cands)
        if cands:
            return cands[yday % len(cands)]      # rotaciona por dia (variedade)
    return None
