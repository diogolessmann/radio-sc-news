# -*- coding: utf-8 -*-
"""
gen_midiakit.py — MÍDIA KIT da Rádio SC News em imagens (deck pro WhatsApp).

Gera 5 cards 1080x1350 na identidade da Rádio, prontos pra mandar DIRETO no zap
do anunciante — imagem abre inline no WhatsApp, ninguém precisa clicar em link.

Atualize os NÚMEROS abaixo e rode de novo quando a conta crescer:
    venv\\Scripts\\python.exe gen_midiakit.py
Saída: Desktop\\MIDIA_KIT_RADIO_SC\\
"""
import os

from PIL import Image, ImageDraw

import gen_instagram as gi

# ── NÚMEROS (atualizar aqui e regerar) ───────────────────────────────────────
VIEWS_30D = "842 MIL"
SEGUIDORES = "6,2 MIL"
POSTS_MES = "+300"
WHATS_VENDA = "(47) 99101-1351"

W, H = gi.W, gi.H
CARD_BG = "#181a22"
BORDA = "#2a2d3a"
VERDE = getattr(gi, "WHATS", "#25d366")


def _canvas():
    c = Image.new("RGB", (W, H), gi.BG)
    d = ImageDraw.Draw(c)
    gi.brand_header(d)
    return c, d


def _center(d, text, fnt, y, fill):
    w = d.textlength(text, font=fnt)
    d.text(((W - w) / 2, y), text, font=fnt, fill=fill)
    return y + fnt.size


def _save(c, outdir, nome):
    p = os.path.join(outdir, nome)
    c.convert("RGB").save(p, "JPEG", quality=92)
    print("  ok:", p)
    return p


def slide_capa(outdir):
    c, d = _canvas()
    _center(d, "MÍDIA KIT", gi.font(150, impact=True), 340, gi.WHITE)
    _center(d, "2026", gi.font(96, impact=True), 520, gi.GOLD)
    _center(d, "Sua marca na frente do Vale inteiro", gi.font(42), 700, gi.WHITE)
    f = gi.font(30)

    def _pills(row, y):
        tw = sum(d.textlength(t, font=f) + 52 for t in row) + 16 * (len(row) - 1)
        x = (W - tw) / 2
        for t in row:
            x = gi.pill(d, x, y, t, f, gi.RED, gi.WHITE) + 16

    _pills(["JARAGUÁ DO SUL", "SCHROEDER", "GUARAMIRIM"], 860)
    _pills(["JOINVILLE", "CORUPÁ"], 950)
    gi.footer_site(d)
    return _save(c, outdir, "midiakit_1_capa.jpg")


def slide_numeros(outdir):
    c, d = _canvas()
    _center(d, "NÚMEROS QUE FALAM SOZINHOS", gi.font(44, impact=True), 190, gi.GOLD)
    stats = [
        (VIEWS_30D, "visualizações nos últimos 30 dias"),
        (SEGUIDORES, "seguidores — e dobrando a cada mês"),
        (POSTS_MES, "posts por mês, 7 dias por semana"),
        ("100%", "orgânico — zero anúncio pago"),
    ]
    y = 300
    for num, lab in stats:
        _center(d, num, gi.font(105, impact=True), y, gi.WHITE)
        _center(d, lab, gi.font(32), y + 122, gi.MUTED)
        y += 225
    _center(d, "Fonte: painel profissional do Instagram @radiosc.news", gi.font(24, bold=False), 1215, gi.MUTED)
    gi.footer_site(d)
    return _save(c, outdir, "midiakit_2_numeros.jpg")


def slide_produto(outdir):
    c, d = _canvas()
    _center(d, "O QUE FAZEMOS PELA SUA MARCA", gi.font(42, impact=True), 190, gi.GOLD)
    blocos = [
        ("1", "SUA HISTÓRIA VIRA REPORTAGEM",
         "A origem, a família, a equipe — contada com credibilidade de notícia, não com cara de anúncio."),
        ("2", "IMPULSIONAMENTO INCLUSO",
         "A gente paga pro Instagram mostrar o post pra SUA cidade. Alcance garantido, sem você mexer em nada."),
        ("3", "SELO NO BOM DIA, VALE",
         "Sua marca como 'Oferecimento' no post que a região vê toda manhã, todos os dias."),
    ]
    y = 310
    for num, tit, txt in blocos:
        d.ellipse([70, y, 150, y + 80], fill=gi.GOLD)
        fnum = gi.font(46, impact=True)
        wnum = d.textlength(num, font=fnum)
        d.text((70 + (80 - wnum) / 2, y + 12), num, font=fnum, fill=gi.BLACK)
        d.text((180, y - 2), tit, font=gi.font(40, impact=True), fill=gi.WHITE)
        f = gi.font(30)
        lines = gi.wrap(d, txt, f, W - 180 - 70)
        gi.draw_lines(d, lines, f, 180, y + 58, gi.MUTED, 40)
        y += 90 + len(lines) * 40 + 62
    gi.footer_site(d)
    return _save(c, outdir, "midiakit_3_produto.jpg")


