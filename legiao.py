# -*- coding: utf-8 -*-
"""💬 LEGIÃO DO PAINEL — o posto avançado (18/ago/2026, pedido "OUSADO" do dono).

A aba "Falar com Legião" do admin: quem estiver no painel (Diogo, Thais) conversa ao
vivo com a Legião do site — o cérebro de IA da casa (cerebro.completar) vestindo a
persona, com o ESTADO REAL da operação injetado a cada mensagem (fila, placar do dia,
agenda, midiateca). Responde na hora, orienta os botões do painel e, quando o pedido
passa da alçada dela, grava RECADO pro Legião-mestre (o Claude Code do Diogo), que lê
a fila nas sessões e nas rondas cloud.

REGRA DE SEGURANÇA (inegociável): o posto avançado NÃO tem mãos — não publica, não
apaga, não mexe em arquivo, não toca em token, não alcança o PC de ninguém. Ele SABE
e ORIENTA; quem age é o humano nos botões do painel, ou o mestre via recado.
"""
import json
import os
from datetime import datetime

_DATA = os.environ.get("DATA_DIR", ".")
_HIST_PATH = os.path.join(_DATA, "legiao_chat.json")
_RECADOS_PATH = os.path.join(_DATA, "legiao_recados.json")

_MAX_HIST = 30          # pares guardados
_CTX_TURNOS = 8         # quantas falas recentes entram no prompt


