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
# 🎨 Acervo de imagens GERADAS por IA (nanobanana), salvas por SITUAÇÃO p/ REUSO (economiza $$):
# gera 1x, reusa pra sempre. No Railway vai pro VOLUME persistente (senão sumiria a cada deploy);
# local cai em static/bg_ia. Escaneado junto com o arsenal fixo (_file olha os dois).
_VOL = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
IA_BG_DIR = os.environ.get("IA_BG_DIR") or (
    os.path.join(_VOL, "bg_ia") if _VOL
    else os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "bg_ia"))
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
_AC = r"(coli|bate|bati|aciden|atropel|tomb|capot|morr|ferid|engav|virou|incend|invad)"
_SITUACOES = [
    # 🏎️ AUTOMOBILISMO vem ANTES de tudo (fix 19/jul): "Antonelli vence GP" + "acidente na
    # largada" no corpo saía com CARRO BATIDO na estrada. Corrida é ESPORTE, não acidente.
    (r"f[óo]rmula\s?1|\bf1\b|\bgp\b|grande pr[êe]mio|automobilismo|stock car|\bkart\b|"
     r"moto\s?gp|pole position|aut[óo]dromo|\bpaddock\b|grid de largada", "automobilismo"),
    (rf"(?=.*(motociclista|de moto|motoqueir))(?=.*{_AC})", "acidente_moto"),
    (rf"(?=.*(scooter|patinete|ciclomotor))(?=.*{_AC})", "acidente_scooter"),
    (rf"(?=.*(ciclista|bicicleta|de bike))(?=.*{_AC})", "acidente_bicicleta"),
    (rf"(?=.*(caminh[ãa]o|caminhonete|picape|pickup|carreta|bitrem|ca[çc]amba))(?=.*{_AC})", "acidente_caminhao"),
    (rf"(?=.*([ôo]nibus|coletivo|micro-?[ôo]nibus))(?=.*{_AC})", "acidente_onibus"),
    # ✈️ AVIAÇÃO (fix 18/jul — 1º turno do Inspetor): "quase colisão no ar / tragédia aérea"
    # caía em 'colis' e saía com CARRO CAPOTADO. Não existia foto de avião no arsenal.
    # Um airliner é ilustração neutra e correta pra QUALQUER notícia de aviação (inclusive
    # queda) — melhor que foto de acidente de outro modal.
    (r"\bvoos?\b|avi[ãa]o|avi[õo]es|aeronave|helic[óo]pter|bimotor|aeroporto|anticolis[ãa]o|"
     r"trag[ée]dia a[ée]rea|acidente a[ée]reo|tr[áa]fego a[ée]reo|companhia a[ée]rea|"
     r"torre de controle|decolag|pouso for[çc]ad", "aviacao"),
    # 🔥 QUEIMADA/fumaça ≠ incêndio urbano (Inspetor pegou: notícia de fumaça de queimada
    # ilustrada com prédio pegando fogo). Vem ANTES do 'incendio'.
    (r"queimada|inc[êe]ndio florestal|inc[êe]ndios florestais|fuma[çc]a|foco de inc[êe]ndio|"
     r"brigadist|desmatament.{0,20}fogo", "queimada"),
    # radar/fiscalização É trânsito, não batida (fix 13/jul: notícia de radar saía com carro batido)
    (r"radar|fiscaliza[çc]|blitz|lei seca", "transito"),
    # rodovia/BR-xxx só vira foto de ACIDENTE se houver palavra de acidente junto (lookahead);
    # senão "obras na BR-280" e "radar nas rodovias" puxavam carro batido (fix 13/jul)
    (rf"(?=.*(\bBR[-\s]?\d{{2,3}}\b|\bSC[-\s]?\d{{2,3}}\b|rodovia|acostament))(?=.*{_AC})", "acidente_rodovia"),
    (r"acidente|colis|bati(d|u)|capot|tomba|atropel", "acidente_carro"),
    (r"inc[êe]ndi|fogo|chamas|bombeir", "incendio"),
    (r"resgat\w+ (de )?(animal|c[ãa]o|cachorro|gato)|maus-tratos.{0,12}animal|animal (preso|resgatad|abandonad)", "animais"),
    # 🗣️ CONFLITO CIVIL (ideia do dono, 20/jul): discussão/desentendimento entre vizinhos,
    # inquilino×proprietário etc. — a foto é DISCUSSÃO em silhueta, não viatura (viatura
    # criminaliza briga de vizinho). GUARDA: crime pesado (morte/arma/violência doméstica/
    # companheira) NUNCA cai aqui — segue pro policial neutro. Vem ANTES do policial.
    # ^ obrigatório: lookahead NEGATIVO sem âncora "escapa" testando posições após a palavra
    # proibida (bug pego no teste 20/jul: "agressão contra companheira após discussão" caía aqui)
    (r"^(?=.*(discuss|desentend|bate.?boca|desaven[çc]))"
     r"(?!.*(morr|mort|faca|esfaque|\barma|tiro|estupr|viol[êe]ncia dom|companheir|esposa|marido|namorad|sequestr|tr[áa]fico))",
     "discussao"),
    # \bbriga\b(?!\s+pel) — "briga pela vaga/liderança" é figurado (esporte), não ocorrência
    (r"pol[íi]ci|preso|pres[ao]s|detid|furto|roub|assalt|apreens|delegacia|tr[áa]fico|"
     r"\bbrigas?\b(?!\s+pel)|agress[aãoõ]|espancament|viol[êe]ncia dom[ée]stica|ladr[ãao]|"
     r"facad|esfaquead|homic[íi]d|assassin|\bmortes?\b", "policial"),
    (r"c[âa]mera de seguran|videomonitor|monitorament|vigil[âa]ncia|\bcftv\b|c[âa]meras flagr", "seguranca"),
    # 📱 golpe digital (pauta semanal!) — "golpe" exige contexto (golpe DO pix) p/ não casar figurado
    (r"golpe (?!de estado|militar)(d[oe]|via|no|contra)|golpista|estelionat|\bfraude|clonad|clonagem|"
     r"\bpix\b.{0,40}(golpe|fraude|roub)", "golpe"),
    # ⚖️ justiça institucional — DEPOIS do policial (crime concreto ganha; aqui é o judiciário)
    (r"justi[çc]a|tribunal|julgament|senten[çc]|liminar|habeas|indeniza[çc]|"
     r"\bstf\b|\bstj\b|\btjsc\b|\btce\b|\bf[óo]rum\b|minist[ée]rio p[úu]blico|promotoria", "justica"),
    # 🗳️ eleição (2026 é ano eleitoral — ago-out vai bombar)
    (r"elei[çc]|urna eletr[ôo]nica|candidat|\btse\b|\btre-?sc\b|segundo turno|campanha eleitoral", "eleicao"),
    (r"supermercad|cesta b[áa]sica|atacadista|pre[çc]os? d[oe]s? aliment", "supermercado"),
    (r"\bempreg|\bvagas?\b|contrata[çc][ãa]o|curr[íi]cul|\bsine\b|processo seletivo|carteira assinada", "emprego"),
    (r"\bpraias?\b|litoral|beira-?mar|\borla\b|banhistas?|ressaca do mar|temporada de ver[ãa]o", "praia"),
    (r"estiagem|\bseca\b|racionamento|n[íi]vel baixo d[oe]s? rios?|falta de chuva", "estiagem"),
    (r"dia de chuva|chuvos|garoa|guarda-chuva|pancada de chuva|chuva forte", "chuva"),
    (r"temporal|tempestade|vendaval|granizo|ciclone|ressaca|chuva", "temporal"),
    (r"alagament|enchente|inunda|transbord|cheia do rio", "alagamento"),
    # frio simples também casa (fix 13/jul: "terça GELADA / o FRIO continua" saía com foto de RAIO
    # via fallback de categoria clima→temporal)
    (r"neblina|nevoeiro|geada|\bfrio\b|gelad|friagem", "neblina_frio"),
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
    # 😤 DESAPROVAÇÃO (ideia do dono, 20/jul): revolta/indignação/vergonha — o facepalm.
    # Por último de propósito: se o título tem o FATO ("revoltados com o buraco"), a foto do
    # fato (buraco) ganha; o facepalm cobre quando a emoção É a notícia.
    # v2 escancarada (20/jul — dono reprovou a sutil): polegarZÃO 👎 e mãos-na-cara 🫣
    (r"vergonh|vexame|constrang|papel[ãa]o|\bmico\b", "vergonha"),
    (r"revolt|indign|absurdo|inaceit[áa]vel|impunidade|desaprov|rep[úu]dio", "desaprovacao"),
]