def slide_planos(outdir):
    c, d = _canvas()
    _center(d, "PLANOS — MENOS POR MAIS", gi.font(44, impact=True), 190, gi.GOLD)
    planos = [
        ("REPORTAGEM DA SUA MARCA", "R$ 350", "post avulso — versão TURBINADA com impulsionamento: R$ 450", False),
        ("PARCEIRO DO VALE", "R$ 890/mês", "selo diário no Bom dia + 3 posts + impulsionamento + relatório de alcance", True),
        ("PARCEIRO MASTER", "R$ 1.500/mês", "tudo do Parceiro + 4 posts + Reels narrado + prioridade total", False),
    ]
    y = 300
    for tit, preco, desc, destaque in planos:
        d.rounded_rectangle([60, y, W - 60, y + 258], radius=24, fill=CARD_BG,
                            outline=gi.GOLD if destaque else BORDA, width=4 if destaque else 2)
        d.text((100, y + 26), tit, font=gi.font(36, impact=True), fill=gi.WHITE)
        d.text((100, y + 82), preco, font=gi.font(62, impact=True), fill=gi.GOLD)
        f = gi.font(27)
        lines = gi.wrap(d, desc, f, W - 200)
        gi.draw_lines(d, lines, f, 100, y + 172, gi.MUTED, 36)
        if destaque:
            f2 = gi.font(24)
            tw = d.textlength("MAIS PROCURADO", font=f2)
            gi.pill(d, W - 60 - tw - 70, y - 22, "MAIS PROCURADO", f2, gi.GOLD, gi.BLACK, pad_x=20, pad_y=8)
        y += 298
    _center(d, "Valores de lançamento — sobem conforme a audiência cresce.", gi.font(24, bold=False), 1215, gi.MUTED)
    gi.footer_site(d)
    return _save(c, outdir, "midiakit_4_planos.jpg")


def slide_fechamento(outdir):
    c, d = _canvas()
    _center(d, "ANÚNCIO AS PESSOAS PULAM.", gi.font(56, impact=True), 360, gi.WHITE)
    _center(d, "NOTÍCIA AS PESSOAS LEEM.", gi.font(56, impact=True), 450, gi.GOLD)
    _center(d, "Bora contar a história da sua marca pro Vale?", gi.font(38), 620, gi.WHITE)
    # botão WhatsApp
    bw, bh = 720, 110
    bx, by = (W - bw) / 2, 760
    d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=26, fill=VERDE)
    f = gi.font(44, impact=True)
    t = f"WhatsApp  {WHATS_VENDA}"
    tw = d.textlength(t, font=f)
    d.text(((W - tw) / 2, by + 28), t, font=f, fill=gi.WHITE)
    _center(d, "@radiosc.news   ·   radioscnews.com.br", gi.font(32), 950, gi.MUTED)
    _center(d, "Norte de Santa Catarina — Jaraguá, Schroeder, Guaramirim, Joinville e Corupá",
            gi.font(24, bold=False), 1030, gi.MUTED)
    gi.footer_site(d)
    return _save(c, outdir, "midiakit_5_contato.jpg")


def main():
    outdir = os.path.join(os.path.expanduser("~"), "Desktop", "MIDIA_KIT_RADIO_SC")
    os.makedirs(outdir, exist_ok=True)
    print("Gerando midia kit em", outdir)
    slide_capa(outdir)
    slide_numeros(outdir)
    slide_produto(outdir)
    slide_planos(outdir)
    slide_fechamento(outdir)
    print("PRONTO: 5 cards. Manda os 5 juntos no WhatsApp do cliente.")


if __name__ == "__main__":
    main()
