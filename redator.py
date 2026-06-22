# -*- coding: utf-8 -*-
"""
redator.py — REDAÇÃO SOB DEMANDA da Rádio SC News.
Você cola a informação bruta (WhatsApp, release, ideia) -> o redator reescreve no tom
da Rádio -> o revisor sinaliza o que confirmar -> gera o carrossel + legenda -> você corrige.

NÃO publica nada (você posta manual). Reaproveita o gerador oficial (gen_instagram).

Uso INTERATIVO (recomendado p/ o dia a dia):
  venv\\Scripts\\python.exe redator.py
  (ou clique 2x em Gerar_Materia.bat)

Uso DIRETO (pra automação/teste):
  venv\\Scripts\\python.exe redator.py --arquivo info.txt --cidade Schroeder --categoria politica --titulo "..."
"""
import argparse, os, re, sys, unicodedata
from datetime import datetime

import gen_instagram as gi

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Groq opcional (mesma chave do distribuidor). Sem ela, usa redator local.
try:
    import distribuidor as dist
    GROQ_KEY = dist.GROQ_API_KEY
except Exception:
    GROQ_KEY = os.environ.get("GROQ_API_KEY", "")

CATEGORIAS = list(gi.CAT_LABEL.keys())

# ---- REVISOR: sinaliza o que um editor confere antes de publicar -----------
NUM_RE = re.compile(r"r\$\s?[\d\.\s]+\s*(?:mil|milh[õo]es|reais)?|\d+\s*(?:mil|milh[õo]es)", re.I)
POLIT_RE = re.compile(r"\b(pt|pl|psdb|mdb|novo|psd|pp|republican|deputad|vereador|prefeit|"
                      r"emenda|partido|c[âa]mara|senad)\b", re.I)
SENS_RE = re.compile(r"\b(pres[oa]|morte|morreu|crime|acusad|investigad|processo|"
                     r"den[úu]ncia|acidente)\b", re.I)

def _strip(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))

def revisar(titulo, corpo, fonte):
    avisos = []
    blob = f"{titulo} {corpo}"
    nums = NUM_RE.findall(blob)
    if nums:
        avisos.append(f"💰 Confira os VALORES com a fonte oficial: {', '.join(set(n.strip() for n in nums))}")
    if POLIT_RE.search(blob) and not fonte:
        avisos.append("🏛️ Pauta política: ATRIBUA a fonte (ex: 'segundo o gabinete X') e "
                      "ofereça direito de resposta/equilíbrio a outros lados.")
    if SENS_RE.search(_strip(blob)):
        avisos.append("⚠️ Tema sensível: cuidado com acusação sem prova (risco de processo).")
    if not avisos:
        avisos.append("✓ Sem alertas — ainda assim confirme a fonte antes de publicar.")
    return avisos

# ---- REDATOR ---------------------------------------------------------------
def _limpa(t):
    # tira instruções de quem mandou ("se possível publicar", "manchete:", etc.)
    t = re.sub(r"(?i)se poss[íi]vel.*?informa[çc][ãa]o\.?", "", t)
    t = re.sub(r"(?i)^\s*(manchete|t[íi]tulo)\s*:?", "", t)
    return re.sub(r"\s+", " ", t).strip()

