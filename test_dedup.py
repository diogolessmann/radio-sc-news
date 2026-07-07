# -*- coding: utf-8 -*-
"""
test_dedup.py — REDE DE SEGURANÇA do dedup (Rádio SC News).

Nasceu da dor viva de 07/jul/2026 (mesma notícia de fontes diferentes postada 2x+). O dedup
compara por SOBREPOSIÇÃO de palavras — que falha em duplicata SEMÂNTICA (mesmo fato, palavras
diferentes de cada fonte). O fix: overlap MÁXIMO (título cru x nosso) + fingerprint evento:cidade:dia.

Mede RECALL (gêmeas que TÊM que ser pegas) e PRECISÃO (fatos diferentes que NÃO podem juntar).
Rodar:  python test_dedup.py     (exit 0 = ok · exit 1 = recall caiu ou juntou fato errado)
"""
import distribuidor as d

FALHAS = []
_ID = [0]


def _n(title, summary="", title_own="", city="", pub="2026-07-08"):
    _ID[0] += 1
    return {"id": _ID[0], "title": title, "title_own": title_own or title,
            "summary": summary, "city": city, "category": "geral", "published_at": pub}


# GÊMEAS: mesmo fato, fontes/palavras diferentes → _mesmo_fato TEM que ser True
GEMEAS = [
    ("Acidente na BR-280 deixa um morto em Guaramirim",
     "Colisao frontal mata motorista na BR-280 proximo a Guaramirim"),
    ("Homem e preso por incendio em hotel de Chapeco",
     "Policia detem suspeito de causar fogo em hotel em Chapeco"),
    ("Bombeiros resgatam vitima de afogamento no rio em Jaragua do Sul",
     "Homem e socorrido apos se afogar em rio em Jaragua do Sul"),
    ("Motociclista morre em acidente em Schroeder",
     "Colisao tira a vida de jovem em moto no centro de Schroeder"),
    ("Obra interdita a Rua XV em Jaragua do Sul nesta sexta",
     "Transito e bloqueado na Rua XV para obra de pavimentacao em Jaragua do Sul"),
    ("Temporal causa alagamento no centro de Joinville",
     "Chuva forte deixa ruas alagadas no centro de Joinville"),
    ("Jovem e baleado durante assalto no centro de Corupa",
     "Homem leva tiro em tentativa de roubo no centro de Corupa"),
    # casos REAIS do feed (07/jul): aviao em Navegantes + Rio Canoas 2x
    ("Aviao cai em Navegantes e tripulantes ficam internados",
     "Aviao bimotor caiu na restinga da Meia Praia em Navegantes"),
    ("Rio Canoas sobe para 6 metros e alaga ruas em Otacilio Costa",
     "Rio Canoas sobe para 6,18m e alaga ruas em dois bairros de Otacilio Costa"),
]
# LIMITACAO CONHECIDA (keyword nao pega, fica p/ o 2o andar de IA no futuro):
# 'SERIPA investiga acidente aereo em Navegantes' x 'Aviao bimotor caiu em Navegantes' -> overlap
# 0.14 (frame investigacao vs queda). Baixar o corte pra pegar isso juntaria fatos diferentes
# (perde precisao), entao mantemos o corte seguro. Ainda assim, colapsa 3 posts do aviao em 2.
_rec_ok = 0
for a, b in GEMEAS:
    na, nb = _n(a, city="x"), _n(b, city="x")
    if d._mesmo_fato(na, nb):
        _rec_ok += 1
    else:
        ov = max(d._overlap(a, b), 0)
        FALHAS.append(f"[recall] GEMEA nao pegou (overlap={ov:.2f}): '{a[:40]}' ~ '{b[:40]}'")

# FATOS DIFERENTES: mesmo tipo, mas NÃO são a mesma história → NÃO pode juntar (precisão)
DIFERENTES = [
    ("Acidente na BR-280 deixa ferido em Guaramirim",
     "Acidente na SC-108 deixa ferido em Corupa"),                       # rodovia+cidade diferentes
    ("Homem e preso por roubo em Joinville",
     "Mulher e presa por trafico de drogas em Jaragua do Sul"),          # crime+cidade diferentes
    ("Acidente com moto na Rua Reinoldo Rau em Jaragua do Sul",
     "Capotamento na BR-280 em Jaragua do Sul deixa feridos"),           # 2 acidentes distintos, MESMA cidade/dia
    ("Jaragua vence no futsal e lidera o campeonato",
     "Joinville perde no volei na estreia do estadual"),                 # esportes diferentes
    ("Incendio atinge residencia no bairro Vila Nova em Jaragua do Sul",
     "Incendio destroi galpao industrial em Guaramirim"),                # incendios diferentes, cidades diferentes
]
_prec_ok = 0
for a, b in DIFERENTES:
    na, nb = _n(a, city="x"), _n(b, city="x")
    if not d._mesmo_fato(na, nb):
        _prec_ok += 1
    else:
        FALHAS.append(f"[precisao] JUNTOU fato diferente: '{a[:40]}' ~ '{b[:40]}'")

print(f"recall gemeas: {_rec_ok}/{len(GEMEAS)}  |  precisao (nao-juntar): {_prec_ok}/{len(DIFERENTES)}")
if FALHAS:
    print("\n❌ %d FALHA(S) NO DEDUP:" % len(FALHAS))
    for f in FALHAS:
        print("  - " + f)
    raise SystemExit(1)
print("✅ test_dedup: gemeas pegas + fatos diferentes preservados")
