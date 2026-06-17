# -*- coding: utf-8 -*-
"""
streetview.py — Imagem REAL e RELEVANTE do local da notícia via Google Maps Platform.

Quando NÃO há foto própria, puxa a foto de rua (Street View Static) ou um mapa estiloso
(Maps Static) do LUGAR ÂNCORA da notícia (prefeitura, rodovia, bairro, cidade). 100% legal
pela API oficial — a atribuição "© Google" fica BAKED na imagem e NÃO pode ser tampada (por
isso a capa que usa esta imagem é layout FOTO+FAIXA: o texto não vai por cima do logo deles).

ZERO dependência nova (só requests). Sai None se sem chave / sem cobertura → cai no card de marca.

SETUP (uma vez): no Google Cloud (mesmo projeto com billing do Nano Banana), ativar
  • 'Street View Static API'  • 'Maps Static API'
criar uma API key e pôr em GOOGLE_MAPS_API_KEY no Railway. Custo: dentro do crédito grátis de
US$200/mês (o volume do Rádio gasta ~US$3). Trava GEOFOTO_ON (default ligado).
"""
import os
import re
import unicodedata

import requests

KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
_META = "https://maps.googleapis.com/maps/api/streetview/metadata"
_SV = "https://maps.googleapis.com/maps/api/streetview"
_STATIC = "https://maps.googleapis.com/maps/api/staticmap"

# Coordenadas fixas das cidades do Vale (centro) — evita uma chamada de geocoding pro mapa.
_CITY_LATLNG = {
    "schroeder": "-26.4119,-49.0736",
    "guaramirim": "-26.4706,-49.0029",
    "jaragua do sul": "-26.4858,-49.0664",
    "jaragua": "-26.4858,-49.0664",
    "corupa": "-26.4253,-49.2436",
    "joinville": "-26.3045,-48.8487",
}

# assunto no título → consulta de um LUGAR real (mais relevante que o centro da cidade)
_SUBJECTS = [
    (r"\bBR[-\s]?280\b", "BR-280"),
    (r"\bBR[-\s]?101\b", "BR-101"),
    (r"\bSC[-\s]?108\b", "SC-108"),
    (r"\bSC[-\s]?416\b", "SC-416"),
    (r"prefeitura", "Prefeitura de {city}"),
    (r"c[âa]mara", "Câmara de Vereadores de {city}"),
    (r"hospital", "Hospital de {city}"),
    (r"rodovi[áa]ria", "Rodoviária de {city}"),
    (r"delegacia|pol[íi]cia", "Delegacia de {city}"),
    (r"escola|col[ée]gio", "Escola {city}"),
    (r"igreja|matriz|par[óo]quia", "Igreja Matriz de {city}"),
    (r"pra[çc]a", "Praça central de {city}"),
    (r"terminal|rodoviári", "Terminal {city}"),
]

# Estilo escuro do mapa (combina com a marca). Cada item vira um param 'style=' repetido.
_DARK_STYLE = [
    ("style", "element:geometry|color:0x14151a"),
    ("style", "element:labels.text.fill|color:0xa8aab4"),
    ("style", "element:labels.text.stroke|color:0x11121a"),
    ("style", "feature:road|element:geometry|color:0x2a2c36"),
    ("style", "feature:road|element:labels|visibility:simplified"),
    ("style", "feature:water|element:geometry|color:0x0e1018"),
    ("style", "feature:poi|element:geometry|color:0x1f212b"),
    ("style", "feature:landscape|element:geometry|color:0x16171e"),
]


def _on():
    return bool(KEY) and os.environ.get("GEOFOTO_ON", "1").strip() != "0"


def _norm(c):
    t = unicodedata.normalize("NFKD", (c or "").lower())
    return "".join(ch for ch in t if not unicodedata.combining(ch)).strip()


def _local(news):
    """Melhor âncora p/ a imagem: assunto+cidade (ex 'Prefeitura de Schroeder') ou a cidade."""
    city = news["city"] or "Santa Catarina"
    title = news["title"] or ""
    for rx, q in _SUBJECTS:
        if re.search(rx, title, re.IGNORECASE):
            base = q.format(city=city)
            # rodovia não tem {city} no template → acrescenta a cidade pra ancorar o trecho
            return base if "{city}" in q else f"{base}, {city}"
    return city


def _city_latlng(news):
    return _CITY_LATLNG.get(_norm(news["city"]))


def _save(content, outdir, name):
    p = os.path.join(outdir, name)
    with open(p, "wb") as f:
        f.write(content)
    return p


def _streetview(query, outdir):
    """Foto de rua do local, SÓ se houver cobertura (checa metadata, que é GRÁTIS, antes de gastar)."""
    loc = f"{query}, SC, Brasil"
    try:
        m = requests.get(_META, params={"location": loc, "key": KEY}, timeout=15).json()
        if m.get("status") != "OK":
            return None
        r = requests.get(_SV, params={
            "size": "512x640", "scale": "2", "location": loc,
            "fov": "80", "pitch": "0", "source": "outdoor", "key": KEY}, timeout=25)
        if r.ok and r.headers.get("content-type", "").startswith("image"):
            return _save(r.content, outdir, "_geo_sv.jpg")
    except Exception:
        return None
    return None


def _mapa(news, outdir):
    """Mapa estiloso escuro (sempre disponível) centrado na cidade, com pino vermelho."""
    center = _city_latlng(news) or f"{news['city'] or 'Santa Catarina'}, SC, Brasil"
    params = [
        ("center", center), ("zoom", "14"), ("size", "512x640"), ("scale", "2"),
        ("maptype", "roadmap"), ("markers", f"color:0xe74c3c|{center}"), ("key", KEY),
    ] + _DARK_STYLE
    try:
        r = requests.get(_STATIC, params=params, timeout=25)
        if r.ok and r.headers.get("content-type", "").startswith("image"):
            return _save(r.content, outdir, "_geo_map.jpg")
    except Exception:
        return None
    return None


def buscar(news, outdir):
    """Devolve (path, tipo) com a imagem do LOCAL ('streetview' real ou 'mapa'), ou (None, None).
    Ordem: Street View do lugar âncora → Street View do centro da cidade → mapa da cidade.
    Só roda se GOOGLE_MAPS_API_KEY + GEOFOTO_ON."""
    if not _on():
        return None, None
    os.makedirs(outdir, exist_ok=True)
    local = _local(news)
    p = _streetview(local, outdir)
    if p:
        return p, "streetview"
    # assunto específico sem cobertura → tenta o centro da cidade
    if local != (news["city"] or ""):
        p = _streetview(news["city"] or "Santa Catarina", outdir)
        if p:
            return p, "streetview"
    p = _mapa(news, outdir)
    if p:
        return p, "mapa"
    return None, None