# ------------------------------------------------------------------ memória do chat
def _carrega(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _salva(path, dado):
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(dado, f, ensure_ascii=False, indent=1)
    except Exception as e:
        print(f"   ! legiao não salvou {path}: {e}")


def historico():
    return _carrega(_HIST_PATH, [])


def recados(pendentes=True):
    r = _carrega(_RECADOS_PATH, [])
    return [x for x in r if not x.get("feito")] if pendentes else r


def deixar_recado(texto, autor="painel"):
    r = _carrega(_RECADOS_PATH, [])
    r.insert(0, {"quando": datetime.now().strftime("%d/%m %H:%M"),
                 "autor": autor, "texto": texto[:1200], "feito": False})
    _salva(_RECADOS_PATH, r[:60])
    return True


def marcar_recado_feito(indice):
    r = _carrega(_RECADOS_PATH, [])
    if 0 <= indice < len(r):
        r[indice]["feito"] = True
        _salva(_RECADOS_PATH, r)
    return True


# ------------------------------------------------------------------ estado da operação
def _estado_operacao():
    """Snapshot honesto do motor pra Legião responder com fato, não com achismo."""
    linhas = []
    try:
        import distribuidor as dist
        conn = dist.get_db()
        fila = conn.execute(
            "SELECT COUNT(*) FROM news WHERE social_hold != '' AND social_hold IS NOT NULL "
            "AND social_hold NOT LIKE 'descartada%' AND social_posted_at IS NULL").fetchone()[0]
        hoje = conn.execute(
            "SELECT COUNT(*) FROM news WHERE social_posted_at >= datetime('now','-24 hours')").fetchone()[0]
        ult = conn.execute(
            "SELECT title, city FROM news WHERE social_posted_at IS NOT NULL "
            "ORDER BY social_posted_at DESC LIMIT 3").fetchall()
        conn.close()
        linhas.append(f"- Fila de revisão: {fila} matérias esperando aprovação")
        linhas.append(f"- Posts nas últimas 24h: {hoje}")
        for u in ult:
            linhas.append(f"- Último post: {u['title'][:70]} ({u['city']})")
    except Exception as e:
        linhas.append(f"- (banco indisponível agora: {e})")
    try:
        import midiateca as mt
        itens = mt.listar("dlmob")
        v = sum(1 for i in itens if i["tipo"] == "video")
        linhas.append(f"- Midiateca DL: {len(itens)} itens ({v} vídeos, {len(itens)-v} fotos)")
    except Exception:
        pass
    try:
        import genericbg as gb
        linhas.append(f"- Arsenal de fundos: {len(gb.listar_arsenal())} imagens")
    except Exception:
        pass
    linhas.append(f"- Recados pendentes pro Legião-mestre: {len(recados())}")
    return "\n".join(linhas)


# ------------------------------------------------------------------ a conversa
_PERSONA = (
    "Você é a LEGIÃO DO PAINEL — o posto avançado da Legião na Rádio SC News e no Grupo "
    "Lessmann (Schroeder/SC). Fala português do Brasil, direto, caloroso e afiado, como "
    "um sócio de confiança. Quem conversa contigo está DENTRO do painel admin (Diogo, o "
    "dono, ou a Thais, da equipe).\n\n"
    "O QUE VOCÊ SABE: o estado da operação vem em ESTADO AGORA (fato, use-o). A operação: "
    "Rádio SC News (jornal hiperlocal das 5 cidades: Schroeder, Jaraguá do Sul, Guaramirim, "
    "Corupá, Joinville — clima é a editoria nº 1, policial sai em modo teaser 'detalhes no "
    "site'), Despachante Lessmann (documentos: SÓ Schroeder; defesa de multa: Brasil todo) "
    "e DL Mobilidade (scooters elétricas NXT, até 48x ViaCredi, parcelas a partir de "
    "R$ 200*, WhatsApp da loja 47 99776-6831 — NUNCA fale 'boleto').\n\n"
    "ONDE FICA CADA COISA NO PAINEL: aprovar matérias = Fila de Revisão (/revisar). "
    "Fotos e vídeos da marca + legendas prontas = Midiateca (/admin/midiateca). Fundos "
    "dos cards = Arsenal (/admin/arsenal). Agenda da marca DL = /admin/despachante.\n\n"
    "O QUE VOCÊ NÃO FAZ (regra de ferro): você NÃO publica, NÃO apaga, NÃO edita arquivo, "
    "NÃO mexe em token/senha, NÃO acessa computador de ninguém. Quando pedirem algo assim, "
    "explique EM QUAL botão do painel a pessoa mesma faz — ou ofereça deixar RECADO pro "
    "Legião-mestre (o Claude do Diogo), que executa depois. Pra deixar recado, diga à "
    "pessoa para usar o botão 'Deixar recado' abaixo do chat.\n\n"
    "Estilo: respostas curtas (2-6 frases), sem enrolação, um emoji quando couber. "
    "Se não souber, diga que não sabe. NUNCA invente número que não está no ESTADO AGORA."
)


def responder(mensagem, autor="painel"):
    """Uma rodada de conversa. Injeta persona + estado + histórico recente no cérebro."""
    import cerebro
    import distribuidor as dist

    hist = historico()
    contexto = "\n".join(
        f"{'PESSOA' if h['quem'] == 'pessoa' else 'LEGIÃO'}: {h['txt']}"
        for h in hist[-_CTX_TURNOS:])
    prompt = (
        _PERSONA + "\n\n"
        "=== ESTADO AGORA (" + datetime.now().strftime("%d/%m %H:%M") + ") ===\n"
        + _estado_operacao() + "\n\n"
        + ("=== CONVERSA ATÉ AQUI ===\n" + contexto + "\n\n" if contexto else "")
        + f"PESSOA ({autor}): {mensagem}\n\n"
        "Responda como LEGIÃO (só a resposta, sem prefixo):"
    )
    txt = None
    try:
        txt = (cerebro.completar(prompt) or "").strip()
        if txt and dist._fala_de_ia(txt):
            txt = None
    except Exception as e:
        print(f"   ! legiao: cérebro indisponível ({e})")
    if not txt:
        txt = ("Tô sem cérebro de IA neste segundo (cai já volto). Enquanto isso: fila e "
               "aprovações ficam em /revisar, mídia da marca na Midiateca. Se for urgente, "
               "deixa recado pro Legião-mestre no botão aqui embaixo. 🧡")

    hist.append({"quem": "pessoa", "txt": mensagem[:800], "autor": autor,
                 "quando": datetime.now().strftime("%d/%m %H:%M")})
    hist.append({"quem": "legiao", "txt": txt[:1500],
                 "quando": datetime.now().strftime("%d/%m %H:%M")})
    _salva(_HIST_PATH, hist[-_MAX_HIST * 2:])
    return txt
