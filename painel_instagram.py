# -*- coding: utf-8 -*-
"""Painel de postagem manual no Instagram da Radio SC News.

POR QUE EXISTE (07/set/2026): a Radio passou a vender 5 dias de anuncio pro
comercio da regiao. O cliente manda foto e preco no zap; alguem precisa colar
isso e publicar. Sem este painel, cada venda vira trabalho manual de editor.

COMO FUNCIONA
  1. sobe 1 a 10 imagens (JPG/PNG) OU um PDF -- as paginas do PDF viram cards
  2. cola a legenda
  3. escolhe feed ou story
  4. publica

DETALHE QUE DECIDE TUDO: a Graph API do Instagram nao aceita upload de arquivo.
Ela exige URL PUBLICA da imagem. Por isso tudo e salvo em static/social/, que o
site ja serve, e a URL e montada com PUBLIC_BASE_URL.

Blueprint separado de proposito: o app.py tem 3.7 mil linhas e outras sessoes
mexem nele. Aqui so entram duas linhas de registro.
"""
import io
import os
import re
import time
from datetime import datetime

from flask import Blueprint, redirect, render_template, request, session, url_for

bp_ig = Blueprint("painel_ig", __name__)


@bp_ig.before_request
def _exige_login():
    """Tranca o blueprint inteiro.

    Nasceu de um bug real: a primeira versao subiu SEM protecao e respondia 200
    deslogado -- qualquer um na internet publicaria no Instagram da Radio. O smoke
    test pegou. Usando before_request em vez de decorar rota a rota, qualquer rota
    nova que entrar aqui ja nasce trancada. Nao importa login_required do app.py
    para nao criar import circular; a checagem e a mesma chave de sessao.
    """
    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

SOCIAL_DIR = os.path.join("static", "social")
MAX_CARDS = 10                      # limite do carrossel no Instagram
ALVO_KB = 900                       # a Graph API engasga com arquivo muito grande


def _dist():
    """Importa tarde: o distribuidor le variaveis de ambiente ao carregar."""
    import distribuidor
    return distribuidor


def _limpa(nome):
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", nome)[:60]


def _prepara(im):
    """Deixa a imagem dentro do que o Instagram aceita.

    O feed aceita de 4:5 (0.8) ate 1.91:1. Fora disso ele corta sozinho, e corta
    mal -- entao a barra entra aqui, controlada, em vez de o Instagram decidir.
    """
    from PIL import Image

    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    if im.mode == "L":
        im = im.convert("RGB")

    prop = im.width / im.height
    if prop < 0.8 or prop > 1.91:
        alvo = 0.8 if prop < 0.8 else 1.91
        if prop < alvo:                       # alta demais: alarga
            nova_l = int(round(im.height * alvo))
            tela = Image.new("RGB", (nova_l, im.height), (255, 255, 255))
            tela.paste(im, ((nova_l - im.width) // 2, 0))
        else:                                  # larga demais: aumenta a altura
            nova_a = int(round(im.width / alvo))
            tela = Image.new("RGB", (im.width, nova_a), (255, 255, 255))
            tela.paste(im, (0, (nova_a - im.height) // 2))
        im = tela

    if im.width > 1440:
        im = im.resize((1440, int(im.height * 1440 / im.width)), Image.LANCZOS)
    return im


def _salva(im, prefixo, i):
    """Grava em static/social comprimindo ate caber no alvo."""
    os.makedirs(SOCIAL_DIR, exist_ok=True)
    nome = "%s_%02d.jpg" % (prefixo, i)
    caminho = os.path.join(SOCIAL_DIR, nome)
    q = 88
    while True:
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=q, optimize=True, progressive=True)
        if buf.tell() <= ALVO_KB * 1024 or q <= 55:
            with open(caminho, "wb") as fh:
                fh.write(buf.getvalue())
            return nome
        q -= 8


def _do_pdf(dados, prefixo):
    """Cada pagina do PDF vira um card. Renderiza em 2x pra nao sair mole."""
    import fitz
    from PIL import Image

    doc = fitz.open(stream=dados, filetype="pdf")
    nomes = []
    for i, pag in enumerate(doc):
        if i >= MAX_CARDS:
            break
        pix = pag.get_pixmap(matrix=fitz.Matrix(2, 2))
        im = Image.open(io.BytesIO(pix.tobytes("png")))
        nomes.append(_salva(_prepara(im), prefixo, i + 1))
    doc.close()
    return nomes


def _do_imagens(arquivos, prefixo):
    from PIL import Image

    nomes = []
    for i, f in enumerate(arquivos):
        if i >= MAX_CARDS:
            break
        im = Image.open(io.BytesIO(f.read()))
        nomes.append(_salva(_prepara(im), prefixo, i + 1))
    return nomes


@bp_ig.route("/admin/instagram", methods=["GET"])
def painel_ig():
    return render_template("admin_instagram.html",
                           msg=request.args.get("msg"),
                           erro=request.args.get("erro"),
                           link=request.args.get("link"),
                           max_cards=MAX_CARDS)


@bp_ig.route("/admin/instagram/publicar", methods=["POST"])
def publicar_ig():
    legenda = (request.form.get("legenda") or "").strip()
    destino = request.form.get("destino") or "feed"

    envios = [f for f in request.files.getlist("arquivos") if f and f.filename]
    if not envios:
        return redirect("/admin/instagram?erro=Escolha ao menos uma imagem ou um PDF.")
    if destino == "feed" and not legenda:
        return redirect("/admin/instagram?erro=A legenda e obrigatoria no feed.")

    prefixo = "ig_%s" % datetime.now().strftime("%Y%m%d%H%M%S")
    try:
        primeiro = envios[0]
        if primeiro.filename.lower().endswith(".pdf"):
            nomes = _do_pdf(primeiro.read(), prefixo)
            if not nomes:
                return redirect("/admin/instagram?erro=O PDF nao tem paginas legiveis.")
        else:
            nomes = _do_imagens(envios, prefixo)
    except Exception as e:
        return redirect("/admin/instagram?erro=Falha ao preparar as imagens: %s" % e)

    dist = _dist()
    base = dist.PUBLIC_BASE_URL.rstrip("/")
    urls = ["%s/static/social/%s" % (base, n) for n in nomes]

    # a Graph API vai BUSCAR essas URLs. Se o deploy ainda nao serviu o arquivo,
    # ela falha com erro generico -- por isso o respiro antes de chamar.
    time.sleep(2)

    try:
        if destino == "story":
            res = dist.post_instagram_story(urls[0])
        elif len(urls) == 1:
            res = dist.post_instagram_single(urls[0], legenda)
        else:
            res = dist.post_instagram_carousel(urls, legenda)
    except Exception as e:
        return redirect("/admin/instagram?erro=O Instagram recusou: %s" % str(e)[:220])

    mid = ""
    try:
        mid = dist._extract_ig_id(res) or ""
    except Exception:
        mid = (res or {}).get("id", "") if isinstance(res, dict) else ""

    quant = len(urls)
    ok = "Publicado: %d %s no %s." % (
        quant, "card" if quant == 1 else "cards", "story" if destino == "story" else "feed")
    link = "https://www.instagram.com/" if not mid else "https://www.instagram.com/p/"
    return redirect("/admin/instagram?msg=%s&link=%s" % (ok, link))
