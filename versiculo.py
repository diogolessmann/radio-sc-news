# -*- coding: utf-8 -*-
"""
versiculo.py — 🙏 MENSAGEM DO DIA (pedido do dono, 27/jul/2026).

Todo dia de manhã (6h40), um card devocional: versículo + reflexão curta, sobre um
amanhecer do Vale. Série com identidade PRÓPRIA (não confunde com notícia).

REGRAS EDITORIAIS (blindagem combinada com o dono):
  - Versículos UNIVERSAIS (esperança, gratidão, trabalho, família, paz) — texto da
    Almeida Revista e Corrigida (domínio público no Brasil).
  - ZERO pregação, ZERO doutrina, ZERO mistura com pauta política. É devocional de
    serviço — a prateleira do "café com fé", não a do noticiário.
  - Visual próprio (amanhecer + serif) pra ninguém confundir com card de notícia.

Rotação determinística (dia do ano) — sem repetir até rodar a lista, sem estado.
Custo por dia: ZERO (banco curado + card PIL local; fundos gerados uma única vez).
Idempotente: marker por data (não posta 2x). Desliga com VERSICULO_ON=0.
Monetização futura: espaço reservado no rodapé pro selo "OFERECIMENTO".
"""
import os
import sys
from datetime import date, datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# {ref, texto (ARC), reflexao (1 frase universal)}
VERSICULOS = [
    ("Salmos 118:24", "Este é o dia que fez o Senhor; regozijemo-nos e alegremo-nos nele.", "Hoje é presente — vive ele por inteiro."),
    ("Filipenses 4:13", "Posso todas as coisas naquele que me fortalece.", "A força que te falta, a fé completa."),
    ("Provérbios 3:5", "Confia no Senhor de todo o teu coração e não te estribes no teu próprio entendimento.", "Nem tudo precisa fazer sentido agora."),
    ("Salmos 23:1", "O Senhor é o meu pastor; nada me faltará.", "Respira: tu não caminhas sozinho."),
    ("Isaías 41:10", "Não temas, porque eu sou contigo; não te assombres, porque eu sou o teu Deus.", "O medo bate, mas não mora."),
    ("Mateus 11:28", "Vinde a mim, todos os que estais cansados e oprimidos, e eu vos aliviarei.", "Descansar também é um ato de fé."),
    ("Provérbios 16:3", "Confia ao Senhor as tuas obras, e teus pensamentos serão estabelecidos.", "Entrega o dia antes de começar o dia."),
    ("Salmos 46:1", "Deus é o nosso refúgio e fortaleza, socorro bem presente na angústia.", "Abrigo não falta pra quem sabe onde procurar."),
    ("Josué 1:9", "Esforça-te e tem bom ânimo; não temas, nem te espantes, porque o Senhor, teu Deus, é contigo por onde quer que andares.", "Coragem é seguir mesmo com o coração apertado."),
    ("Lamentações 3:22-23", "As misericórdias do Senhor são a causa de não sermos consumidos; novas são a cada manhã.", "Cada amanhecer é um recomeço assinado."),
    ("Colossenses 3:23", "E, tudo quanto fizerdes, fazei-o de todo o coração.", "Capricho no pequeno é oração em silêncio."),
    ("Gálatas 6:9", "E não nos cansemos de fazer o bem, porque a seu tempo ceifaremos, se não houvermos desfalecido.", "O bem plantado sempre brota — no tempo certo."),
    ("1 Tessalonicenses 5:18", "Em tudo dai graças, porque esta é a vontade de Deus em Cristo Jesus para convosco.", "Gratidão muda o olhar antes de mudar o dia."),
    ("Salmos 37:5", "Entrega o teu caminho ao Senhor; confia nele, e ele o fará.", "Faz a tua parte — e solta o resto."),
    ("João 14:27", "Deixo-vos a paz, a minha paz vos dou.", "Paz não é ausência de problema; é presença de confiança."),
    ("Provérbios 17:22", "O coração alegre serve de bom remédio.", "Um sorriso de manhã já é meio caminho."),
    ("Salmos 121:1-2", "Elevo os meus olhos para os montes: de onde me virá o socorro? O meu socorro vem do Senhor.", "Olha pra cima antes de olhar pro problema."),
    ("Isaías 40:31", "Mas os que esperam no Senhor renovarão as suas forças e subirão com asas como águias.", "Esperar também é avançar."),
    ("Salmos 90:17", "E seja sobre nós a graça do Senhor, nosso Deus; e confirma sobre nós a obra das nossas mãos.", "Que o teu trabalho de hoje tenha propósito."),
    ("Mateus 5:9", "Bem-aventurados os pacificadores, porque eles serão chamados filhos de Deus.", "Ser ponte vale mais que ter razão."),
    ("Salmos 133:1", "Oh! Quão bom e quão suave é que os irmãos vivam em união!", "Família unida é o maior patrimônio."),
    ("1 Pedro 4:8", "Tende ardente caridade uns para com os outros, porque a caridade cobrirá a multidão de pecados.", "Amor cobre o que a crítica escancara."),
    ("Lucas 6:31", "E, como vós quereis que os homens vos façam, da mesma maneira lhes fazei vós também.", "A regra de ouro nunca sai de moda."),
    ("Efésios 4:32", "Antes, sede uns para com os outros benignos, misericordiosos, perdoando-vos uns aos outros.", "Perdão pesa menos que mágoa."),
    ("Provérbios 15:1", "A resposta branda desvia o furor.", "Fala manso — ganha o dia."),
    ("Provérbios 11:25", "A alma generosa engordará, e o que regar também será regado.", "Quem ajuda, colhe ajuda."),
    ("Salmos 34:8", "Provai e vede que o Senhor é bom; bem-aventurado o homem que nele confia.", "Bondade se experimenta, não se explica."),
    ("Romanos 12:12", "Alegrai-vos na esperança, sede pacientes na tribulação, perseverai na oração.", "Três remédios pra qualquer dia difícil."),
    ("Filipenses 4:6", "Não estejais inquietos por coisa alguma; antes, as vossas petições sejam em tudo conhecidas diante de Deus.", "Preocupação nenhuma resolveu um amanhã."),
    ("Salmos 19:14", "Sejam agradáveis as palavras da minha boca e a meditação do meu coração perante a tua face, Senhor.", "Que o teu falar de hoje construa."),
    ("Eclesiastes 3:1", "Tudo tem o seu tempo determinado, e há tempo para todo propósito debaixo do céu.", "Nada em ti está atrasado."),
    ("Salmos 30:5", "O choro pode durar uma noite, mas a alegria vem pela manhã.", "Aguenta a noite — a manhã já vem."),
    ("Miquéias 6:8", "Que é o que o Senhor pede de ti, senão que pratiques a justiça, e ames a beneficência, e andes humildemente?", "Simples assim: justiça, bondade, humildade."),
    ("Salmos 4:8", "Em paz também me deitarei e dormirei, porque só tu, Senhor, me fazes habitar em segurança.", "Dorme em paz quem entrega o dia."),
    ("Jeremias 29:11", "Porque eu bem sei os pensamentos que penso de vós, diz o Senhor; pensamentos de paz e não de mal, para vos dar o fim que esperais.", "O plano pra tua vida é maior que o teu medo."),
    ("Salmos 28:7", "O Senhor é a minha força e o meu escudo; nele confiou o meu coração, e fui socorrido.", "Força emprestada do alto não acaba."),
    ("João 13:34", "Um novo mandamento vos dou: Que vos ameis uns aos outros.", "Amar é o único mandamento que resume todos."),
    ("Romanos 12:10", "Amai-vos cordialmente uns aos outros com amor fraternal, preferindo-vos em honra uns aos outros.", "Honrar o outro engrandece os dois."),
    ("Tiago 1:17", "Toda boa dádiva e todo dom perfeito vêm do alto.", "Conta as bênçãos antes de contar os problemas."),
    ("Gálatas 5:22", "Mas o fruto do Espírito é: amor, gozo, paz, longanimidade, benignidade, bondade, fé, mansidão, temperança.", "Nove frutos — escolhe um pra regar hoje."),
    ("Salmos 143:8", "Faze-me ouvir a tua benignidade pela manhã, pois em ti confio.", "Começa o dia ouvindo o que edifica."),
    ("Filipenses 4:8", "Tudo o que é verdadeiro, tudo o que é honesto, tudo o que é justo, tudo o que é puro, tudo o que é amável — nisso pensai.", "Teu dia vira aquilo que tu alimenta na mente."),
]

