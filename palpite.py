# -*- coding: utf-8 -*-
"""
palpite.py — "O PALPITE DO VALE" (gamificação / moeda social).
O loop do "EU FALEI": a galera crava o palpite (A ou B), volta pra ver se acertou, e os
VENCEDORES se gabam = 2 posts por palpite (vota + revela) + retorno + zoeira. Conteúdo de
hábito que vicia. Reusa gen_instagram + distribuidor (publish_single).
"""
import os
from datetime import datetime

from PIL import Image, ImageDraw

import gen_instagram as gi
import distribuidor as dist


def slide_palpite(time_a, time_b, evento, outdir):
    """Card 'QUEM LEVA?' (A vs B) — formato VS vertical, nomes de qualquer tamanho cabem."""
    W, H = gi.W, gi.H
    canvas = Image.new("RGB", (W, H), gi.BG)
    d = ImageDraw.Draw(canvas)
    gi.brand_header(d)

    # selo dourado
    selo = "PALPITE DO VALE"
    fs = gi.font(38)
    sw = d.textlength(selo, font=fs)
    d.rounded_rectangle([(W - sw) // 2 - 28, 200, (W + sw) // 2 + 28, 268], radius=28, fill=gi.GOLD)
    d.text(((W - sw) // 2, 210), selo, font=fs, fill=gi.BLACK)

    # QUEM LEVA?
    fq = gi.font(92, impact=True)
    q = "QUEM LEVA?"
    qw = d.textlength(q, font=fq)
    d.text(((W - qw) // 2, 320), q, font=fq, fill=gi.WHITE, stroke_width=3, stroke_fill=gi.BLACK)
    if evento:
        fe = gi.font(38)
        ew = d.textlength(evento.upper(), font=fe)
        d.text(((W - ew) // 2, 432), evento.upper(), font=fe, fill=gi.MUTED)

    # bloco VS vertical: A / TIME_A / X / B / TIME_B
    def _opcao(letra, nome, y, cor_letra):
        fl = gi.font(56, impact=True)
        lw = d.textlength(letra, font=fl)
        d.rounded_rectangle([(W - lw) // 2 - 26, y, (W + lw) // 2 + 26, y + 78], radius=18, fill=cor_letra)
        d.text(((W - lw) // 2, y + 6), letra, font=fl, fill=gi.BLACK)
        fn = gi.font(64, impact=True)
        yy = y + 96
        for ln in gi.wrap(d, nome.upper(), fn, W - 140):
            nw = d.textlength(ln, font=fn)
            d.text(((W - nw) // 2, yy), ln, font=fn, fill=gi.WHITE, stroke_width=2, stroke_fill=gi.BLACK)
            yy += int(fn.size * 1.02)
        return yy

    y = 560
    y = _opcao("A", time_a, y, gi.GOLD) + 14
    fx = gi.font(50, impact=True)
    xw = d.textlength("X", font=fx)
    d.text(((W - xw) // 2, y), "X", font=fx, fill=gi.RED)
    y += 80
    y = _opcao("B", time_b, y, gi.WHITE)

    # gancho de gamificação
    hall = "QUEM ACERTAR ENTRA NO HALL DA FAMA"
    fh = gi.font(34)
    hw = d.textlength(hall, font=fh)
    d.rounded_rectangle([(W - hw) // 2 - 24, H - 200, (W + hw) // 2 + 24, H - 138], radius=20, fill=gi.RED)
    d.text(((W - hw) // 2, H - 192), hall, font=fh, fill=gi.WHITE)
    vota = "VOTA A OU B NOS COMENTARIOS"
    fv = gi.font(36, impact=True)
    vw = d.textlength(vota, font=fv)
    d.text(((W - vw) // 2, H - 116), vota, font=fv, fill=gi.GOLD)

    gi.footer_site(d)
    path = os.path.join(outdir, "palpite.png")
    canvas.save(path, quality=95)
    return path


def caption(time_a, time_b, evento):
    return (
        f"🏆 PALPITE DO VALE — {evento}!\n\n"
        f"E aí, QUEM LEVA? Crava o teu palpite 👇\n"
        f"🅰️ {time_a}\n"
        f"🅱️ {time_b}\n\n"
        f"Comenta A ou B — quem ACERTAR a gente lembra, entra no Hall da Fama do Vale 😎\n"
        f"🔁 Marca aquele amigo que SEMPRE erra o palpite kkk\n\n"
        f"➕ Segue @radiosc.news pra ver o resultado depois!\n\n"
        f"#palpite #futebol #vale #valedoitapocu #nortedesc #radioscnews"
    )


def run(time_a, time_b, evento, post=False):
    day = datetime.now().strftime("%Y-%m-%d")
    outdir = os.path.join("instagram_posts", day + "_palpite")
    os.makedirs(outdir, exist_ok=True)
    img = slide_palpite(time_a, time_b, evento, outdir)
    cap = caption(time_a, time_b, evento)
    with open(os.path.join(outdir, "legenda.txt"), "w", encoding="utf-8") as f:
        f.write(cap)
    if post:
        dist.publish_single("palpite", img, cap)
    return {"img": img, "outdir": outdir, "postado": bool(post)}


# ---------------------------------------------------------------- REVELA (resultado) + AUTO
def slide_revela(time_a, time_b, res, outdir):
    """Card do RESULTADO: placar + quem acertou (Hall da Fama)."""
    W, H = gi.W, gi.H
    canvas = Image.new("RGB", (W, H), gi.BG)
    d = ImageDraw.Draw(canvas)
    gi.brand_header(d)
    ga, gb, venc = res["gols_a"], res["gols_b"], res["vencedor"]

    selo = "DEU O JOGO!"
    fs = gi.font(40)
    sw = d.textlength(selo, font=fs)
    d.rounded_rectangle([(W - sw) // 2 - 28, 210, (W + sw) // 2 + 28, 278], radius=28, fill=gi.GOLD)
    d.text(((W - sw) // 2, 220), selo, font=fs, fill=gi.BLACK)

    # TIME A (dourado se venceu) / PLACAR / TIME B
    fn = gi.font(56, impact=True)
    for nome, cor, y in ((time_a.upper(), gi.GOLD if venc == "A" else gi.MUTED, 360),
                         (time_b.upper(), gi.GOLD if venc == "B" else gi.MUTED, 760)):
        for ln in gi.wrap(d, nome, fn, W - 140):
            w = d.textlength(ln, font=fn)
            d.text(((W - w) // 2, y), ln, font=fn, fill=cor)
            y += int(fn.size * 1.02)
    fnum = gi.font(150, impact=True)
    placar = f"{ga} x {gb}"
    pw = d.textlength(placar, font=fnum)
    d.text(((W - pw) // 2, 480), placar, font=fnum, fill=gi.WHITE, stroke_width=3, stroke_fill=gi.BLACK)

    msg = "DEU EMPATE!" if venc == "EMPATE" else f"QUEM VOTOU {'A' if venc == 'A' else 'B'} ACERTOU"
    fm = gi.font(46)
    mw = d.textlength(msg, font=fm)
    d.rounded_rectangle([(W - mw) // 2 - 34, 940, (W + mw) // 2 + 34, 1022], radius=22, fill=gi.RED)
    d.text(((W - mw) // 2, 952), msg, font=fm, fill=gi.WHITE)
    call = "JOGA O PRINT, CAMPEOES DO VALE"
    fc = gi.font(34)
    cw = d.textlength(call, font=fc)
    d.text(((W - cw) // 2, 1050), call, font=fc, fill=gi.GOLD)
    gi.footer_site(d)
    path = os.path.join(outdir, "revela.png")
    canvas.save(path, quality=95)
    return path


def revela_caption(time_a, time_b, res):
    ga, gb, venc = res["gols_a"], res["gols_b"], res["vencedor"]
    linhas = ["🏆 PALPITE DO VALE — deu o resultado:", ""]
    if venc == "EMPATE":
        linhas += [f"🤝 {time_a} {ga} x {gb} {time_b} — DEU EMPATE!", "",
                   "Quem cravou empate é vidente! 😏"]
    else:
        venc_nome = (time_a if venc == "A" else time_b).upper()
        letra = "A" if venc == "A" else "B"
        linhas += [f"🏆 {venc_nome}! ({time_a} {ga} x {gb} {time_b})", "",
                   f"Quem votou {letra} ACERTOU! 😎 Joga o print aqui que entra no Hall da Fama do Vale 🏅"]
    linhas += ["", "🔁 Marca o amigo que errou feio kkk", "➕ Segue @radiosc.news", "",
               "#palpite #copadomundo #futebol #vale #valedoitapocu #radioscnews"]
    return "\n".join(linhas)


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS palpites_jogos (
        match_id INTEGER PRIMARY KEY, time_a TEXT, time_b TEXT, data TEXT,
        posted_vota TEXT, posted_revela TEXT)""")
    conn.commit()


def run_auto(post=False):
    """Motor do Palpite: posta o VOTA do jogo do dia e a REVELA quando o jogo ACABA (FINISHED).
    Tudo do fato livre (API oficial). Pula sozinho se não há jogo / sem chave."""
    import sqlite3
    import futebol
    conn = sqlite3.connect(dist.DB_PATH)
    conn.row_factory = sqlite3.Row
    _ensure_table(conn)
    feito = {"vota": None, "revela": None}

    # 1) VOTA — jogo de destaque de hoje, se ainda não votado
    jogo = futebol.jogo_destaque()
    if jogo and jogo.get("id"):
        if not conn.execute("SELECT 1 FROM palpites_jogos WHERE match_id=?", (jogo["id"],)).fetchone():
            ev = f"Copa do Mundo · hoje {jogo['hora']}".strip().rstrip("·").strip()
            run(jogo["time_a"], jogo["time_b"], ev, post=post)
            conn.execute("INSERT INTO palpites_jogos(match_id,time_a,time_b,data,posted_vota) "
                         "VALUES (?,?,?,?,?)",
                         (jogo["id"], jogo["time_a"], jogo["time_b"],
                          datetime.now().strftime("%Y-%m-%d"),
                          datetime.now().isoformat(timespec="seconds") if post else "preview"))
            conn.commit()
            feito["vota"] = f"{jogo['time_a']} x {jogo['time_b']}"

    # 2) REVELA — jogos votados, sem revela, já FINISHED
    pend = conn.execute("SELECT * FROM palpites_jogos WHERE posted_vota IS NOT NULL "
                        "AND posted_revela IS NULL").fetchall()
    for r in pend:
        res = futebol.resultado(r["match_id"])
        if not res:
            continue                      # ⏳ ainda não acabou
        day = datetime.now().strftime("%Y-%m-%d")
        outdir = os.path.join("instagram_posts", day + "_palpite_revela")
        os.makedirs(outdir, exist_ok=True)
        img = slide_revela(r["time_a"], r["time_b"], res, outdir)
        cap = revela_caption(r["time_a"], r["time_b"], res)
        if post:
            dist.publish_single(f"revela_{r['match_id']}", img, cap)
        conn.execute("UPDATE palpites_jogos SET posted_revela=? WHERE match_id=?",
                     (datetime.now().isoformat(timespec="seconds") if post else "preview", r["match_id"]))
        conn.commit()
        feito["revela"] = f"{r['time_a']} {res['gols_a']}x{res['gols_b']} {r['time_b']}"

    conn.close()
    return feito


if __name__ == "__main__":
    print(run_auto(post=False))