# CATEGORIA (fallback quando nada do título bateu) → slug.
# "clima" SAIU do fallback (fix 13/jul): clima→temporal servia RAIO pra matéria de frio/sol.
# Clima sem situação específica agora cai na IA-gen (imagem sob medida do tema) ou no genérico.
_CATEGORIA = {
    "policial": "policial", "politica": "prefeitura", "saude": "saude",
    "esporte": "esporte", "economia": "economia",
    "cultura": "evento",
}


def _file(slug, seed=0):
    """Acha <slug>.<ext> (+ rotação <slug>-1, <slug>-2...) no arsenal fixo (static/bg) E no
    acervo IA (volume). Rotaciona pela seed. None se não há em lugar nenhum."""
    if not slug:
        return None
    cands = []
    for root in (BG_DIR, IA_BG_DIR):
        if not os.path.isdir(root):
            continue
        for ext in EXTS:
            base = os.path.join(root, slug + ext)
            if os.path.exists(base):
                cands.append(base)
            i = 1
            while True:
                v = os.path.join(root, f"{slug}-{i}{ext}")
                if os.path.exists(v):
                    cands.append(v)
                    i += 1
                else:
                    break
    if not cands:
        return None
    return cands[seed % len(cands)]


def _situacao_slug(title):
    """O slug de SITUAÇÃO que o título casa (temporal/alagamento/incendio...), ou None."""
    for rx, slug in _SITUACOES:
        if re.search(rx, title or "", re.IGNORECASE):
            return slug
    return None


