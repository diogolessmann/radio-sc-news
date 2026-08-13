# -*- coding: utf-8 -*-
"""🏛️ FONTES OFICIAIS — notícia de prefeitura direto da fonte (12/ago/2026, carta branca do dono).

Por que vale ouro: ato oficial não tem direito autoral (Lei 9.610, Art. 8º, IV) e o conteúdo
é SERVIÇO que os portais da região demoram a dar — interdição, obra, vacina, prazo, sistema
fora do ar. É a Rádio deixando de ser repetidora: notícia que ainda não virou notícia.

O extrator entrega só TÍTULO + LINK: o save_articles do scraper faz o resto (og:image,
corpo da matéria via fetch_article_text, reescrita no nosso tom, dedup por link e por gêmea).
O redator downstream transforma release chato em impacto no leitor ("Rua X FECHA segunda").

Estado do serralheiro (sondagem de 12/ago, porta por porta):
- Joinville   ✅ lista HTML aberta (WordPress tema pyli; REST 403; /feed 410)
- Jaraguá     ⏳ vitrine Next.js sobre WordPress — timeout de fora (90s); TODO tentar do Railway
- Schroeder   🔒 403 até com UA de navegador (WAF)
- Guaramirim  🔒 RSS existe (.sc.leg.br/rss) mas atrás de captcha (lsrecaptcha)
- Corupá      🔒 www.corupa.sc.gov.br nem resolveu DNS
Câmaras (.sc.leg.br): a de Jaraguá já é fonte RSS normal do scraper.
"""
import logging
import re

import requests

logger = logging.getLogger(__name__)
_UA = {"User-Agent": "Mozilla/5.0 (compatible; RadioSCBot/1.0)"}

# 🥇 SÓ SERVIÇO ENTRA: o que muda a vida do leitor essa semana. Release institucional
# (comitiva/assinatura/homenagem) fica na vitrine da prefeitura — não é notícia nossa.
_UTILIDADE = re.compile(
    r"\bobras?\b|interdi|tr[âa]nsito|desvio|\brua\b|avenida|ponte|viaduto|duplica[çc]|"
    r"vagas?\b|emprego|concurso|processo seletivo|matr[íi]cula|inscri[çc]|edital|"
    r"vacina|sa[úu]de|dengue|mutir[ãa]o|hospital|\bUPA\b|posto de|"
    r"[áa]gua|energia|\bluz\b|apag[ãa]o|indispon[íi]v|fora do ar|sistema|"
    r"IPTU|imposto|tribut|prazo|desconto|gratuit|"
    r"evento|festival|festa|parque|pra[çc]a|escola|creche|\bCEI\b|estudant|"
    r"[ôo]nibus|tarifa|transporte|coleta|\blixo\b|feira|plant[ãa]o|farm[áa]cia|"
    r"chuva|alerta|defesa civil|abrigo|campanha|castra[çc]|ades[ãa]o|benef[íi]cio|"
    r"hor[áa]rio|funcionamento|atendimento|melhor (?:escola|cidade)|IDEB",
    re.IGNORECASE)


def _joinville():
    """Lista de notícias da Prefeitura de Joinville (HTML aberto, âncoras limpas)."""
    r = requests.get("https://www.joinville.sc.gov.br/noticias/", headers=_UA, timeout=20)
    r.raise_for_status()
    arts, vistos = [], set()
    for href, inner in re.findall(
            r'<a[^>]+href="(https://www\.joinville\.sc\.gov\.br/noticias/[^"]+/)"[^>]*>(.*?)</a>',
            r.text, re.S):
        titulo = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", inner)).strip()
        if href in vistos or len(titulo) < 25:      # âncora de imagem/vazia: pula
            continue
        vistos.add(href)
        arts.append({"title": titulo[:500], "link": href})
    return arts


FONTES = [
    {"nome": "Prefeitura de Joinville", "city": "Joinville", "extrator": _joinville, "max": 6},
    # TODO Jaraguá (Next.js/WP — testar do Railway), Schroeder/Guaramirim/Corupá (muradas por ora)
]


def coletar():
    """Artigos no formato do scraper. category=None de propósito: o collect_all preenche
    com detect_category (evita import circular — scraper importa este módulo)."""
    out = []
    for f in FONTES:
        try:
            arts = f["extrator"]()
        except Exception as e:
            logger.warning(f"🏛️ {f['nome']} falhou: {e}")
            continue
        uteis = [a for a in arts if _UTILIDADE.search(a["title"])]
        for a in uteis[: f.get("max", 6)]:
            out.append({
                "title": a["title"],
                "summary": a.get("summary", ""),   # <180 chars -> save_articles puxa o corpo
                "link": a["link"],
                "source": f["nome"],
                "city": f["city"],
                "category": None,
                "published_at": None,
                "image_url": None,
                "priority": True,
            })
        logger.info(f"🏛️ {f['nome']}: {len(arts)} na vitrine, {len(uteis)} de serviço")
    return out


if __name__ == "__main__":
    for a in coletar():
        print(f"[{a['city']}] {a['title'][:90]}")
