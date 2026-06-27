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
import glob
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
# Acidente: o TIPO de veículo tem prioridade. Exige veículo + palavra de acidente (lookahead),
# pra "linha de ônibus nova" / "moto 0km" NÃO virarem foto de batida.
_AC = r"(coli|bate|bati|aciden|atropel|tomb|capot|morr|ferid|engav|virou|incend)"
_SITUACOES = [
    (rf"(?=.*(motociclista|de moto|motoqueir))(?=.*{_AC})", "acidente_moto"),
    (rf"(?=.*(scooter|patinete|ciclomotor))(?=.*{_AC})", "acidente_scooter"),
    (rf"(?=.*(ciclista|bicicleta|de bike))(?=.*{_AC})", "acidente_bicicleta"),
    (rf"(?=.*(caminh[ãa]o|carreta|bitrem|ca[çc]amba))(?=.*{_AC})", "acidente_caminhao"),
    (rf"(?=.*([ôo]nibus|coletivo|micro-?[ôo]nibus))(?=.*{_AC})", "acidente_onibus"),
    (r"\bBR[-\s]?\d{2,3}\b|\bSC[-\s]?\d{2,3}\b|rodovia|acostament", "acidente_rodovia"),
    (r"acidente|colis|bati(d|u)|capot|tomba|atropel", "acidente_carro"),
    (r"inc[êe]ndi|fogo|chamas|bombeir", "incendio"),
    (r"resgat\w+ (de )?(animal|c[ãa]o|cachorro|gato)|maus-tratos.{0,12}animal|animal (preso|resgatad|abandonad)", "animais"),
    (r"pol[íi]ci|preso|pres[ao]s|furto|roub|assalt|apreens|delegacia|tr[áa]fico", "policial"),
    (r"c[âa]mera de seguran|videomonitor|monitorament|vigil[âa]ncia|\bcftv\b|c[âa]meras flagr", "seguranca"),
    (r"dia de chuva|chuvos|garoa|guarda-chuva|pancada de chuva|chuva forte", "chuva"),
    (r"temporal|tempestade|vendaval|granizo|ciclone|ressaca|chuva", "temporal"),
    (r"alagament|enchente|inunda|transbord|cheia do rio", "alagamento"),
    (r"neblina|nevoeiro|geada|frio intenso|onda de frio", "neblina_frio"),
    (r"dia de sol|ensolarad|sol forte|tempo firme|c[ée]u azul|sem previs[ãa]o de chuva", "sol"),
    (r"onda de calor|calor[ãa]o|calor intenso|altas temperaturas|ver[ãa]o", "calor"),
    (r"buraco|cratera|esburacad|asfalto destru|via destru", "buraco"),
    (r"obra|asfalt|pavimenta|recape|constru[çc]|saneament", "obra"),
    (r"\bponte\b|viaduto|passarela", "ponte"),
    (r"interdi|desvio de tr[áa]fego|tr[âa]nsito (lento|parado|bloquead|interrompid)|bloqueio de (via|rua|avenida)", "transito"),
    (r"linha de [ôo]nibus|ponto de [ôo]nibus|transporte p[úu]blic|tarifa de [ôo]nibus|terminal urbano|passagem de [ôo]nibus", "transporte"),
    (r"falta de (luz|energia)|apag[ãa]o|blecaute|sem energia", "energia"),
    (r"falta de [áa]gua|sem [áa]gua|rod[íi]zio de [áa]gua|abastecimento de [áa]gua", "agua"),
    (r"internet|sinal de celular|telefonia|telecom|fibra [óo]ptic|banda larga|\b[45]g\b|antena de celular|sem sinal", "internet"),
    (r"manifesta[çc]|protesto|greve|paralisa[çc]", "manifestacao"),
    (r"zona rural|agricultor|agricultura|colheita|planta[çc]|plantio|lavoura|safra|propriedade rural|agropecu|\btrator|gado|su[íi]no|avic[óo]l|leiteir", "rural"),
    (r"cachoeira|trilha ecol|parque natural|ponto tur[íi]stic", "turismo"),
    (r"doa[çc][ãa]o|agasalho|arrecada[çc]|volunt[áa]ri|solidaried|vaquinha|campanha do agasalho", "solidariedade"),
    (r"meio ambiente|preserva[çc][ãa]o ambiental|reciclag|sustentab|nascente|reflorest|coleta seletiva", "meioambiente"),
    (r"prefeitur|prefeit[oa]", "prefeitura"),
    (r"c[âa]mara|vereador|sess[ãa]o|legislativ", "camara"),
    (r"hospital|sa[úu]de|posto de sa|m[ée]dic|vacin|sus|upa", "saude"),
    (r"escola|col[ée]gio|aluno|educa[çc]|creche|professor", "escola"),
    (r"formatur|formand|cola[çc][ãa]o de grau", "formatura"),
    (r"emprego|vaga|contrata|trabalho|ind[úu]stri|empres", "economia"),
    (r"com[ée]rcio|loja|mercado|shopping|varejo", "comercio"),
    (r"feira livre|feir[ãa]o|feira de artesan|feira do produtor", "feira"),
    (r"igreja|par[óo]quia|missa|cat[óo]lic|capela|festa religios|romaria", "igreja"),
    (r"lixo|coleta de lixo|entulho|descarte irregular|aterro sanit", "lixo"),
    (r"natal\b|natalin|papai noel|luzes de natal|decora[çc][ãa]o de natal|ceia de natal", "natal"),
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


# Cidades do Vale: detecta no TÍTULO (mais confiável que o campo city, que às vezes vem errado/
# genérico — ex: notícia de Jaraguá marcada como Schroeder). A cidade citada no título manda.
_CIDADES_VALE = [
    ("jaragua", "Jaraguá do Sul"), ("schroeder", "Schroeder"),
    ("guaramirim", "Guaramirim"), ("joinville", "Joinville"), ("corupa", "Corupá"),
]


def cidade_no_titulo(title):
    """Se o título cita uma cidade do Vale, devolve o NOME dela (a 1ª que aparece). Senão None.
    Reusado pela imagem (arsenal/Street View) e pelo selo da cidade na capa."""
    t = _norm(title)
    achados = [(t.find(k), nome) for k, nome in _CIDADES_VALE if k in t]
    return min(achados)[1] if achados else None


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

    # 2) cidade — PREFERE a citada no TÍTULO (o campo city às vezes vem errado: notícia de
    #    Jaraguá marcada como Schroeder). Assim a imagem é da cidade CERTA.
    city = _norm(cidade_no_titulo(title) or news["city"])
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

    # 4) genérico do Vale: cidade_geral/geral; senão rotaciona entre QUALQUER aérea de cidade que
    #    exista (melhor uma cidade do Vale "ilustrativa" do que um card vazio na notícia estadual).
    p = _file("cidade_geral", seed) or _file("geral", seed)
    if p:
        return p
    cidades = sorted(glob.glob(os.path.join(BG_DIR, "cidade_*.jpg")) +
                     glob.glob(os.path.join(BG_DIR, "cidade_*.jpeg")) +
                     glob.glob(os.path.join(BG_DIR, "cidade_*.png")))
    return cidades[seed % len(cidades)] if cidades else None