def redator_groq(bruto, cidade, fonte):
    if not GROQ_KEY:
        return None
    import requests
    atrib = f" Atribua a informação à fonte: {fonte}." if fonte else \
            " Se for afirmação de um único lado (político/partidário), deixe claro que é segundo a fonte."
    prompt = (
        "Você é repórter da Rádio SC News (Norte de SC). Reescreva a informação abaixo como "
        "uma NOTÍCIA curta, em português do Brasil, tom de vizinho bem informado — claro, "
        "direto e SEM sensacionalismo. Não invente nada (principalmente números)." + atrib +
        " Devolva no formato exato:\nTITULO: <manchete forte, sem ponto final>\nCORPO: <2 a 4 "
        f"frases>\n\nCIDADE: {cidade}\nINFORMAÇÃO BRUTA: {bruto}"
    )
    try:
        r = requests.post(dist.GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={"model": dist.GROQ_MODEL, "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.4, "max_tokens": 360}, timeout=30)
        r.raise_for_status()
        txt = r.json()["choices"][0]["message"]["content"].strip()
        mt = re.search(r"(?is)titulo:\s*(.+?)\s*corpo:\s*(.+)$", txt)
        if mt:
            return mt.group(1).strip().strip('"'), mt.group(2).strip().strip('"')
    except Exception as e:
        print(f"   ! Groq indisponível ({e}) — usando redator local")
    return None

def _fonte_ja_citada(corpo, fonte):
    """True se a fonte já aparece no corpo (evita duplicar 'Segundo X, ...X...')."""
    toks = [t for t in _strip(fonte).split()
            if len(t) > 3 and t not in ("presidente", "deputado", "deputada",
                                        "prefeito", "schroeder", "gabinete", "vereador")]
    return any(t in _strip(corpo) for t in toks)

def redator_local(bruto, titulo, fonte):
    corpo = _limpa(bruto)
    # manchete deriva ANTES da atribuição (pra não herdar o "Segundo..."), curta e limpa
    if not titulo:
        prim = re.split(r"(?<=[.!?])\s", corpo)[0]
        titulo = prim[:85].rstrip(" .,;") + ("..." if len(prim) > 85 else "")
    # atribuição só no CORPO, e só se a fonte ainda não foi citada
    if fonte and not _fonte_ja_citada(corpo, fonte):
        corpo = f"Segundo {fonte}, " + corpo[0].lower() + corpo[1:]
    return titulo, corpo

def redigir(bruto, cidade, titulo, fonte):
    g = redator_groq(bruto, cidade, fonte)
    if g:
        t, c = g
        return (titulo or t), c
    return redator_local(bruto, titulo, fonte)

# ---- LEGENDA ---------------------------------------------------------------
def legenda(titulo, corpo, cidade, categoria):
    tags = gi.CITY_TAGS.get(cidade, []) + gi.CAT_TAGS.get(categoria, []) + gi.BASE_TAGS
    seen, uniq = set(), []
    for t in tags:
        if t not in seen: seen.add(t); uniq.append(t)
    return (f"📢 {titulo}\n\n{corpo}\n\n"
            f"📍 {cidade}  ·  🔊 Leia e ouça no site (link na bio)\n\n" + " ".join(uniq))

# ---- ARTE ------------------------------------------------------------------
# Formatos de saída (rótulo amigável pra UI). A Redação produz o artefato escolhido.
FORMATOS = {
    "site": "Só pro site (texto)",
    "story1": "Story simples (1 imagem)",
    "story_carrossel": "Story carrossel (3-5, storytelling)",
    "feed": "Feed (carrossel)",
    "reels": "Reels com áudio",
}


def _news(titulo, cidade, categoria, admin_image=None):
    # admin_image (nome do arquivo em uploads/) tem PRIORIDADE na capa: o cover_image usa a foto
    # que o dono colou em vez do arsenal/card. None = cai na cascata normal.
    return {"image_url": None, "admin_image": admin_image, "city": cidade,
            "category": categoria, "title": titulo}


def _slides_feed(news, corpo, outdir):
    """Carrossel padrão (1080x1350): capa + até 2 slides de texto + CTA (motor oficial)."""
    import textwrap
    paths = [gi.slide_cover(news, outdir)]
    for i, ch in enumerate(textwrap.wrap(corpo, 300, break_long_words=False)[:2], 1):
        paths.append(gi.slide_text(ch, i, 2, outdir, len(paths) + 1))
    paths.append(gi.slide_cta(news, outdir, len(paths) + 1))
    return paths


def gerar_arte(titulo, corpo, cidade, categoria, slug):
    """Compat: gera o carrossel de feed (usado pelo CLI). Devolve (outdir, paths)."""
    news = _news(titulo, cidade, categoria)
    outdir = os.path.join("instagram_posts", "redator_" + slug)
    os.makedirs(outdir, exist_ok=True)
    return outdir, _slides_feed(news, corpo, outdir)


def gerar_formato(formato, titulo, corpo, cidade, categoria, slug, admin_image=None):
    """Gera o ARTEFATO do formato escolhido. Devolve dict:
       {kind:'none'|'imgs'|'video'|'error', outdir, paths:[...], video:'/...'}.
       admin_image (opcional): foto colada pelo dono → vira a CAPA. Reusa gen_instagram (imagens)
       e reels.py (vídeo) — zero dependência nova."""
    news = _news(titulo, cidade, categoria, admin_image)
    outdir = os.path.join("instagram_posts", "redator_" + slug)
    os.makedirs(outdir, exist_ok=True)

    if formato == "site":                       # só o texto, sem arte
        return {"kind": "none", "outdir": outdir, "paths": []}

    if formato == "feed":                       # carrossel 1080x1350 (padrão)
        return {"kind": "imgs", "outdir": outdir, "paths": _slides_feed(news, corpo, outdir)}

    if formato in ("story1", "story_carrossel"):   # 9:16 (1 imagem ou 3-5 storytelling)
        import reels as rl
        base = ([gi.slide_cover(news, outdir)] if formato == "story1"
                else _slides_feed(news, corpo, outdir)[:5])
        sdir = os.path.join(outdir, "story")
        os.makedirs(sdir, exist_ok=True)
        paths = [rl._to_vertical(p, os.path.join(sdir, f"s{i}.jpg")) for i, p in enumerate(base, 1)]
        return {"kind": "imgs", "outdir": outdir, "paths": paths}

    if formato == "reels":                      # vídeo vertical narrado
        import reels as rl
        import tts_engine
        base = _slides_feed(news, corpo, outdir)
        vdir = os.path.join(outdir, "vert")
        os.makedirs(vdir, exist_ok=True)
        vslides = [rl._to_vertical(p, os.path.join(vdir, f"v{i}.jpg")) for i, p in enumerate(base, 1)]
        script = re.sub(r"\s+", " ",
                        f"{titulo}. {corpo} Siga a Rádio SC News e fique por dentro do Vale.").strip()
        os.makedirs(rl.AUDIO_DIR, exist_ok=True)
        narr = os.path.join(rl.AUDIO_DIR, f"redator_{slug}.mp3")
        if not tts_engine.generate_tts(script, narr, category=categoria, prefer_free=True):
            return {"kind": "error", "erro": "não consegui gerar a narração (TTS)."}
        pubdir = os.path.join("static", "redacao")
        os.makedirs(pubdir, exist_ok=True)
        mp4 = os.path.join(pubdir, f"reel_{slug}.mp4")
        rl.build_reel(vslides, narr, mp4, caption_script=script, capdir=os.path.join(outdir, "caps"))
        return {"kind": "video", "outdir": outdir, "video": "/static/redacao/" + os.path.basename(mp4)}

    return {"kind": "imgs", "outdir": outdir, "paths": _slides_feed(news, corpo, outdir)}

# ---- fluxo -----------------------------------------------------------------
def _slug(t):
    return re.sub(r"[^a-z0-9]+", "-", _strip(t))[:40].strip("-") or datetime.now().strftime("%H%M")

def produzir(bruto, cidade, categoria, titulo, fonte, salvar=True):
    titulo, corpo = redigir(bruto, cidade, titulo, fonte)
    cap = legenda(titulo, corpo, cidade, categoria)
    avisos = revisar(titulo, corpo, fonte)
    print("\n" + "="*62)
    print("📰 MANCHETE:", titulo)
    print("-"*62)
    print("📝 CORPO:", corpo)
    print("-"*62)
    print("🔎 REVISOR (confira antes de postar):")
    for a in avisos: print("   " + a)
    print("="*62)
    outdir = paths = None
    if salvar:
        outdir, paths = gerar_arte(titulo, corpo, cidade, categoria, _slug(titulo))
        with open(os.path.join(outdir, "legenda.txt"), "w", encoding="utf-8") as f:
            f.write(cap)
        print(f"🖼️  {len(paths)} slides + legenda.txt em: {os.path.abspath(outdir)}")
    print("\n----- LEGENDA -----\n" + cap + "\n")
    return titulo, corpo, cap, outdir

def interativo():
    print("\n=== REDATOR RÁDIO SC NEWS (dry-run, você posta manual) ===\n")
    print("Cole a informação bruta. Termine com uma linha só com FIM:")
    linhas = []
    while True:
        try: l = input()
        except EOFError: break
        if l.strip().upper() == "FIM": break
        linhas.append(l)
    bruto = "\n".join(linhas).strip()
    if not bruto:
        print("Nada informado."); return
    cidade = input("Cidade [Schroeder]: ").strip() or "Schroeder"
    categoria = input(f"Categoria {CATEGORIAS} [politica]: ").strip() or "politica"
    fonte = input("Fonte p/ atribuir (enter p/ pular): ").strip()
    titulo = input("Manchete (enter = redator decide): ").strip()
    while True:
        titulo, corpo, cap, outdir = produzir(bruto, cidade, categoria, titulo, fonte)
        acao = input("\n[A]provar  [E]ditar manchete  [R]efazer corpo  [S]air: ").strip().lower()
        if acao == "a":
            print(f"✅ Aprovado. Slides + legenda em {outdir}. Bora postar!"); break
        elif acao == "e":
            titulo = input("Nova manchete: ").strip() or titulo
        elif acao == "r":
            bruto = input("Cole o corpo corrigido (ou enter p/ manter): ").strip() or bruto
            titulo = ""  # deixa o redator refazer
        else:
            print("Saindo."); break

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arquivo"); ap.add_argument("--texto")
    ap.add_argument("--cidade", default="Schroeder")
    ap.add_argument("--categoria", default="politica")
    ap.add_argument("--titulo", default=""); ap.add_argument("--fonte", default="")
    args = ap.parse_args()
    bruto = args.texto
    if args.arquivo and os.path.exists(args.arquivo):
        bruto = open(args.arquivo, encoding="utf-8").read()
    if not bruto and not sys.stdin.isatty():
        bruto = sys.stdin.read()
    if not bruto:
        return interativo()
    produzir(bruto, args.cidade, args.categoria, args.titulo, args.fonte)

if __name__ == "__main__":
    main()
