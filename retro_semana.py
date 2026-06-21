# -*- coding: utf-8 -*-
"""
retro_semana.py — "O VALE NA SEMANA": retrospectiva automática (jornalismo de DADOS).

O coelho na cartola: o PRÓPRIO BANCO vira conteúdo. Toda semana o sistema já sabe quantas
notícias cobriu, qual cidade mais apareceu e qual assunto mais bombou — vira um carrossel de
infográfico, altamente salvável, que ninguém no Vale faz. Conteúdo do ~zero de esforço + mostra
AUTORIDADE ("a gente cobre TUDO"). Fica mais esperto quando o Placar tiver dado (ranqueia por
engajamento real); até lá, ranqueia por relevância/recência.

Padrão Enquete/Curiosidade: gera p/ revisão em /admin/retro (scheduler domingo), dono posta.
Reusa gen_instagram (zero dep nova).

Uso: python retro_semana.py    |    retro_semana.run()
"""
import glob
import os
import sqlite3
from collections import Counter
from datetime import datetime

from PIL import Image, ImageDraw

import gen_instagram as gi
import distribuidor as dist

DB_PATH = os.environ.get("DB_PATH", "radio_sc.db")
OUT_BASE = os.path.join("static", "retro")
_DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
_CAT_LABEL = {
    "policial": "Segurança", "politica": "Política", "saude": "Saúde", "esporte": "Esporte",
    "economia": "Economia", "clima": "Tempo", "cultura": "Cultura", "geral": "Geral",
}


def _db():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def _semana(conn):
    rows = conn.execute(
        "SELECT * FROM news WHERE active=1 AND created_at > datetime('now','-7 days')").fetchall()
    if len(rows) < 5:   # snapshot velho / semana fraca: pega as mais recentes
        rows = conn.execute(
            "SELECT * FROM news WHERE active=1 ORDER BY datetime(created_at) DESC LIMIT 90").fetchall()
    return rows


def _numeros(rows):
    cidades = Counter(r["city"] for r in rows if r["city"] in gi.NORTE_SC)
    cats = Counter((r["category"] or "geral").lower() for r in rows)
    dias = Counter()
    for r in rows:
        try:
            dias[datetime.fromisoformat(r["created_at"]).weekday()] += 1
        except Exception:
            pass
    top_cidade = cidades.most_common(1)[0][0] if cidades else "o Vale"
    top_cat = cats.most_common(1)[0][0] if cats else "geral"
    top_dia = _DIAS[dias.most_common(1)[0][0]] if dias else "—"
    return {
        "total": len(rows),
        "cidade": top_cidade,
        "assunto": _CAT_LABEL.get(top_cat, top_cat.capitalize()),
        "dia": top_dia,
        "n_cidades": len(cidades),
    }


def _titulo(r):
    """title_own (nosso texto) se a coluna existir; senão o título original. Blinda banco 'magro'."""
    try:
        t = r["title_own"]
    except (IndexError, KeyError):
        t = None
    return (t or r["title"] or "")


def _top_noticias(rows, n=3):
    """As que mais mexeram: por engajamento real (Placar) se houver; senão relevância/recência."""
    try:
        import placar
        p = placar.painel()
        if p.get("tem_dado") and p.get("top_posts"):
            tit = [t["titulo"] for t in p["top_posts"][:n] if t.get("titulo")]
            if len(tit) >= n:
                return tit
    except Exception:
        pass
    seguras = [r for r in rows if not dist.sensitive_reason(r)]
    local = [r for r in seguras if r["city"] in gi.NORTE_SC] or seguras
    local = sorted(local, key=lambda r: (r["priority"] or 0), reverse=True)
    out, seen = [], []
    for r in local:
        if len(out) >= n:
            break
        if dist.duplicate_of(r, seen):
            continue
        out.append(_titulo(r)[:84])
        seen.append(r)
    return out


# ---------------------------------------------------------------- slides
def _grad(top, bot):
    g = Image.new("RGB", (1, gi.H))
    for y in range(gi.H):
        t = y / gi.H
        g.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    return g.resize((gi.W, gi.H))


