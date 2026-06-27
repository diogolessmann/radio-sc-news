# -*- coding: utf-8 -*-
"""
streetview.py — FOTO REAL do prédio/lugar da notícia via Google Street View Static.

SÓ entra quando o título cita um LUGAR ESPECÍFICO (prefeitura, câmara, hospital, rodovia, etc.)
que tenha cobertura de Street View. Aí pega a foto real daquele prédio (ex: a Câmara de Vereadores
de Schroeder, a Prefeitura). Notícia genérica ("Santa Catarina"/nacional) NÃO usa isto — cai no
arsenal/card. NÃO usa mapa (mapa genérico ficou ruim e foi removido).

100% legal pela API oficial — o "© Google" fica BAKED na imagem (a capa usa layout foto+faixa
pra não tampar o logo). ZERO dependência nova. Sai None se sem chave / sem lugar / sem cobertura.

SETUP: GOOGLE_MAPS_API_KEY no Railway + 'Street View Static API' ativa. Trava GEOFOTO_ON.
"""
import os
import re

import requests

KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
_META = "https://maps.googleapis.com/maps/api/streetview/metadata"
_SV = "https://maps.googleapis.com/maps/api/streetview"

# LUGAR específico citado no título → consulta do Street View. Só estes valem (prédio/rodovia real);
# notícia sem lugar específico não usa Street View. {city} é a cidade da notícia.
_SUBJECTS = [
    (r"\bBR[-\s]?\d{2,3}\b", "BR-{num}"),
    (r"\bSC[-\s]?\d{2,3}\b", "SC-{num}"),
    (r"c[âa]mara|vereador|sess[ãa]o legislativ", "Câmara de Vereadores de {city}"),
    (r"prefeitur|prefeit[oa]", "Prefeitura Municipal de {city}"),
    (r"hospital", "Hospital {city}"),
    (r"rodovi[áa]ria|terminal rodovi", "Rodoviária de {city}"),
    (r"delegacia", "Delegacia de {city}"),
    (r"f[óo]rum|justi[çc]a", "Fórum de {city}"),
    (r"igreja matriz|matriz|par[óo]quia", "Igreja Matriz de {city}"),
    (r"pra[çc]a central|pra[çc]a", "Praça central de {city}"),
    (r"hospital de olhos|upa|posto de sa", "Posto de Saúde {city}"),
]


def _on():
    return bool(KEY) and os.environ.get("GEOFOTO_ON", "1").strip() != "0"


def _landmark_query(news):
    """Consulta de um LUGAR específico citado no título (ex 'Câmara de Vereadores de Schroeder'),
    ou None se a notícia não cita um lugar concreto. Sem lugar = sem Street View (cai no arsenal)."""
    title = news["title"] or ""
    # PREFERE a cidade citada no TÍTULO (o campo city às vezes vem errado — notícia de Jaraguá
    # marcada como Schroeder). Assim a foto do prédio é da cidade CERTA.
    try:
        import genericbg
        city = (genericbg.cidade_no_titulo(title) or (news["city"] or "")).strip()
    except Exception:
        city = (news["city"] or "").strip()
    for rx, tmpl in _SUBJECTS:
        m = re.search(rx, title, re.IGNORECASE)
        if not m:
            continue
        if "{num}" in tmpl:                       # rodovia: BR-280, SC-108...
            num = re.sub(r"\D", "", m.group(0))
            q = tmpl.format(num=num)
            return f"{q}, {city}" if city else q
        if "{city}" in tmpl:
            if not city:
                return None                       # prédio precisa de cidade pra ancorar
            return tmpl.format(city=city)
    return None


def _streetview(query, outdir):
    """Foto de rua do lugar, SÓ se houver cobertura (checa metadata, que é GRÁTIS, antes de gastar)."""
    loc = f"{query}, SC, Brasil"
    try:
        m = requests.get(_META, params={"location": loc, "key": KEY}, timeout=15).json()
        if m.get("status") != "OK":
            return None
        r = requests.get(_SV, params={
            "size": "512x640", "scale": "2", "location": loc,
            "fov": "80", "pitch": "0", "source": "outdoor", "key": KEY}, timeout=25)
        if r.ok and r.headers.get("content-type", "").startswith("image"):
            p = os.path.join(outdir, "_geo_sv.jpg")
            with open(p, "wb") as f:
                f.write(r.content)
            return p
    except Exception:
        return None
    return None


def buscar(news, outdir):
    """Devolve (path, 'streetview') com a foto REAL do lugar citado, ou (None, None). Só roda
    quando o título cita um lugar específico com cobertura. NUNCA devolve mapa."""
    if not _on():
        return None, None
    q = _landmark_query(news)
    if not q:
        return None, None
    os.makedirs(outdir, exist_ok=True)
    p = _streetview(q, outdir)
    return (p, "streetview") if p else (None, None)
