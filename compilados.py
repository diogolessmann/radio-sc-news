# -*- coding: utf-8 -*-
"""📦 COMPILADOS — matérias NOSSAS feitas da colheita dos radares (20/ago/2026).

Diretiva do dono: "ir incluindo pesquisas na internet E MATERIAL NOSSO". Os radares
(vagas, eventos) pescam o dia inteiro; aqui a Rádio junta a colheita e publica a
MATÉRIA PRÓPRIA que nenhum concorrente tem:

- 💼 VAGAS DA SEMANA (segunda 08h30): tudo que os radares de emprego acharam nos
  últimos 7 dias, compilado numa matéria única por cidade. (WEG vagas = 5.060 views.)
- 🎉 AGENDA DO FIM DE SEMANA (quinta 16h30): festas/eventos achados pros próximos dias.
  (Festival no Baile do MOA = 16,9 MIL views — o recorde do perfil.)

Link sintético own://compilado/... (news.link é UNIQUE — idempotência pelo banco).
A matéria entra na esteira normal: card automático, curador decide a hora.
"""
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


def _colhe(conn, fontes_like, dias, termos_extra=None):
    """Itens recentes das fontes-radar (title_own/title + cidade), sem repetição de fato."""
    q = ("SELECT id, title, title_own, city, source FROM news "
         "WHERE created_at > datetime('now', ?) AND (" +
         " OR ".join("source LIKE ?" for _ in fontes_like) + ") ORDER BY created_at DESC")
    rows = conn.execute(q, (f"-{dias} days", *fontes_like)).fetchall()
    itens, vistos = [], set()
    for r in rows:
        t = (r["title_own"] or r["title"] or "").strip()
        chave = re.sub(r"\W+", "", t.lower())[:60]
        if not t or chave in vistos:
            continue
        if termos_extra and not re.search(termos_extra, t, re.I):
            continue
        vistos.add(chave)
        itens.append({"titulo": t, "cidade": r["city"] or ""})
    return itens


def _publica_compilado(conn, titulo, corpo, cidade, categoria, chave_link):
    """Insere a matéria NOSSA na esteira (idempotente pelo link sintético)."""
    link = f"own://compilado/{chave_link}/{datetime.now().strftime('%Y%m%d')}"
    if conn.execute("SELECT id FROM news WHERE link=?", (link,)).fetchone():
        logger.info(f"📦 compilado {chave_link} já existe hoje — pulo")
        return None
    cur = conn.execute(
        "INSERT INTO news (title, summary, title_own, resumo_own, link, source, city, "
        "category, published_at, priority, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (titulo[:500], corpo[:2000], titulo[:500], corpo[:2000], link,
         "Rádio SC News", cidade, categoria, datetime.now().isoformat(), 1,
         datetime.now().isoformat()))
    conn.commit()
    logger.info(f"📦 compilado publicado: {titulo[:60]} (id {cur.lastrowid})")
    return cur.lastrowid


def _redige(pauta, instrucao):
    """Matéria própria via cérebro, com fallback de lista simples."""
    try:
        import cerebro
        txt = cerebro.completar(instrucao + "\n\nITENS COLETADOS:\n" + pauta)
        if txt:
            import distribuidor as dist
            if not dist._fala_de_ia(txt):
                return txt.strip()[:1900]
    except Exception as e:
        logger.warning(f"📦 cérebro indisponível ({e}) — lista simples")
    return None


def vagas_da_semana():
    """💼 Segunda de manhã: o compilado de vagas que o povo compartilha."""
    import distribuidor as dist
    conn = dist.get_db()
    itens = _colhe(conn, ["Radar Vagas%", "Radar WEG%", "Radar %"], 7,
                   termos_extra=r"vagas?|emprego|contrata|seletivo|recrutam|mutir[ãa]o")
    if len(itens) < 2:
        logger.info("📦 vagas: colheita magra, sem compilado")
        conn.close()
        return 0
    pauta = "\n".join(f"- {i['titulo']} ({i['cidade']})" for i in itens[:12])
    corpo = _redige(pauta, (
        "Você é editor da Rádio SC News. Escreva a matéria 'VAGAS DA SEMANA no Norte de SC' "
        "em português do Brasil: 1 linha de abertura animada (semana começando com porta "
        "aberta), depois um item POR LINHA no formato 'Cidade: resumo curtíssimo da vaga/"
        "oportunidade'. Só use os itens fornecidos, NÃO invente números nem empresas. "
        "Feche com: 'Guarda este post e manda pra quem está procurando.' Máximo 12 linhas. "
        "Responda SÓ a matéria."))
    if not corpo:
        corpo = ("Semana começando com porta aberta no Vale! Olha as oportunidades que "
                 "mapeamos:\n" + pauta + "\nGuarda este post e manda pra quem está procurando.")
    nid = _publica_compilado(conn, "💼 Vagas da semana: as oportunidades abertas no Norte de SC",
                             corpo, "Jaraguá do Sul", "economia", "vagas")
    conn.close()
    return 1 if nid else 0


def agenda_fim_de_semana():
    """🎉 Quinta à tarde: o que tem de festa/evento vindo aí (o filão dos 16,9 mil)."""
    import distribuidor as dist
    conn = dist.get_db()
    itens = _colhe(conn, ["Radar Eventos%", "Radar %"], 10,
                   termos_extra=r"festa|festival|show|feira|baile|inaugura|edi[çc][ãa]o|encontro|rodeio|osterfest|festival")
    if len(itens) < 2:
        logger.info("📦 agenda: colheita magra, sem compilado")
        conn.close()
        return 0
    pauta = "\n".join(f"- {i['titulo']} ({i['cidade']})" for i in itens[:10])
    corpo = _redige(pauta, (
        "Você é editor da Rádio SC News. Escreva 'AGENDA DO FIM DE SEMANA no Norte de SC' "
        "em português do Brasil: 1 linha de abertura convidativa, depois um item POR LINHA "
        "no formato 'Cidade: evento — dia (se o item disser)'. Só use os itens fornecidos, "
        "NÃO invente datas nem horários; se o item não diz o dia, não diga. PROIBIDO "
        "'hoje/amanhã'. Feche com: 'Marca quem vai contigo!'. Máximo 10 linhas. "
        "Responda SÓ a matéria."))
    if not corpo:
        corpo = ("O fim de semana no Vale vem cheio! Olha o que está rolando:\n" + pauta +
                 "\nMarca quem vai contigo!")
    nid = _publica_compilado(conn, "🎉 Agenda do fim de semana: o que tem de bom no Vale",
                             corpo, "Jaraguá do Sul", "cultura", "agenda-fds")
    conn.close()
    return 1 if nid else 0
