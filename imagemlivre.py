# -*- coding: utf-8 -*-
"""
imagemlivre.py — Banco de imagem LIVRE (Pexels) p/ a capa, por categoria.
Foto ILUSTRATIVA (não a do evento real), 100% LEGAL: licença Pexels = uso comercial liberado,
sem atribuição obrigatória. Resolve o buraco do anti-strike (sem foto de terceiro).

⚖️ HONESTIDADE: como é ilustrativa, o card carimba "Foto ilustrativa".
🛡️ SENSÍVEL: pra notícia policial, usa só imagem SEM pessoa (rodovia/viatura) — evita pôr o rosto
   de alguém aleatório do banco ao lado de um crime (risco de difamação).

Precisa da chave grátis: PEXELS_API_KEY (cadastro em pexels.com/api). Sem chave -> None (cai pro
próximo da cascata, nada quebra). Trava: IMG_LIVRE_ON (default on).
"""
import os
import random

import requests

PEXELS_KEY = os.environ.get("PEXELS_API_KEY", "").strip()
PEXELS_URL = "https://api.pexels.com/v1/search"
LIGADO = os.environ.get("IMG_LIVRE_ON", "1").strip() != "0"

# queries em inglês (Pexels rende melhor). Policial = SEM pessoa (rodovia/viatura/ambulância).
_QUERY = {
    "policial": ["police car street", "highway road night", "ambulance emergency lights"],
    "politica": ["city hall building", "government building", "council chamber"],
    "saude":    ["hospital building", "health clinic", "stethoscope doctor"],
    "esporte":  ["soccer stadium", "football pitch", "running track"],
    "economia": ["business office", "shopping street", "local market commerce"],
    "clima":    ["heavy rain street", "thunderstorm sky", "storm clouds"],
    "cultura":  ["festival crowd", "live concert stage", "street fair night"],
    "local":    ["small town street", "town square"],
    "geral":    ["city street", "brazilian town"],
}


def buscar(categoria, titulo="", seed=0):
    """Devolve a URL de uma foto ilustrativa (portrait) do Pexels, ou None."""
    if not (LIGADO and PEXELS_KEY):
        return None
    cat = (categoria or "geral").lower()
    qs = _QUERY.get(cat, _QUERY["geral"])
    s = int(seed) or random.randint(0, 999)
    query = qs[s % len(qs)]
    try:
        r = requests.get(
            PEXELS_URL,
            params={"query": query, "per_page": 15, "orientation": "portrait"},
            headers={"Authorization": PEXELS_KEY}, timeout=15,
        )
        if not r.ok:
            return None
        photos = r.json().get("photos", [])
        if not photos:
            return None
        p = photos[s % len(photos)]
        src = p.get("src", {})
        return src.get("portrait") or src.get("large") or src.get("original")
    except Exception:
        return None