def slug_alvo(titulo, categoria):
    """Slug sob o qual uma imagem IA deve ser SALVA (e que buscar prioriza) — a CHAVE do reuso.
    Situação no título > categoria mapeada > categoria crua > 'geral'."""
    cat = (categoria or "geral").strip().lower()
    return _situacao_slug(titulo) or _CATEGORIA.get(cat) or cat or "geral"


# Cidades do Vale: detecta no TÍTULO (mais confiável que o campo city, que às vezes vem errado/
# genérico — ex: notícia de Jaraguá marcada como Schroeder). A cidade citada no título manda.
_CIDADES_VALE = [
    ("jaragua", "Jaraguá do Sul"), ("schroeder", "Schroeder"),
    ("guaramirim", "Guaramirim"), ("joinville", "Joinville"), ("corupa", "Corupá"),
    # vizinhas cobertas (fix 16/jul: notícia de MASSARANDUBA saiu com pill "SCHROEDER" porque a
    # cidade do título não era conhecida e valeu a city fixa do feed)
    ("massaranduba", "Massaranduba"), ("barra velha", "Barra Velha"), ("pomerode", "Pomerode"),
]

# 🔴 Slugs PROIBIDOS em notícia SENSÍVEL (fix 16/jul: a CÂMARA DE SCHROEDER — nome na fachada —
# ilustrou notícia de LAVAGEM DE DINHEIRO): prédio público/lugar IDENTIFICÁVEL nunca ilustra
# crime — associa a instituição/cidade ao delito (risco jurídico). Sensível usa só fundo
# genérico neutro (policial/seguranca) ou card de marca.
_PROIBIDOS_SENSIVEL = {"prefeitura", "camara", "escola", "igreja", "formatura", "feira",
                       "comercio", "evento", "turismo", "saude"}


def _slug_proibido_sensivel(slug):
    return slug in _PROIBIDOS_SENSIVEL or (slug or "").startswith("cidade_")


def cidade_no_titulo(title):
    """Se o título cita uma cidade do Vale, devolve o NOME dela (a 1ª que aparece). Senão None.
    Reusado pela imagem (arsenal/Street View) e pelo selo da cidade na capa."""
    t = _norm(title)
    achados = [(t.find(k), nome) for k, nome in _CIDADES_VALE if k in t]
    return min(achados)[1] if achados else None


def _especifico(news, seed, title, sensivel=False):
    """Match ESPECÍFICO: situação → cidade → categoria (inclui o acervo IA). None se nada casa.
    sensivel=True: pula slugs proibidos (prédio público/cidade identificável nunca ilustra crime)."""
    slug = _situacao_slug(title)
    if slug and not (sensivel and _slug_proibido_sensivel(slug)):
        p = _file(slug, seed)
        if p:
            return p
    # cidade — PREFERE a citada no TÍTULO (o campo city às vezes vem errado).
    # 🔴 Em sensível, NUNCA: foto identificável da cidade + crime = associação indevida.
    if not sensivel:
        city = _norm(cidade_no_titulo(title) or news["city"])
        if city:
            p = _file("cidade_" + city, seed) or _file(city, seed)
            if p:
                return p
    slug = _CATEGORIA.get((news["category"] or "").strip().lower())
    if slug and not (sensivel and _slug_proibido_sensivel(slug)):
        p = _file(slug, seed)
        if p:
            return p
    return None


def _generico(seed):
    """Fallback GENÉRICO do Vale: cidade_geral/geral; senão QUALQUER aérea de cidade que exista."""
    p = _file("cidade_geral", seed) or _file("geral", seed)
    if p:
        return p
    cidades = sorted(glob.glob(os.path.join(BG_DIR, "cidade_*.jpg")) +
                     glob.glob(os.path.join(BG_DIR, "cidade_*.jpeg")) +
                     glob.glob(os.path.join(BG_DIR, "cidade_*.png")))
    return cidades[seed % len(cidades)] if cidades else None


def buscar(news, permitir_generico=True, sensivel=False):
    """Caminho da NOSSA imagem (arsenal fixo static/bg + acervo IA no volume) mais adequada, ou
    None. Prioridade: situação → cidade → categoria → [genérico do Vale].
    permitir_generico=False PARA no específico — usado quando a IA (nanobanana) vai preencher o
    buraco com uma imagem sob medida (e salvar no acervo p/ reuso). O genérico vira fallback final.
    sensivel=True (crime/tragédia): sem cidade identificável, sem prédio público, sem genérico de
    cidade — só situação neutra (policial/seguranca) ou None (→ card de marca)."""
    if not _on():
        return None
    try:
        seed = int(news["id"])
    except Exception:
        seed = 0
    title = news["title"] or ""
    p = _especifico(news, seed, title, sensivel=sensivel)
    if p:
        return p
    if sensivel:
        return None          # genérico é aéreo de CIDADE → proibido em crime; card resolve
    return _generico(seed) if permitir_generico else None