def _capa(dia, outdir, n):
    canvas = _grad((14, 15, 21), (44, 16, 22))
    d = ImageDraw.Draw(canvas)
    gi.brand_header(d)
    fs = gi.font(56, impact=True)
    seal = "RETROSPECTIVA"
    w = d.textlength(seal, font=fs)
    d.rounded_rectangle([(gi.W - w) // 2 - 36, 430, (gi.W + w) // 2 + 36, 514], radius=42, fill=gi.GOLD)
    d.text(((gi.W - w) // 2, 444), seal, font=fs, fill=gi.BLACK)
    fb = gi.font(118, impact=True)
    for i, ln in enumerate(["O VALE", "NA SEMANA"]):
        w = d.textlength(ln, font=fb)
        d.text(((gi.W - w) // 2, 560 + i * 140), ln, font=fb, fill=gi.WHITE, stroke_width=3, stroke_fill=gi.BLACK)
    fd = gi.font(46)
    data = f"semana de {dia.strftime('%d/%m')}"
    w = d.textlength(data, font=fd)
    d.text(((gi.W - w) // 2, 880), data, font=fd, fill=gi.MUTED)
    fa = gi.font(40, impact=True)
    arr = "ARRASTA  ->"
    w = d.textlength(arr, font=fa)
    d.rounded_rectangle([(gi.W - w) // 2 - 28, 1230, (gi.W + w) // 2 + 28, 1300], radius=20, fill=gi.RED)
    d.text(((gi.W - w) // 2, 1244), arr, font=fa, fill=gi.WHITE)
    p = os.path.join(outdir, f"slide_{n}.png")
    canvas.convert("RGB").save(p, quality=92)
    return p


def _numeros_slide(num, outdir, n):
    canvas = Image.new("RGB", (gi.W, gi.H), gi.BG)
    d = ImageDraw.Draw(canvas)
    gi.brand_header(d)
    gi.pill(d, 56, 150, "  OS NÚMEROS  ", gi.font(40, impact=True), gi.RED, gi.WHITE)

    # número gigante
    fn = gi.font(200, impact=True)
    s = str(num["total"])
    w = d.textlength(s, font=fn)
    d.text(((gi.W - w) // 2, 300), s, font=fn, fill=gi.GOLD, stroke_width=3, stroke_fill=gi.BLACK)
    fl = gi.font(48)
    lbl = "notícias do Vale cobertas"
    w = d.textlength(lbl, font=fl)
    d.text(((gi.W - w) // 2, 540), lbl, font=fl, fill=gi.WHITE)

    # linhas de destaque
    linhas = [
        ("CIDADE QUE MAIS APARECEU", num["cidade"]),
        ("ASSUNTO QUE MAIS BOMBOU", num["assunto"]),
        ("DIA MAIS MOVIMENTADO", num["dia"].capitalize()),
    ]
    y = 700
    for cap, val in linhas:
        d.text((90, y), cap, font=gi.font(30), fill=gi.MUTED)
        d.text((90, y + 40), val, font=gi.font(58, impact=True), fill=gi.WHITE)
        y += 165
    gi.footer_site(d)
    p = os.path.join(outdir, f"slide_{n}.png")
    canvas.save(p, quality=92)
    return p


def _destaques_slide(titulos, outdir, n):
    canvas = Image.new("RGB", (gi.W, gi.H), gi.BG)
    d = ImageDraw.Draw(canvas)
    gi.brand_header(d)
    gi.pill(d, 56, 150, "  O QUE MEXEU COM O VALE  ", gi.font(38, impact=True), gi.RED, gi.WHITE)
    y = 300
    for i, t in enumerate(titulos[:3], 1):
        d.text((70, y), str(i), font=gi.font(80, impact=True), fill=gi.GOLD)
        ft = gi.font(46, impact=True)
        lines = gi.wrap(d, t, ft, gi.W - 230)[:3]
        ly = y + 6
        for ln in lines:
            d.text((180, ly), ln, font=ft, fill=gi.WHITE)
            ly += int(ft.size * 1.18)
        y = max(ly, y + 130) + 30
    gi.footer_site(d)
    p = os.path.join(outdir, f"slide_{n}.png")
    canvas.save(p, quality=92)
    return p


def _cta_slide(outdir, n):
    canvas = _grad((14, 15, 21), (16, 30, 22))
    d = ImageDraw.Draw(canvas)
    gi.brand_header(d)
    seal = "TODA SEMANA TEM"
    fs = gi.font(44, impact=True)
    w = d.textlength(seal, font=fs)
    d.rounded_rectangle([(gi.W - w) // 2 - 32, 470, (gi.W + w) // 2 + 32, 552], radius=40, fill=gi.GOLD)
    d.text(((gi.W - w) // 2, 484), seal, font=fs, fill=gi.BLACK)
    for i, ln in enumerate(["SEGUE A RÁDIO", "E NÃO PERDE NADA", "DO VALE"]):
        fb = gi.font(80, impact=True)
        w = d.textlength(ln, font=fb)
        d.text(((gi.W - w) // 2, 600 + i * 100), ln, font=fb, fill=gi.WHITE, stroke_width=2, stroke_fill=gi.BLACK)
    handle = "@radioscnews"
    fh = gi.font(60, impact=True)
    w = d.textlength(handle, font=fh)
    d.text(((gi.W - w) // 2, 980), handle, font=fh, fill=gi.GOLD)
    mark = "SALVA E MARCA UM AMIGO DO VALE"
    fm = gi.font(36)
    w = d.textlength(mark, font=fm)
    d.rounded_rectangle([(gi.W - w) // 2 - 30, 1120, (gi.W + w) // 2 + 30, 1190], radius=20, fill=gi.RED)
    d.text(((gi.W - w) // 2, 1133), mark, font=fm, fill=gi.WHITE)
    p = os.path.join(outdir, f"slide_{n}.png")
    canvas.convert("RGB").save(p, quality=92)
    return p


def _legenda(num, titulos):
    tops = "\n".join(f"{i}. {t}" for i, t in enumerate(titulos[:3], 1))
    return (f"📊 O VALE NA SEMANA\n\n"
            f"Foram {num['total']} notícias cobertas em {num['n_cidades']} cidades do Vale. "
            f"{num['cidade']} foi a que mais apareceu e {num['assunto']} foi o assunto do momento.\n\n"
            f"O que mais mexeu com a gente:\n{tops}\n\n"
            f"Seguiu? Toda semana tem a retrospectiva. 👉 @radioscnews\n"
            f"Salva e marca um amigo do Vale 💚\n\n"
            f"#radioscnews #norteSC #valedoitapocu #jaraguadosul #schroeder #guaramirim #joinville")


def run():
    conn = _db()
    rows = _semana(conn)
    if not rows:
        conn.close()
        return {"ok": False, "motivo": "sem notícias"}
    num = _numeros(rows)
    titulos = _top_noticias(rows, 3)
    conn.close()

    dia = datetime.now()
    outdir = os.path.join(OUT_BASE, dia.strftime("%Y-%m-%d"))
    os.makedirs(outdir, exist_ok=True)
    slides = [
        _capa(dia, outdir, 1),
        _numeros_slide(num, outdir, 2),
        _destaques_slide(titulos, outdir, 3),
        _cta_slide(outdir, 4),
    ]
    legenda = _legenda(num, titulos)
    with open(os.path.join(outdir, "legenda.txt"), "w", encoding="utf-8") as f:
        f.write(legenda)
    return {"ok": True, "slides": slides, "pasta": outdir, "legenda": legenda,
            "numeros": num, "titulos": titulos}


def ultima():
    pastas = sorted(glob.glob(os.path.join(OUT_BASE, "*")))
    if not pastas:
        return None
    pasta = pastas[-1]
    slides = ["/" + p.replace("\\", "/") for p in sorted(glob.glob(os.path.join(pasta, "slide_*.png")))]
    legenda = ""
    lp = os.path.join(pasta, "legenda.txt")
    if os.path.exists(lp):
        with open(lp, encoding="utf-8") as f:
            legenda = f.read()
    return {"slides": slides, "legenda": legenda} if slides else None


if __name__ == "__main__":
    out = run()
    print(out if not out.get("ok") else f"OK: {out['numeros']} | {out['titulos']}")
