# -*- coding: utf-8 -*-
"""
genericbg.py — ARSENAL PRÓPRIO de imagens (as NOSSAS) pro fundo da capa.

Quando a notícia não tem foto do admin, o motor escolhe a NOSSA imagem certa pelo TEMA:
  1) SITUAÇÃO no título (acidente, incêndio, temporal, obra...) — a mais topical
  2) CIDADE da notícia (Schroeder, Guaramirim, Jaraguá...)
  3) CATEGORIA (policial, saúde, economia...)
  4) genérico do Vale

As imagens ficam em static/bg/<slug>.(jpg|jpeg|png|webp). Pode ter variações pra rotacionar:
<slug>-1.jpg, <slug>-2.jpg ... (o motor alterna pela id da notícia). Tudo NOSSO (gerado por
nós / IA própria) → 100% legal, on-brand e sempre relevante. Dormente até existir imagem.
Trava BG_ON (default ligado). Ver static/bg/_LEIA-ME.txt pros nomes exatos.
"""
import os
import re
import unicodedata

BG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "bg")
EXTS = (".jpg", ".jpeg", ".png", ".webp")


def _on():
    return os.environ.get("BG_ON", "1").strip() != "0"


def _norm(s):
    t = unicodedata.normalize("NFKD", (s or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")


# SITUAÇÃO detectada no título → slug do arquivo. Ordem = prioridade (mais específico primeiro).
_SITUACOES = [
    (r"\bBR[-\s]?\d{2,3}\b|\bSC[-\s]?\d{2,3}\b|rodovia|acostament", "acidente_rodovia"),
    (r"acidente|colis|bati(d|u)|capot|tomba|atropel", "acidente_carro"),
    (r"inc[êe]ndi|fogo|chamas|bombeir", "incendio"),
    (r"resgat\w+ (de )?(animal|c[ãa]o|cachorro|gato)|maus-tratos.{0,12}animal|animal (preso|resgatad|abandonad)", "animais"),
    (r"pol[íi]ci|preso|pres[ao]s|furto|roub|assalt|apreens|delegacia|tr[áa]fico", "policial"),
    (r"temporal|tempestade|vendaval|granizo|ciclone|chuva", "temporal"),
    (r"alagament|enchente|inunda|transbord", "alagamento"),
    (r"neblina|nevoeiro|geada|frio intenso|onda de frio", "neblina_frio"),
    (r"obra|asfalt|pavimenta|recape|constru[çc]|saneament", "obra"),
    (r"interdi|desvio de tr[áa]fego|tr[âa]nsito (lento|parado|bloquead|interrompid)|bloqueio de (via|rua|avenida)", "transito"),
    (r"falta de (luz|energia)|apag[ãa]o|blecaute|sem energia", "energia"),
    (r"falta de [áa]gua|sem [áa]gua|rod[íi]zio de [áa]gua|abastecimento de [áa]gua", "agua"),
    (r"manifesta[çc]|protesto|greve|paralisa[çc]", "manifestacao"),
    (r"zona rural|agricultor|colheita|planta[çc][ãa]o|propriedade rural|agropecu", "rural"),
    (r"cachoeira|trilha ecol|parque natural|ponto tur[íi]stic", "turismo"),
    (r"prefeitur|prefeit[oa]", "prefeitura"),
    (r"c[âa]mara|vereador|sess[ãa]o|legislativ", "camara"),
    (r"hospital|sa[úu]de|posto de sa|m[ée]dic|vacin|sus|upa", "saude"),
    (r"escola|col[ée]gio|aluno|educa[çc]|creche|professor", "escola"),
    (r"emprego|vaga|contrata|trabalho|ind[úu]stri|empres", "economia"),
    (r"com[ée]rcio|loja|feira|mercado|shopping", "comercio"),
    (r"festa|show|evento|festival|m[úu]sica|arrai|cultura|teatro", "evento"),
    (r"futebol|jogo|campeonat|esporte|t[íi]tulo|copa|atleta", "esporte"),
]

# CATEGORIA (fallback quando nada do título bateu) → slug.
_CATEGORIA = {
    "policial": "policial", "politica": "prefeitura", "saude": "saude",
    "esporte": "esporte", "economia": "economia", "clima": "temporal",
    "cultura": "evento",
}


def _file(slug, seed=0):
    """Acha static/bg/<slug>.<ext>, com rotação <slug>-1, <slug>-2... pela seed. None se não há."""
    if not slug:
        return None
    cands = []
    for ext in EXTS:
        base = os.path.join(BG_DIR, slug + ext)
        if os.path.exists(base):
            cands.append(base)
        i = 1
        while True:
            v = os.path.join(BG_DIR, f"{slug}-{i}{ext}")
            if os.path.exists(v):
                cands.append(v)
                i += 1
            else:
                break
    if not cands:
        return None
    return cands[seed % len(cands)]


def buscar(news):
    """Devolve o caminho da NOSSA imagem mais adequada à notícia, ou None (cai no próximo da
    cascata). Prioridade: situação no título → cidade → categoria → genérico do Vale."""
    if not _on():
        return None
    try:
        seed = int(news["id"])
    except Exception:
        seed = 0
    title = news["title"] or ""

    # 1) situação no título (mais topical)
    for rx, slug in _SITUACOES:
        if re.search(rx, title, re.IGNORECASE):
            p = _file(slug, seed)
            if p:
                return p

    # 2) cidade da notícia
    city = _norm(news["city"])
    if city:
        p = _file("cidade_" + city, seed) or _file(city, seed)
        if p:
            return p

    # 3) categoria
    slug = _CATEGORIA.get((news["category"] or "").strip().lower())
    if slug:
        p = _file(slug, seed)
        if p:
            return p

    # 4) genérico do Vale
    return _file("cidade_geral", seed) or _file("geral", seed)
