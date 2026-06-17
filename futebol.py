# -*- coding: utf-8 -*-
"""
futebol.py — Dados de futebol (jogos + resultados) p/ o Palpite do Vale.
FATO LIVRE: placar e fixture são fatos públicos (ninguém é dono). Puxa de uma API grátis
(football-data.org) — confiável, oficial. Resultado SÓ quando o jogo termina (status FINISHED),
pra nunca postar placar errado/cedo.

Chave grátis: FOOTBALL_API_KEY (cadastro em football-data.org). Competição: FOOTBALL_COMP
(default WC = Copa do Mundo). Sem chave -> [] / None (nada quebra).
"""
import os
from datetime import datetime

import requests

FD_KEY = os.environ.get("FOOTBALL_API_KEY", "").strip()
FD_URL = "https://api.football-data.org/v4"
COMP = os.environ.get("FOOTBALL_COMP", "WC").strip()   # WC = Copa do Mundo

# tradução leve de seleções p/ PT-BR (cobre as principais; o resto cai no nome original)
_PT = {
    "Brazil": "Brasil", "Portugal": "Portugal", "Argentina": "Argentina",
    "France": "França", "England": "Inglaterra", "Spain": "Espanha", "Germany": "Alemanha",
    "Croatia": "Croácia", "Netherlands": "Holanda", "Belgium": "Bélgica", "Italy": "Itália",
    "Uruguay": "Uruguai", "Colombia": "Colômbia", "Mexico": "México", "USA": "Estados Unidos",
    "South Korea": "Coreia do Sul", "Japan": "Japão", "Morocco": "Marrocos",
    "DR Congo": "RD Congo", "Switzerland": "Suíça", "Denmark": "Dinamarca",
}


def _nome(t):
    n = (t or {}).get("name") or (t or {}).get("shortName") or ""
    return _PT.get(n, n)


def _hdr():
    return {"X-Auth-Token": FD_KEY}


def jogos_do_dia(data=None):
    """Lista de jogos da competição na data (default hoje). [] se sem chave/erro."""
    if not FD_KEY:
        return []
    d = data or datetime.now().strftime("%Y-%m-%d")
    try:
        r = requests.get(f"{FD_URL}/competitions/{COMP}/matches",
                         params={"dateFrom": d, "dateTo": d}, headers=_hdr(), timeout=20)
        return r.json().get("matches", []) if r.ok else []
    except Exception:
        return []


def jogo_destaque(data=None):
    """Escolhe 1 jogo de destaque do dia. Prioriza Brasil/Portugal; senão o primeiro.
    Devolve dict simples {id, time_a, time_b, hora} ou None."""
    ms = jogos_do_dia(data)
    if not ms:
        return None
    pref = ("Brazil", "Portugal")
    escolha = None
    for m in ms:
        nomes = (m.get("homeTeam", {}).get("name", "") + m.get("awayTeam", {}).get("name", ""))
        if any(p in nomes for p in pref):
            escolha = m
            break
    escolha = escolha or ms[0]
    hora = ""
    try:
        dt = datetime.fromisoformat(escolha["utcDate"].replace("Z", "+00:00"))
        # UTC -> Brasília (-3h), simples
        h = (dt.hour - 3) % 24
        hora = f"{h:02d}h{dt.minute:02d}".replace("h00", "h")
    except Exception:
        pass
    return {"id": escolha.get("id"), "time_a": _nome(escolha.get("homeTeam")),
            "time_b": _nome(escolha.get("awayTeam")), "hora": hora}


def resultado(match_id):
    """Resultado FINAL (só se FINISHED). Devolve {gols_a, gols_b, vencedor: 'A'|'B'|'EMPATE'} ou None."""
    if not (FD_KEY and match_id):
        return None
    try:
        r = requests.get(f"{FD_URL}/matches/{match_id}", headers=_hdr(), timeout=20)
        if not r.ok:
            return None
        m = r.json()
        if m.get("status") != "FINISHED":
            return None      # ⏳ trava de segurança: só revela jogo ACABADO
        ft = m.get("score", {}).get("fullTime", {})
        ga, gb = ft.get("home"), ft.get("away")
        if ga is None or gb is None:
            return None
        venc = "A" if ga > gb else ("B" if gb > ga else "EMPATE")
        return {"gols_a": ga, "gols_b": gb, "vencedor": venc}
    except Exception:
        return None