FUNDOS_DIR = os.path.join("static", "bg_versiculo")
OUT_DIR = os.path.join("static", "social")


def do_dia(quando=None):
    """Versículo + fundo do dia — rotação pelo dia do ano (determinística, sem estado)."""
    d = quando or date.today()
    v = VERSICULOS[d.toordinal() % len(VERSICULOS)]
    fundos = sorted(f for f in os.listdir(FUNDOS_DIR) if f.endswith(".jpg")) or ["amanhecer-1.jpg"]
    fundo = os.path.join(FUNDOS_DIR, fundos[d.toordinal() % len(fundos)])
    return v, fundo


def gerar_card(quando=None):
    """Card 1080x1350 com identidade PRÓPRIA (serif + amanhecer). Devolve o caminho."""
    from PIL import Image, ImageDraw, ImageFilter
    import gen_instagram as gi

    (ref, texto, reflexao), fundo = do_dia(quando)
    W, H = 1080, 1350
    img = Image.open(fundo).convert("RGB").resize((W, H))
    # escurece suave embaixo e no meio pra tipografia branca respirar
    ov = Image.new("L", (W, H), 0)
    dv = ImageDraw.Draw(ov)
    dv.rectangle([0, 0, W, H], fill=70)
    dv.rectangle([0, int(H * .58), W, H], fill=130)
    ov = ov.filter(ImageFilter.GaussianBlur(60))
    img.paste(Image.new("RGB", (W, H), (10, 10, 14)), (0, 0), ov)
    d = ImageDraw.Draw(img)

    GOLD = "#F5C518"
    # kicker
    fk = gi.font(34, impact=True)
    t = "🙏 MENSAGEM DO DIA"
    t_plain = "MENSAGEM DO DIA"
    w = d.textlength(t_plain, font=fk)
    d.text(((W - w) / 2, 96), t_plain, font=fk, fill=GOLD)
    d.line([(W - 260) / 2, 160, (W + 260) / 2, 160], fill=GOLD, width=3)

    # versículo (grande, centralizado)
    fv = gi.font(58, impact=True)
    linhas = gi.wrap(d, f"“{texto}”", fv, W - 170)
    if len(linhas) > 7:                       # versículo longo -> fonte menor
        fv = gi.font(48, impact=True)
        linhas = gi.wrap(d, f"“{texto}”", fv, W - 170)
    alt = len(linhas) * (fv.size + 16)
    y = max(240, int(H * .52) - alt // 2)
    for ln in linhas:
        w = d.textlength(ln, font=fv)
        d.text(((W - w) / 2, y), ln, font=fv, fill="#FFFFFF")
        y += fv.size + 16

    # referência
    fr = gi.font(38, impact=True)
    w = d.textlength(ref, font=fr)
    d.text(((W - w) / 2, y + 26), ref, font=fr, fill=GOLD)

    # reflexão
    fx = gi.font(31)
    linhas_r = gi.wrap(d, reflexao, fx, W - 220)
    yy = y + 26 + 78
    for ln in linhas_r:
        w = d.textlength(ln, font=fx)
        d.text(((W - w) / 2, yy), ln, font=fx, fill="#E8E4D8")
        yy += 42

    # rodapé (espaço reservado p/ futuro selo OFERECIMENTO)
    fb = gi.font(28, impact=True)
    rod = "@radiosc.news"
    w = d.textlength(rod, font=fb)
    d.text(((W - w) / 2, H - 92), rod, font=fb, fill="#FFFFFF")

    os.makedirs(OUT_DIR, exist_ok=True)
    stamp = (quando or date.today()).strftime("%Y%m%d")
    out = os.path.join(OUT_DIR, f"versiculo_{stamp}.jpg")
    img.save(out, "JPEG", quality=92)
    return out, ref


def legenda(quando=None):
    (ref, texto, reflexao), _ = do_dia(quando)
    return (f"🙏 Mensagem do dia pra começar bem.\n\n“{texto}”\n— {ref}\n\n{reflexao}\n\n"
            f"➡️ Manda pra alguém que precisa ler isso hoje.\n"
            f"➕ Segue @radiosc.news pra receber todas as manhãs.\n\n"
            f"#mensagemdodia #bomdia #fé #valedoitapocu")


def _marker(stamp):
    return os.path.join(OUT_DIR, f".versiculo_{stamp}.done")


def run(post=True):
    """Gera e publica o card do dia (imagem única no feed). Idempotente por data."""
    if os.environ.get("VERSICULO_ON", "1").strip() == "0":
        return {"ok": False, "motivo": "VERSICULO_ON=0"}
    stamp = date.today().strftime("%Y%m%d")
    if os.path.exists(_marker(stamp)):
        return {"ok": False, "motivo": "ja postou hoje"}
    card, ref = gerar_card()
    if not post or os.environ.get("SOCIAL_AUTOPOST", "0") != "1":
        print(f"[versiculo] (dry) card gerado: {card}")
        return {"ok": True, "dry": True, "card": card}
    import distribuidor as dist
    url = f"{dist.PUBLIC_BASE_URL}/static/social/{os.path.basename(card)}"
    import requests
    base = f"https://graph.facebook.com/v21.0/{dist.META_IG_USER_ID}"
    r = requests.post(f"{base}/media", data={
        "image_url": url, "caption": legenda(),
        "access_token": dist.META_PAGE_TOKEN}, timeout=60)
    r.raise_for_status()
    cid = r.json()["id"]
    r2 = requests.post(f"{base}/media_publish", data={
        "creation_id": cid, "access_token": dist.META_PAGE_TOKEN}, timeout=60)
    r2.raise_for_status()
    with open(_marker(stamp), "w") as f:
        f.write(datetime.now().isoformat())
    print(f"[versiculo] 🙏 postado: {ref}")
    return {"ok": True, "ref": ref, "ig": r2.json()}


if __name__ == "__main__":
    print(run(post="--post" in sys.argv))
