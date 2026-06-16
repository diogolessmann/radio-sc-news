# -*- coding: utf-8 -*-
"""
geo.py — Geotag por cidade (location_id) pros posts.
Geotag é o sinal nº1 de busca hiperlocal ("perto de mim"/cidade) — e regional é o NOSSO
diferencial. Hoje o motor não marca localização; este módulo resolve o Place id do Facebook
de cada cidade e injeta no post (carrossel/Reels).

Resolução (em ordem, com fallback seguro):
  1) MAPA MANUAL via env GEO_LOCATIONS="Schroeder=1234,Jaragua do Sul=5678"
     (o jeito 100% confiável — pega o id na página do local no Facebook).
  2) CACHE em static/.geo_cache.json (resultados já resolvidos).
  3) BUSCA na Graph (/pages/search) SE houver token com permissão — salva no cache.
  4) None -> post sai SEM geotag (comportamento atual, nada quebra).

Trava: GEO_ON (default ligado). Desliga com GEO_ON=0.
"""
import os
import json
import threading

import requests

CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", ".geo_cache.json")
_lock = threading.Lock()


def _on():
    return os.environ.get("GEO_ON", "1").strip() != "0"


def _norm(city):
    return (city or "").strip().lower()


def _valid_id(v):
    """Place id do FB é NUMÉRICO e longo. Rejeita placeholder ('ID'), vazio ou texto —
    blindagem p/ um valor errado no env NUNCA quebrar o post (vira 'sem geotag')."""
    v = (v or "").strip()
    return v.isdigit() and len(v) >= 5


def _manual_map():
    """Mapa cidade->id vindo do env GEO_LOCATIONS (o jeito confiável).
    Ex: GEO_LOCATIONS="Schroeder=11122233,Jaragua do Sul=44455566". Ignora ids inválidos."""
    raw = os.environ.get("GEO_LOCATIONS", "").strip()
    out = {}
    for part in raw.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            if k.strip() and _valid_id(v):     # ignora 'ID' e qualquer coisa não-numérica
                out[_norm(k)] = v.strip()
    return out


def candidatos(city, token=None):
    """Lista candidatos de Place id pra uma cidade (id, nome, local) via Graph /pages/search.
    Pra alimentar a página /admin/geo (o dono escolhe o certo). [] se token/permite falhar."""
    if token is None:
        try:
            import distribuidor as dist
            token, graph = dist.META_PAGE_TOKEN, dist.GRAPH
        except Exception:
            token, graph = "", "https://graph.facebook.com/v21.0"
    else:
        graph = "https://graph.facebook.com/v21.0"
    if not token:
        return []
    try:
        r = requests.get(
            f"{graph}/pages/search",
            params={"q": f"{city} SC", "fields": "id,name,location", "access_token": token},
            timeout=20,
        )
        out = []
        for p in (r.json().get("data", []) if r.ok else []):
            loc = p.get("location") or {}
            cidade_uf = ", ".join(x for x in (loc.get("city"), loc.get("state")) if x)
            out.append({"id": p.get("id", ""), "name": p.get("name", ""), "local": cidade_uf})
        return out
    except Exception:
        return []


def _load_cache():
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(c):
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(c, f, ensure_ascii=False)
    except Exception:
        pass


def location_id(city, token=None):
    """Place id do FB pra geotag desta cidade, ou None (sem geotag)."""
    if not _on() or not city:
        return None
    key = _norm(city)

    man = _manual_map()
    if key in man:
        return man[key]

    cache = _load_cache()
    if key in cache:
        return cache[key] or None

    # busca automática só se houver token (em prod vem do distribuidor)
    if token is None:
        try:
            import distribuidor as dist
            token = dist.META_PAGE_TOKEN
            graph = dist.GRAPH
        except Exception:
            token, graph = "", "https://graph.facebook.com/v21.0"
    else:
        graph = "https://graph.facebook.com/v21.0"
    if not token:
        return None

    found = ""
    try:
        r = requests.get(
            f"{graph}/pages/search",
            params={"q": f"{city} Santa Catarina", "fields": "id,name,location",
                    "access_token": token},
            timeout=20,
        )
        data = r.json().get("data", []) if r.ok else []
        for p in data:
            loc = p.get("location") or {}
            st = (loc.get("state") or "") + (loc.get("city") or "")
            if "SC" in st or "Santa Catarina" in st:
                found = p["id"]
                break
        if not found and data:
            found = data[0].get("id", "")
    except Exception:
        found = ""

    with _lock:
        cache[key] = found
        _save_cache(cache)
    return found or None
