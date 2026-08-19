"""
scraper.py — Coleta automática de notícias via RSS
Rádio SC News
"""
import feedparser
import json
import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
from datetime import datetime
import sqlite3
import logging
import re
import os
import unicodedata
import warnings

# Alguns portais servem HTML com declaração <?xml ...?> no topo -> bs4 avisa. Silencia o ruído.
try:
    from bs4 import XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
except Exception:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = os.environ.get('DB_PATH', 'radio_sc.db')


# 🏭 DICIONÁRIO DE EMPRESAS DA REGIÃO (18/ago — leva 3, "tem MUITAS"): menção a qualquer
# uma destas em QUALQUER feed promove a matéria (passe-livre da regra master + cidade da
# empresa + prioridade). Escala pra centenas sem custo de coleta — pra adicionar, é uma
# linha: "Nome": "Cidade". Radar individual fica só pros gigantes que geram pauta sozinhos.
EMPRESAS_REGIAO = {
    # Schroeder
    "Metal Nox": "Schroeder", "Real Vidro": "Schroeder", "Castertech": "Schroeder",
    "FAMAC": "Schroeder",
    # Guaramirim
    "Falbran": "Guaramirim", "Modely": "Guaramirim", "Nanete": "Guaramirim",
    "IMB Behrendt": "Guaramirim", "WEG Tintas": "Guaramirim",
    # Jaraguá do Sul
    "Chocoleite": "Jaraguá do Sul", "Argi ": "Jaraguá do Sul",
    "Caraguá Veículos": "Jaraguá do Sul",
    # Joinville
    "Docol": "Joinville", "Buschle": "Joinville", "Whirlpool": "Joinville",
    "Amanco": "Joinville",
}

RSS_FEEDS = [
    # ── 🛰️ RADAR GOOGLE NEWS por cidade (11/ago — PROJETO HIPERLOCAL): pega QUALQUER
    #    veículo que citar as 5 cidades, inclusive os que não temos no radar. É o
    #    multiplicador de coleta local que a REGRA MASTER exige (cidade = 3-10 mil views).
    {'url': 'https://news.google.com/rss/search?q=%22Jaragu%C3%A1+do+Sul%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Jaraguá do Sul', 'city': 'Jaraguá do Sul', 'category': 'geral', 'priority': True},
    {'url': 'https://news.google.com/rss/search?q=%22Schroeder%22+SC&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Schroeder', 'city': 'Schroeder', 'category': 'geral', 'priority': True},
    {'url': 'https://news.google.com/rss/search?q=%22Guaramirim%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Guaramirim', 'city': 'Guaramirim', 'category': 'geral', 'priority': True},
    {'url': 'https://news.google.com/rss/search?q=%22Corup%C3%A1%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Corupá', 'city': 'Corupá', 'category': 'geral', 'priority': True},
    {'url': 'https://news.google.com/rss/search?q=%22Joinville%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Joinville', 'city': 'Joinville', 'category': 'geral', 'priority': False},
    # 🚧 RADAR BR-280 (13/ago) — a novela diária do Vale: obra, interdição, acidente, fila.
    #    A rodovia corta Corupá-Jaraguá-Guaramirim; regra master deixa passar só o trecho nosso.
    {'url': 'https://news.google.com/rss/search?q=%22BR-280%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar BR-280', 'city': None, 'category': 'geral', 'priority': True},
    # 🚨 RADAR POLICIAL/BOMBEIROS por cidade (13/ago, aprovado: alimentar o teaser) — ocorrência
    #    que qualquer blog cobrir, a gente fica sabendo. Categoria fixa: policial (modo teaser).
    {'url': 'https://news.google.com/rss/search?q=pol%C3%ADcia+%22Jaragu%C3%A1+do+Sul%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Policial Jaraguá', 'city': 'Jaraguá do Sul', 'category': 'policial', 'priority': True,
     'max_entries': 8},
    {'url': 'https://news.google.com/rss/search?q=bombeiros+%22Jaragu%C3%A1+do+Sul%22+OR+%22Guaramirim%22+OR+%22Schroeder%22+OR+%22Corup%C3%A1%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Bombeiros Vale', 'city': None, 'category': 'policial', 'priority': True,
     'max_entries': 8},
    # ── 🏭 TURBO EMPRESAS (18/ago, pedido do dono): tudo que a internet falar dos GIGANTES
    #    da região vira matéria NOSSA (orgulho local = ibope comprovado: Lunelli 930, Antidio
    #    4mi). bypass_master: empresa daqui É notícia daqui, mesmo sem cidade no texto. ──
    {'url': 'https://news.google.com/rss/search?q=%22WEG%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar WEG', 'city': 'Jaraguá do Sul', 'category': 'economia',
     'priority': True, 'max_entries': 4, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Malwee%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Malwee', 'city': 'Jaraguá do Sul', 'category': 'economia',
     'priority': True, 'max_entries': 4, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Duas+Rodas%22+ingredientes&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Duas Rodas', 'city': 'Jaraguá do Sul', 'category': 'economia',
     'priority': True, 'max_entries': 4, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Lunelli%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Lunelli', 'city': 'Guaramirim', 'category': 'economia',
     'priority': True, 'max_entries': 4, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Live%21%22+moda+fitness&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Live!', 'city': 'Jaraguá do Sul', 'category': 'economia',
     'priority': True, 'max_entries': 4, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Elian%22+moda&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Elian', 'city': 'Massaranduba', 'category': 'economia',
     'priority': True, 'max_entries': 4, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Grupo+Mime%22+OR+%22Postos+Mime%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Mime', 'city': 'Joinville', 'category': 'economia',
     'priority': True, 'max_entries': 4, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Agricopel%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Agricopel', 'city': 'Guaramirim', 'category': 'economia',
     'priority': True, 'max_entries': 4, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Menegotti%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Menegotti', 'city': 'Schroeder', 'category': 'economia',
     'priority': True, 'max_entries': 4, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Marisol%22+moda&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Marisol', 'city': 'Jaraguá do Sul', 'category': 'economia',
     'priority': True, 'max_entries': 4, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Urbano+Alimentos%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Urbano', 'city': 'Jaraguá do Sul', 'category': 'economia',
     'priority': True, 'max_entries': 4, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Zanotti%22+el%C3%A1sticos+OR+Jaragu%C3%A1&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Zanotti', 'city': 'Jaraguá do Sul', 'category': 'economia',
     'priority': True, 'max_entries': 4, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Bretzke%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Bretzke', 'city': 'Jaraguá do Sul', 'category': 'economia',
     'priority': True, 'max_entries': 4, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Tigre%22+tubos+OR+Joinville&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Tigre', 'city': 'Joinville', 'category': 'economia',
     'priority': True, 'max_entries': 4, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22D%C3%B6hler%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Döhler', 'city': 'Joinville', 'category': 'economia',
     'priority': True, 'max_entries': 4, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Schulz%22+Joinville&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Schulz', 'city': 'Joinville', 'category': 'economia',
     'priority': True, 'max_entries': 4, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Ciser%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Ciser', 'city': 'Joinville', 'category': 'economia',
     'priority': True, 'max_entries': 4, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Embraco%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Embraco', 'city': 'Joinville', 'category': 'economia',
     'priority': True, 'max_entries': 4, 'bypass_master': True},
    # ── 🏭 TURBO EMPRESAS leva 2 (18/ago — 'mapeia todas, tem muitas') ──
    {'url': 'https://news.google.com/rss/search?q=%22Tupy%22+fundi%C3%A7%C3%A3o+OR+Joinville&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Tupy', 'city': 'Joinville', 'category': 'economia',
     'priority': True, 'max_entries': 3, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Krona%22+tubos&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Krona', 'city': 'Joinville', 'category': 'economia',
     'priority': True, 'max_entries': 3, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Lepper%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Lepper', 'city': 'Joinville', 'category': 'economia',
     'priority': True, 'max_entries': 3, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Wetzel%22+Joinville&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Wetzel', 'city': 'Joinville', 'category': 'economia',
     'priority': True, 'max_entries': 3, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Neogrid%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Neogrid', 'city': 'Joinville', 'category': 'economia',
     'priority': True, 'max_entries': 3, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Mannes%22+colch%C3%B5es+OR+espumas&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Mannes', 'city': 'Guaramirim', 'category': 'economia',
     'priority': True, 'max_entries': 3, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Marcatto%22+chap%C3%A9us+OR+Jaragu%C3%A1&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Marcatto', 'city': 'Jaraguá do Sul', 'category': 'economia',
     'priority': True, 'max_entries': 3, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Metal%C3%BArgica+CSM%22+OR+%22CSM%22+Jaragu%C3%A1&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar CSM', 'city': 'Jaraguá do Sul', 'category': 'economia',
     'priority': True, 'max_entries': 3, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Formitz%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Formitz', 'city': 'Guaramirim', 'category': 'economia',
     'priority': True, 'max_entries': 3, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Eletropoll%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Eletropoll', 'city': 'Corupá', 'category': 'economia',
     'priority': True, 'max_entries': 3, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Frigor%C3%ADfico+Corup%C3%A1%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Frig. Corupá', 'city': 'Corupá', 'category': 'economia',
     'priority': True, 'max_entries': 3, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Dibrape%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Dibrape', 'city': 'Guaramirim', 'category': 'economia',
     'priority': True, 'max_entries': 3, 'bypass_master': True},
    # ── 🏭 LOTES do dicionário (1 busca cobre várias — sem estourar a coleta) ──
    {'url': 'https://news.google.com/rss/search?q=%22Metal+Nox%22+OR+%22Real+Vidro%22+OR+%22Castertech%22+OR+%22FAMAC%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Empresas Schroeder', 'city': 'Schroeder', 'category': 'economia',
     'priority': True, 'max_entries': 5, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Falbran%22+OR+%22Modely%22+OR+%22Nanete%22+OR+%22IMB+Behrendt%22&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Empresas Guaramirim', 'city': 'Guaramirim', 'category': 'economia',
     'priority': True, 'max_entries': 5, 'bypass_master': True},
    {'url': 'https://news.google.com/rss/search?q=%22Docol%22+OR+%22Buschle%22+OR+%28Whirlpool+Joinville%29&hl=pt-BR&gl=BR&ceid=BR:pt-419',
     'source': 'Radar Empresas Joinville 2', 'city': 'Joinville', 'category': 'economia',
     'priority': True, 'max_entries': 5, 'bypass_master': True},
    # ── Santa Catarina (geral) ──────────────────
    {
        'url': 'https://g1.globo.com/rss/g1/sc/',
        'source': 'G1 Santa Catarina',
        'city': None,          # Usa detecção por keyword — pode ser qualquer cidade de SC
        'category': 'geral',
        'priority': True
    },
    {
        'url': 'https://ndmais.com.br/feed/',
        'source': 'ND Mais',
        'city': None,          # Detecção automática de cidade
        'category': 'geral',
        'priority': False
    },
    # ── Norte de SC — Joinville ─────────────────
    {
        'url': 'https://ndmais.com.br/joinville/feed/',
        'source': 'ND Mais – Joinville',
        'city': 'Joinville',
        'category': 'geral',
        'priority': True
    },
    {
        'url': 'https://g1.globo.com/rss/g1/sc/norte-catarinense/',
        'source': 'G1 Norte Catarinense',
        'city': None,          # Norte de SC — keyword decide a cidade exata
        'category': 'geral',
        'priority': True
    },
    {
        'url': 'https://ocp.news/tag/joinville/feed/',
        'source': 'OCP News – Joinville',
        'city': 'Joinville',
        'category': 'geral',
        'priority': True
    },
    # ── Norte de SC — Jaraguá do Sul ────────────
    {
        'url': 'https://ndmais.com.br/tag/jaragua-do-sul/feed/',
        'source': 'ND Mais – Jaraguá do Sul',
        'city': 'Jaraguá do Sul',
        'category': 'geral',
        'priority': True
    },
    {
        'url': 'https://ocp.news/tag/jaragua-do-sul/feed/',
        'source': 'OCP News – Jaraguá do Sul',
        'city': 'Jaraguá do Sul',
        'category': 'geral',
        'priority': True
    },
    # ── Norte de SC — Jaraguá do Sul + Guaramirim (RBN 94.3 FM) ──
    {
        'url': 'https://portal.rbnfm.com.br/feed',
        'source': 'RBN 94.3 FM',
        'city': None,          # Cobre Jaraguá e Guaramirim — keyword detecta
        'category': 'geral',
        'priority': True,
        'max_entries': 15
    },
    # ── CHIP Stage 3 (04/jul/2026, garimpo por agentes — feeds testados vivos) ──
    {
        'url': 'https://fm105.com.br/feed/',
        'source': 'Rádio 105 FM',
        'city': None,          # sede em Guaramirim, cobre Jaraguá/Schroeder/Guaramirim — keyword
        'category': 'geral',   # RSS sem imagem -> og:image da página resolve (Fase 1)
        'priority': True
    },
    {
        'url': 'https://www.diariodajaragua.com.br/onde/jaragua-do-sul/feed/',
        'source': 'Diário da Jaraguá',
        'city': None,          # feed geral do site (tags não filtram de verdade) — keyword decide
        'category': 'geral',   # imagem via <enclosure>; pubDate fora do RFC822 -> parser cai no now()
        'priority': True
    },
    {
        'url': 'https://nossa.fm/feed/',
        'source': 'Nossa FM 99,9',
        'city': None,          # foco Jaraguá + pautas estaduais — keyword decide
        'category': 'geral',
        'priority': True
    },
    {
        'url': 'https://www.pensejornal.com.br/rss.xml',
        'source': 'Pense Jornal',
        'city': None,          # sediado em Jaraguá mas pauta estadual — keyword filtra o local
        'category': 'geral',
        'priority': False
    },
    # ── Norte de SC — Guaramirim ────────────────
    {
        'url': 'https://ocp.news/tag/guaramirim/feed/',
        'source': 'OCP News – Guaramirim',
        'city': 'Guaramirim',
        'category': 'geral',
        'priority': True
    },
    {
        'url': 'https://ndmais.com.br/tag/guaramirim/feed/',
        'source': 'ND Mais – Guaramirim',
        'city': 'Guaramirim',
        'category': 'geral',
        'priority': True
    },
    # ── Norte de SC — Schroeder, Guaramirim, Corupá (JDV) ──
    {
        'url': 'https://www.jdv.com.br/feed/',
        'source': 'JDV',
        'city': None,          # JDV cobre Schroeder/Guaramirim/Corupá — keyword detecta
        'category': 'geral',
        'priority': True
    },
    # ── Norte de SC — Schroeder (SchPost) ───────
    {
        'url': 'https://www.schpost.com.br/feed/',
        'source': 'Portal de Schroeder',
        'city': 'Schroeder',
        'category': 'local',
        'priority': True
    },
    {
        'url': 'https://ndmais.com.br/tag/schroeder/feed/',
        'source': 'ND Mais – Schroeder',
        'city': 'Schroeder',
        'category': 'geral',
        'priority': True
    },
    # ── Norte de SC — CORUPÁ (saiu do zero! CHIP Stage 3, 04/jul/2026) ──
    {
        'url': 'http://noticiascorupa.blogspot.com/feeds/posts/default?alt=rss',
        'source': 'Notícias Corupá',
        'city': 'Corupá',      # blog 100% dedicado, vivo, media:thumbnail em todos os itens
        'category': 'local',
        'priority': True
    },
    {
        'url': 'https://ndmais.com.br/tag/corupa/feed/',
        'source': 'ND Mais – Corupá',
        'city': 'Corupá',      # fluxo baixo (~2-4/mês) mas filtro real e com imagem
        'category': 'geral',
        'priority': True
    },
    # ── CHIP Stage 4 (04/jul/2026) — garimpo total do Vale (agentes + curl) ──
    # POLÍCIA: feeds de CATEGORIA segurança pré-filtrados (menos ruído que o feed geral).
    # O filtro editorial segura morte/sexual/menor; o resto (preso/apreensão/operação) posta.
    {
        'url': 'https://www.schpost.com.br/feed/seguranca',
        'source': 'Portal de Schroeder – Segurança',
        'city': None,          # alta concentração Schroeder/Guaramirim/Jaraguá — keyword decide
        'category': 'policial',
        'priority': True
    },
    {
        'url': 'https://www.diariodajaragua.com.br/seguranca/feed/',
        'source': 'Diário da Jaraguá – Segurança',
        'city': None,          # foco Jaraguá/Guaramirim, com imagem no RSS
        'category': 'policial',
        'priority': True
    },
    # OFICIAIS: as ÚNICAS 2 fontes de governo com RSS vivo (o resto é anti-robô/SPA).
    {
        'url': 'https://schroeder.sc.gov.br/feed/',
        'source': 'Prefeitura de Schroeder',
        'city': 'Schroeder',   # notícia oficial (obra, vacina, evento); 403 no 1º hit -> fallback pega
        'category': 'local',
        'priority': True
    },
    {
        'url': 'https://www.jaraguadosul.sc.leg.br/feed/',
        'source': 'Câmara de Jaraguá do Sul',
        'city': 'Jaraguá do Sul',   # sessões, projetos, vereadores — política local
        'category': 'local',
        'priority': True
    },
    # PORTAL novo de Joinville (o gap da maior cidade) — cobre a região, com imagem.
    {
        'url': 'https://joinvillenoticias.com.br/feed/rss/ultimas',
        'source': 'Joinville Notícias',
        'city': None,          # cobre Joinville + região (Guaramirim/Jaraguá aparecem) — keyword
        'category': 'geral',
        'priority': True
    },
    # ── Norte de SC — OCP News (regional) ───────
    {
        'url': 'https://ocp.news/feed/',
        'source': 'OCP News',
        'city': None,
        'category': 'geral',
        'priority': False
    },
    # ── ☔ CLIMA/METEOROLOGIA (28/jul — pedido do dono: fontes DEDICADAS pra mina de ouro;
    # Placar: clima nota 16.8, alcance médio 5.719 = 10× o local; os 3 maiores posts da
    # história são clima/alerta). Testados ao vivo: MetSul ~30 itens · Defesa Civil ~10.
    # O motor REESCREVE tudo (voz própria, Art. 46) e usa NOSSAS imagens — nunca as deles.
    {
        'url': 'https://metsul.com/feed/',
        'source': 'MetSul Meteorologia',
        'city': None,                 # detecção — Sul/SC genérico vira 'Santa Catarina'
        'category': 'clima',
        'priority': True,
        'max_entries': 6
    },
    {
        'url': 'https://www.defesacivil.sc.gov.br/feed/',
        'source': 'Defesa Civil SC',
        'city': None,
        'category': 'clima',
        'priority': True,
        'max_entries': 4    # alertas repetem por hora (17:29/16:57/16:53...) — o dedup segura o resto
    },
    # ── Futebol Nacional — DESLIGADO 28/jul (DIETA DO MOTOR, auditoria do Placar):
    # esporte = nota 1.4 (a PIOR) ocupando 29% da coleta (1.056 matérias/mês), cada uma
    # passando pela IA de reescrita (custo real) pra depois ser DESCARTADA na postagem
    # (ESPORTE_NACIONAL_OFF). Coletar + pagar + jogar fora = desperdício duplo.
    # Esporte LOCAL (futsal de Schroeder etc.) segue vindo dos feeds regionais acima.
    # Pra religar: descomentar os feeds abaixo.
    # {'url': 'https://ge.globo.com/rss/ge/futebol/', 'source': 'GE Futebol',
    #  'city': 'Brasil', 'category': 'esporte', 'priority': True, 'max_entries': 5},
    # {'url': 'https://ge.globo.com/rss/ge/brasileirao-serie-a/', 'source': 'GE Brasileirão',
    #  'city': 'Brasil', 'category': 'esporte', 'priority': True, 'max_entries': 5},
    # {'url': 'https://www.gazetaesportiva.com/feed/', 'source': 'Gazeta Esportiva',
    #  'city': 'Brasil', 'category': 'esporte', 'priority': False, 'max_entries': 3},
    # {'url': 'https://lance.com.br/feed/', 'source': 'Lance!',
    #  'city': 'Brasil', 'category': 'esporte', 'priority': False, 'max_entries': 3},
]

# Ordem importa: cidades mais específicas ANTES de genéricas
CITY_KEYWORDS = {
    'Schroeder':     ['schroeder', 'schroder'],
    'Guaramirim':    ['guaramirim'],
    'Corupá':        ['corupá', 'corupa'],
    'Joinville':     ['joinville', 'joinvilense', 'joinvilhense'],
    'Jaraguá do Sul':['jaraguá do sul', 'jaragua do sul', 'jaraguaense', 'jaraguá', 'hospital são josé', 'hospital jaraguá', 'br-280 jaraguá'],
    'Blumenau':      ['blumenau', 'blumenauense'],
    'Florianópolis': ['florianópolis', 'floripa', 'florianopolitano'],
    'Norte de SC':   ['norte catarinense', 'norte de santa catarina', 'região norte'],
    'Santa Catarina':['santa catarina', 'catarinense'],
}

# Cidades que pertencem ao Norte de SC (para o filtro de região)
NORTE_SC_CITIES = {'Schroeder', 'Joinville', 'Jaraguá do Sul', 'Guaramirim', 'Corupá', 'Norte de SC'}

CATEGORY_KEYWORDS = {
    'policial': ['crime', 'assalto', 'homicídio', 'acidente', 'preso', 'policial', 'pm', 'delegacia', 'roubo', 'furto', 'morte', 'óbito', 'batida', 'colisão'],
    'politica': ['prefeitura', 'câmara', 'vereador', 'prefeito', 'eleição', 'governo', 'governador', 'deputado', 'política'],
    'saude': ['hospital', 'saúde', 'dengue', 'vacina', 'ubs', 'médico', 'doença', 'covid', 'pandemia'],
    'esporte': ['futebol', 'esporte', 'atleta', 'campeonato', 'jogo', 'gol', 'time', 'torneio', 'libertadores', 'brasileirão', 'brasileirao', 'escalações', 'escalacao', 'rodada', 'tabela do campeonato', 'série a', 'serie a', 'copa do brasil', 'flamengo', 'corinthians', 'palmeiras', 'são paulo', 'grêmio', 'internacional', 'cruzeiro', 'atlético'],
    'economia': ['emprego', 'empresa', 'mercado', 'economia', 'negócio', 'indústria', 'comércio', 'renda'],
    'clima': ['chuva', 'temporal', 'vento', 'frio', 'calor', 'enchente', 'clima', 'previsão do tempo'],
    'cultura': ['evento', 'festa', 'show', 'cultura', 'música', 'teatro', 'exposição', 'festival'],
    # 🚧 TRÂNSITO (13/ago, ordem do dono: "o buraco que os vizinhos têm e nós não") — a novela
    # diária da BR-280. Obra/fluxo/interdição é TRÂNSITO; acidente com vítima segue POLICIAL
    # (o detect escolhe por MAIS acertos, e acidente puxa termos policiais junto).
    'transito': ['trânsito', 'transito', 'br-280', 'br 280', 'sc-108', 'sc-416', 'rodovia',
                 'interdição', 'interditada', 'interditado', 'desvio', 'duplicação', 'pedágio',
                 'congestionamento', 'fila de veículos', 'obras na pista', 'pista', 'viaduto',
                 'ponte', 'asfalto', 'pavimentação', 'semáforo', 'rotatória', 'binário',
                 'faixa de pedestre', 'estacionamento rotativo', 'detran', 'radar de velocidade'],
}


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)   # espera o banco destravar em vez de estourar
    conn.row_factory = sqlite3.Row
    return conn


# ── Deduplicação por CONTEÚDO (mesmo fato vindo de várias fontes) ──
_DEDUP_STOP = set((
    "de da do das dos a o e os as um uma uns umas no na nos nas ao aos que com por "
    "para pra apos sobre entre ate sem sob desde como mais menos muito pouco urgente "
    "video veja confira saiba assista foto fotos imagem imagens noticia em e foi sao "
    "ser tem ter dois tres anos ano hoje agora cidade regiao apos"
).split())


def _stem_keys(text):
    t = unicodedata.normalize("NFKD", (text or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    keys = set()
    for w in re.findall(r"[a-z0-9]+", t):
        if len(w) < 3 or w in _DEDUP_STOP:
            continue
        keys.add(w[:5])  # stem leve por prefixo (atropelado/atropelamento -> atrop)
    return keys


def _overlap(a, b):
    ka, kb = _stem_keys(a), _stem_keys(b)
    if not ka or not kb:
        return 0.0
    return len(ka & kb) / min(len(ka), len(kb))


def _is_similar(title, titles, thresh=0.6):
    """True se 'title' for o mesmo fato de algum título já visto."""
    for t in titles:
        if _overlap(title, t) >= thresh:
            return True
    return False


def detect_city(text):
    text_lower = text.lower()
    for city, keywords in CITY_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return city
    return 'Santa Catarina'


# ☔ Fontes de clima que cobrem o SUL INTEIRO (MetSul fala muito de Porto Alegre/RS): o
# detect_city tem fallback 'Santa Catarina', que colocaria selo SC em notícia 100% gaúcha.
# Regra: cidade específica de SC > menção a SC/Sul → 'Santa Catarina' > só-RS/outros → 'Brasil'
# (e aí o pick_next só deixa passar se for útil — ciclone/tempestade passam pelo _NACIONAL_UTIL).
_FONTES_CLIMA_SUL = {'MetSul Meteorologia', 'Defesa Civil SC'}
_MENCIONA_SC = re.compile(r"santa catarina|catarinense|\bsc\b|vale do itapoc|litoral norte|"
                          r"regi[ãa]o sul|sul do (brasil|pa[íi]s)|frente fria|todo o sul", re.IGNORECASE)


def _cidade_clima(texto):
    """Cidade correta pra matéria de fonte de clima do Sul (sem herdar o fallback SC indevido)."""
    c = detect_city(texto)
    if c and c != 'Santa Catarina':
        return c                          # achou cidade específica (Jaraguá, Joinville...)
    return 'Santa Catarina' if _MENCIONA_SC.search(texto or "") else 'Brasil'


# 🚪 DIETA NA PORTA (3/ago): notícia claramente de FORA da nossa área (país estrangeiro,
# outro estado, campeonato europeu, candidatura presidencial) SEM nenhum gancho de SC não
# entra nem no funil. Antes: entrava, o motor vestia ela de SC ("selo Santa Catarina" +
# "marca um amigo do Vale"), o Portão barrava e a fila /revisar virava depósito (Grécia,
# Cuba, Guaíba/RS, neve na Argentina, UEFA, Augusto Cury...). Barrar na origem > revisar.
# O GANCHO SC salva o que importa: "De Joinville para a Rússia" fica (Joinville), frente
# fria do RS chegando em SC fica (menciona SC) — "Nível do Guaíba baixa" (só RS) morre.
_FORA_DA_AREA = re.compile(
    r"Gr[ée]cia|Atenas|\bCuba\b|Argentina|Uruguai|\bChile\b|Venezuela|M[ée]xico|"
    r"Estados Unidos|\bEUA\b|R[úu]ssia|Ucr[âa]nia|\bChina\b|Jap[ãa]o|Israel|\bIr[ãa]\b|"
    r"\bGaza\b|Portugal|Espanha|Fran[çc]a|It[áa]lia|Alemanha|\bEuropa\b|"
    r"\bKiev\b|\bKyiv\b|Moscou|russ[oa]s?\b|ucranian[oa]s?\b|Zelensky|Putin|"
    r"Cor[ée]ia|\b[ÍI]ndia\b|Indon[ée]sia|Austr[áa]lia|Canad[áa]|Turquia|Egito|"
    r"Filipinas|Tail[âa]ndia|Vietn[ãa]|Paquist[ãa]o|Afeganist[ãa]o|S[íi]ria|"
    r"\bL[íi]bano\b|Nig[ée]ria|\b[ÁA]frica\b|Col[ôo]mbia|\bPeru\b|Bol[íi]via|Equador|"
    r"\bNASA\b|\bOMS\b|\bONU\b|UEFA|Champions|Liga Europa|Premier League|"
    r"\bno RS\b|\bdo RS\b|Rio Grande do Sul|Porto Alegre|Gua[íi]ba|Cidreira|"
    r"litoral ga[úu]cho|\bem SP\b|\bde SP\b|\bno Paran[áa]\b|Curitiba|Rio de Janeiro|"
    r"pr[ée]-candidatura [àa] presid[êe]ncia|presid[êe]ncia da Rep[úu]blica",
    re.IGNORECASE)
_GANCHO_SC = re.compile(
    r"Santa Catarina|catarinense|\bSC\b|Jaragu[áa]|Guaramirim|Schroeder|Corup[áa]|"
    r"Massaranduba|Joinville|Blumenau|Itaja[íi]|Balne[áa]rio|Florian[óo]polis|"
    r"Crici[úu]ma|Chapec[óo]|Vale do Itapocu|Norte de SC|Barra Velha",
    re.IGNORECASE)


# 🏠 SC-LONGE (8/ago, ordem do dono: "notícias de Criciúma, Blumenau etc de longe devem
# sumir — ficar só as do Vale"). Cidade catarinense FORA da nossa região na manchete, sem
# nenhuma cidade NOSSA junto, e que não seja CLIMA → nem entra. O gancho genérico "SC" não
# salva (era por ele que o estado inteiro inundava o feed — 63% dos posts, views de 60-200).
# Região NOSSA (fica): Vale do Itapocu + Joinville/litoral norte vizinho + planalto norte.
_SC_LONGE = re.compile(
    r"Florian[óo]polis|Blumenau|Itaja[íi]|Balne[áa]rio Cambori[úu]|\bCambori[úu]\b|Brusque|"
    r"Crici[úu]ma|Tubar[ãa]o|\bLages\b|Chapec[óo]|Xanxer[êe]|Conc[óo]rdia|Ca[çc]ador|"
    r"Videira|Joa[çc]aba|S[ãa]o Joaquim|Urussanga|Ararangu[áa]|\bLaguna\b|Imbituba|"
    r"Itapema|Bombinhas|Porto Belo|Navegantes|Api[úu]na|Ibirama|Rio do Sul|Indaial|"
    r"Timb[óo]|Gaspar|Ilhota|Palho[çc]a|S[ãa]o Jos[ée]\b|Bigua[çc]u|Tijucas|Forquilhinha|"
    r"Guatambu|Capivari de Baixo|Campos Novos|Palma Sola|\bModelo\b|Fraiburgo|Curitibanos|"
    r"Herval|Ituporanga|Ta[ió][óo]\b|Orleans|Bra[çc]o do Norte|Sombrio|Maravilha|Pinhalzinho",
    re.IGNORECASE)
# 🎯 REGRA MASTER do dono (11/ago): o jornal é DESSAS 5 CIDADES. Ponto.
_CINCO_CIDADES = re.compile(
    r"Jaragu[áa]|Schroeder|Guaramirim|Corup[áa]|Joinville", re.IGNORECASE)

_GANCHO_NORTE = re.compile(
    r"Jaragu[áa]|Schroeder|Guaramirim|Corup[áa]|Massaranduba|Joinville|Barra Velha|"
    r"S[ãa]o Jo[ãa]o do Itaperi[úu]|Pomerode|S[ãa]o Bento do Sul|Rio Negrinho|Mafra|"
    r"Canoinhas|Itapo[áa]|Garuva|Araquari|S[ãa]o Francisco do Sul|Pi[çc]arras|\bPenha\b|"
    r"Vale do Itapocu|Norte de SC|norte catarinense",
    re.IGNORECASE)


# Marca INEQUÍVOCA de esporte (usada só pra VETAR classificação policial — ver uso abaixo)
_ESPORTE_FORTE = re.compile(
    r"sele[çc][ãa]o brasileira|liga das na[çc][õo]es|copa d[oa]|campeonato|brasileir[ãa]o|"
    r"libertadores|futsal|v[ôo]lei|voleibol|f[uú]tebol|handebol|basquete|"
    r"jogo d[eo]|partida|rodada|placar|\bgols?\b|\batleta|olimp[íi]|paralimp|"
    r"f[óo]rmula 1|grande pr[êe]mio|\bgp d[ao]\b|sub-\d{2}|artilheir|t[ée]cnico do",
    re.IGNORECASE)


def detect_category(text):
    """Categoria por PALAVRA INTEIRA (\\b) — evita 'preso' casar dentro de 'Caropreso' (sobrenome)
    e marcar política/saúde como POLICIAL. Escolhe a categoria com MAIS acertos (não a 1ª que casa)."""
    text_lower = text.lower()
    best, best_score = 'geral', 0
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords
                    if re.search(r'\b' + re.escape(kw) + r'\b', text_lower))
        if score > best_score:
            best, best_score = category, score
    return best


# 🧽 Resíduo de scraping (fix 9/ago — auditoria jurídica): feeds WordPress terminam com
# "The post X appeared first on FONTE." / "O post X apareceu primeiro em FONTE." — isso é
# assinatura de cópia visível no fallback do site e nos cards da fila. Fora, sempre.
_RODAPE_FEED = re.compile(
    r"(The post\b.{0,300}?\bappeared first on\b[^.]{0,80}\.?|"
    r"O post\b.{0,300}?\bapareceu primeiro em\b[^.]{0,80}\.?|"
    r"Leia mais em[^.]{0,80}\.?)\s*$",
    re.IGNORECASE | re.DOTALL)


def clean_html(text):
    if not text:
        return ''
    soup = BeautifulSoup(text, 'lxml')
    txt = soup.get_text(separator=' ').strip()
    return _RODAPE_FEED.sub('', txt).strip()


# Cabeçalhos de navegador real — portais regionais (ex: SchPost) devolvem 403 p/ UA de bot.
# Accept-Language pt-BR + Referer do Google + Upgrade-Insecure-Requests passam pelo bloqueio.
_BROWSER_HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9',
    'Referer': 'https://www.google.com/',
    'Upgrade-Insecure-Requests': '1',
    'Connection': 'keep-alive',
}


# ── Fontes cujas IMAGENS NÃO usamos (litigiosas: OCP e Portal de Schroeder/Gabriel). Mantemos o
#    TEXTO (o fato é livre; a gente reescreve). G1 fica liberado. Edite via env IMG_BLOCK_DOMAINS.
# metsul.com BLOQUEADA 30/jul: posts saíram com "Foto: MetSul" — a MetSul é notoriamente
# agressiva juridicamente com uso de imagens. Texto reescrito pode (Art. 46); imagem JAMAIS.
# defesacivil idem por consistência (capa de clima usa NOSSO arsenal, que rende mais mesmo).
_IMG_BLOCK = [d.strip().lower() for d in
              os.environ.get("IMG_BLOCK_DOMAINS",
                             "ocp.news,schpost.com.br,metsul.com,defesacivil.sc.gov.br").split(",")
              if d.strip()]


def _image_blocked(link, source=""):
    """True se a notícia vem de fonte com imagem bloqueada (não usar a foto, só o texto)."""
    blob = f"{link or ''} {source or ''}".lower()
    return any(d and d in blob for d in _IMG_BLOCK)


def fetch_og_image(link):
    """Foto da PÁGINA da matéria (og:image / twitter:image). Resolve o buraco dos feeds
    locais que não trazem foto no RSS mas têm na página. Devolve URL ou None.
    É a foto do PRÓPRIO portal da notícia que estamos reportando (uso jornalístico)."""
    if not link or not link.startswith(('http://', 'https://')):
        return None
    try:
        r = requests.get(link, headers=_BROWSER_HEADERS, timeout=8, verify=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, 'lxml')
        for attrs in ({'property': 'og:image'}, {'property': 'og:image:url'},
                      {'name': 'twitter:image'}, {'name': 'twitter:image:src'}):
            tag = soup.find('meta', attrs=attrs)
            if tag and tag.get('content', '').strip().startswith(('http://', 'https://')):
                return tag['content'].strip()
    except Exception as e:
        logger.info(f"og:image falhou ({link[:50]}): {e}")
    return None


_TEXT_LIXO = re.compile(
    r"leia (mais|tamb[eé]m)|compartilh|publicidade|continua ap[oó]s|aceit[ae].*cookies|"
    r"(siga|participe|receba).*(instagram|whatsapp|telegram|grupo|not[ií]cias)|"
    r"fale conosco|grupo no whatsapp|todos os direitos|clique aqui|"
    r"\bfoto:|\bfonte:|inscreva-se|newsletter", re.IGNORECASE)


def fetch_article_text(link, min_total=180, max_total=1400):
    """Puxa o CORPO da matéria da página, p/ encher o carrossel quando o RSS vem sem resumo
    (15% das notícias). Funciona com texto em <p> OU solto dentro do <article>: usa
    stripped_strings (cada fragmento de texto), filtra boilerplate (leia mais, WhatsApp,
    cookies) e junta. Devolve texto corrido ou None (best-effort, nunca quebra a coleta)."""
    if not link or not link.startswith(('http://', 'https://')):
        return None
    try:
        r = requests.get(link, headers=_BROWSER_HEADERS, timeout=8, verify=True)
        r.raise_for_status()
        # html.parser evita o modo XML (portais com <?xml?> no topo) e acha o <article>.
        soup = BeautifulSoup(r.content, 'html.parser')
        for tag in soup(['script', 'style', 'nav', 'aside', 'footer', 'header', 'form', 'figure']):
            tag.decompose()

        # escopo: o <article> (ou o container com mais texto); senão a página toda
        scope = soup.find('article')
        if scope is None:
            best, best_len = None, 0
            for cont in soup.find_all(['div', 'section', 'main']):
                tlen = len(cont.get_text(strip=True))
                if tlen > best_len:
                    best, best_len = cont, tlen
            scope = best or soup

        partes, total, seen = [], 0, set()
        for frag in scope.stripped_strings:
            t = re.sub(r'\s+', ' ', frag).strip()
            if len(t) < 40 or t in seen or _TEXT_LIXO.search(t):
                continue
            seen.add(t)
            partes.append(t)
            total += len(t)
            if total >= max_total:
                break
        corpo = ' '.join(partes).strip()
        if len(corpo) >= min_total:
            return corpo[:max_total]
    except Exception as e:
        logger.info(f"corpo da matéria falhou ({link[:50]}): {e}")
    return None


# Idade MÁXIMA (dias) da notícia pra entrar no motor. Evita que o HISTÓRICO antigo de um feed
# novo (que traz semanas de matéria) seja ingerido e postado como se fosse fresco. Ajuste via
# env MAX_NEWS_AGE_DIAS. Só filtra quando o feed dá data REAL; sem data -> trata como fresca.
MAX_NEWS_AGE_DIAS = int(os.environ.get("MAX_NEWS_AGE_DIAS", "3") or 3)


_UA_NAV = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}


def _resolve_gnews(link):
    """🛰️ Destrava a URL REAL por trás de news.google.com/rss/articles/... (fix 12/ago).

    Sem isso o Radar salvava o link do GOOGLE: o corpo da matéria vinha errado/misturado
    (fetch_article_text batia na página do Google), a foto vinha do CDN do Google FURANDO
    o bloqueio de imagem regional (_image_blocked checa o link — e o link era google.com),
    e o dedup com o feed direto da mesma fonte não casava. Método do googlenewsdecoder:
    página do artigo -> assinatura/timestamp -> API batchexecute. Fail-open (devolve o
    link original se qualquer etapa falhar)."""
    try:
        m = re.search(r"/articles/([^?/]+)", link)
        if not m:
            return link
        art_id = m.group(1)
        pg = requests.get(f"https://news.google.com/articles/{art_id}",
                          headers=_UA_NAV, timeout=15).text
        sg = re.search(r'data-n-a-sg="([^"]*)"', pg).group(1)
        ts = re.search(r'data-n-a-ts="([^"]*)"', pg).group(1)
        payload = ["Fbv4je",
                   f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,'
                   f'null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],'
                   f'"{art_id}",{ts},"{sg}"]']
        r = requests.post("https://news.google.com/_/DotsSplashUi/data/batchexecute",
                          headers={"content-type": "application/x-www-form-urlencoded;charset=UTF-8",
                                   **_UA_NAV},
                          data="f.req=" + quote(json.dumps([[payload]])), timeout=15)
        real = json.loads(json.loads(r.text.split("\n\n")[1])[:-2][0][2])[1]
        if real and isinstance(real, str) and real.startswith("http"):
            return real
    except Exception as e:
        logger.info(f"🛰️ radar: não destravei a URL real ({type(e).__name__}) — mantive o link do Google")
    return link


def fetch_feed(feed_config):
    """Coleta notícias de um feed RSS."""
    url = feed_config['url']
    logger.info(f"Coletando: {feed_config['source']} — {url}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; RadioSCBot/1.0)',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
        }
        response = requests.get(url, headers=headers, timeout=15, verify=True)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
    except Exception as e:
        logger.warning(f"Erro ao acessar {url}: {e}")
        try:
            # Tenta sem verificação SSL para sites com certificado auto-assinado
            response = requests.get(url, headers=headers, timeout=15, verify=False)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
        except Exception:
            try:
                feed = feedparser.parse(url)
            except Exception as e2:
                logger.error(f"Falha total em {url}: {e2}")
                return []

    max_entries = feed_config.get('max_entries', 20)
    articles = []
    for entry in feed.entries[:max_entries]:
        title = clean_html(getattr(entry, 'title', ''))
        summary = clean_html(getattr(entry, 'summary', '') or getattr(entry, 'description', ''))
        link = getattr(entry, 'link', '')
        
        # Data de publicação
        published = None
        published_dt = None
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                published_dt = datetime(*entry.published_parsed[:6])
                published = published_dt.isoformat()
            except Exception:
                pass
        if not published:
            published = datetime.now().isoformat()

        # 🛑 GUARDA DE IDADE (coleta): pula notícia VELHA — o feed novo não despeja mais o
        # histórico antigo no banco. Só filtra quando a data é real (senão, ingere).
        if published_dt is not None and (datetime.now() - published_dt).days > MAX_NEWS_AGE_DIAS:
            continue

        # Imagem da notícia
        image_url = None
        if hasattr(entry, 'media_content') and entry.media_content:
            image_url = entry.media_content[0].get('url')
        elif hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
            image_url = entry.media_thumbnail[0].get('url')
        elif hasattr(entry, 'enclosures') and entry.enclosures:
            for enc in entry.enclosures:
                if enc.get('type', '').startswith('image'):
                    image_url = enc.get('href') or enc.get('url')
                    break

        # 🚫 fonte de imagem bloqueada (OCP/Schroeder): descarta a foto, mantém o texto
        if _image_blocked(link, feed_config.get('source', '')):
            image_url = None

        # Valida que o link é uma URL real (http/https)
        if not title or not link or not link.startswith(('http://', 'https://')):
            continue

        full_text = f"{title} {summary}"
        # 🚪 dieta na porta: fora da área + sem gancho SC = nem entra (ver _FORA_DA_AREA)
        if _FORA_DA_AREA.search(full_text) and not _GANCHO_SC.search(full_text):
            logger.info(f"🚪 fora da área (sem gancho SC): {title[:70]}")
            continue
        if feed_config.get('source') in _FONTES_CLIMA_SUL:
            city = _cidade_clima(full_text)       # ☔ fonte do Sul: sem herdar fallback SC indevido
        else:
            city = feed_config.get('city') or detect_city(full_text)
        # Usa categoria do feed quando for explícita (esporte, local); senão detecta pelo texto.
        # 🔴 EXCEÇÃO (fix 16/jul): POLICIAL detectado no TEXTO sempre GANHA da categoria fixa do
        # feed — "presa pela PM/lavagem de dinheiro" saiu como 'local' (feed SchPost) e FUROU as
        # travas policiais de imagem (câmara de Schroeder ilustrou notícia de crime). Crime é crime.
        feed_cat = feed_config.get('category', 'geral')
        detected = detect_category(full_text)
        # 🏐 VETO DO ESPORTE (fix 19/jul — Inspetor: "Brasil perde da Polônia" saiu com pill
        # POLICIAL): quando o texto tem marca CLARA de esporte, nada mais o classifica como
        # crime — nem o detect, nem a categoria do feed. Derrota não é ocorrência policial.
        if _ESPORTE_FORTE.search(full_text) and (detected == 'policial' or feed_cat == 'policial'):
            feed_cat, detected = 'esporte', 'esporte'
        # ⚠️ o override NÃO vale contra feed de ESPORTE (fix 19/jul): "Antonelli vence GP" com
        # "acidente na largada" no corpo virou POLICIAL e saiu com foto de carro batido.
        # Corrida com batida continua sendo ESPORTE. Feeds 'local'/'geral' seguem cedendo.
        if detected == 'policial' and (feed_cat or 'geral') in ('geral', 'local', ''):
            category = 'policial'
        else:
            category = feed_cat if feed_cat and feed_cat != 'geral' else detected

        # 🏠 SC-longe: cidade catarinense de longe, sem cidade nossa junto, fora clima → fora
        if category != 'clima' and _SC_LONGE.search(full_text) and not _GANCHO_NORTE.search(full_text):
            logger.info(f"🏠 SC-longe (fora do Vale): {title[:70]}")
            continue

        # 🎯 REGRA MASTER (11/ago — veredito do dono após 1 dia estudando o Insta):
        # "notícias APENAS Schroeder · Jaraguá do Sul · Guaramirim · Corupá · Joinville."
        # Única exceção: CLIMA (pode ser SC/Sul/Brasil — 1º lugar do Placar, todo mundo precisa).
        # Estadual genérico, Brasil e demais cidades: NÃO entram mais, nem com selo SC.
        # 🏭 DETECTOR: empresa da região citada em qualquer feed = matéria promovida
        emp_hit = None
        _ft_low = full_text.lower()
        for _nome, _cid in EMPRESAS_REGIAO.items():
            if _nome.lower() in _ft_low:
                emp_hit = (_nome, _cid)
                break
        if emp_hit:
            city = city or emp_hit[1]
            logger.info(f"🏭 empresa da região ({emp_hit[0]}): {title[:60]}")

        if (category != 'clima' and not feed_config.get('bypass_master') and not emp_hit
                and not _CINCO_CIDADES.search(full_text)):
            logger.info(f"🎯 regra master (fora das 5 cidades): {title[:70]}")
            continue

        # 🛰️ RADAR (12/ago): item do Google News chega com link do GOOGLE, '- Fonte' colada
        # no título e descrição-lixo (âncora pro próprio Google). Aqui — DEPOIS dos filtros,
        # pra não gastar requisição com item barrado — destrava a URL real, assume a fonte
        # verdadeira e zera o resumo (o corpo REAL vem no save_articles via o link real).
        # Com o link real, o bloqueio de imagem regional e o dedup voltam a funcionar.
        source_name = feed_config['source']
        if 'news.google.com' in link:
            real = _resolve_gnews(link)
            if real != link:
                link = real
                partes = title.rsplit(' - ', 1)
                if len(partes) == 2 and 0 < len(partes[1].strip()) <= 40:
                    title, source_name = partes[0].strip(), partes[1].strip()
                summary = ''
                if image_url and _image_blocked(link, source_name):
                    image_url = None

        articles.append({
            'title': title[:500],
            'summary': summary[:2000],
            'link': link,
            'source': source_name,
            'city': city,
            'category': category,
            'published_at': published,
            'image_url': image_url,
            'priority': True if emp_hit else feed_config.get('priority', False),
        })

    return articles


def _ensure_text_cols(conn):
    """Garante as colunas do NOSSO texto (reescrita) na tabela news."""
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(news)")]
        if 'title_own' not in cols:
            conn.execute("ALTER TABLE news ADD COLUMN title_own TEXT")
        if 'resumo_own' not in cols:
            conn.execute("ALTER TABLE news ADD COLUMN resumo_own TEXT")
        if 'materia_own' not in cols:
            conn.execute("ALTER TABLE news ADD COLUMN materia_own TEXT")
        conn.commit()
    except Exception as e:
        logger.error(f"_ensure_text_cols falhou: {e}")


def _reescreve(art):
    """Reescreve a notícia no NOSSO tom (anti-strike + emoção) via cerebro. (titulo, corpo) ou
    (None, None) se desligado/IA falhar — aí o site cai no texto original."""
    if os.environ.get("REWRITE_ON", "1").strip() == "0":
        return None, None
    try:
        import cerebro
        t, c, _ = cerebro.gerar_texto(
            art.get('summary') or art.get('title') or '',
            cidade=art.get('city') or '', fonte=art.get('source') or '',
            titulo_hint=art.get('title') or '')
        if t and c:
            return t.strip()[:500], c.strip()[:2000]
    except Exception as e:
        logger.error(f"reescrita falhou p/ '{(art.get('title') or '')[:40]}': {e}")
    return None, None


def _gerar_materia(art):
    """MATÉRIA COMPLETA nossa (3-5 parágrafos) pro SITE — o conteúdo que o Google ranqueia
    (a página de notícia com ~250 chars é rasa demais pra busca/Discover). Só gera quando a
    fonte tem material (summary >= 350 chars). Trava MATERIA_ON (default ligado); None se
    IA falhar — a página cai no resumo curto, nada quebra. Custo: ~centavos (Gemini flash)."""
    if os.environ.get("MATERIA_ON", "1").strip() == "0":
        return None
    if os.environ.get("REWRITE_ON", "1").strip() == "0":
        return None
    fonte = (art.get('summary') or '').strip()
    if len(fonte) < 350:
        return None                      # sem material -> matéria inventada, não fazemos isso
    try:
        import cerebro
        prompt = (
            "Você é o redator do Rádio SC News (Vale do Itapocu, Norte de SC). Reescreva a "
            "notícia abaixo como uma MATÉRIA COMPLETA de portal, com as SUAS palavras (nunca "
            "copie frases da fonte):\n"
            "- 3 a 5 parágrafos curtos (2-3 frases cada), separados por UMA linha em branco\n"
            "- 1º parágrafo é o lide: o fato principal, com a cidade e quando\n"
            "- Apenas FATOS do texto-fonte; PROIBIDO inventar dado, número, nome ou declaração\n"
            "- Tom claro e direto de portal local, sem opinião, sem clickbait, sem emoji, sem hashtag\n"
            "Responda SÓ os parágrafos.\n\n"
            f"TÍTULO: {art.get('title') or ''}\n"
            f"CIDADE: {art.get('city') or ''}\n"
            f"TEXTO-FONTE: {fonte[:3000]}"
        )
        m = (cerebro.completar(prompt) or "").strip()
        if 200 <= len(m) <= 4500:
            return m
    except Exception as e:
        logger.error(f"matéria falhou p/ '{(art.get('title') or '')[:40]}': {e}")
    return None


def save_articles(articles):
    """Salva notícias, ignorando duplicatas. ENRIQUECE (Fase 2): se a duplicata trouxer foto
    e a versão já salva estiver SEM foto, preenche a foto (não joga a foto fora).
    TEXTO NOSSO: reescreve cada notícia nova no tom da Rádio (title_own/resumo_own)."""
    conn = get_db()
    _ensure_text_cols(conn)
    saved = 0
    # base de comparação: registros recentes (id, título, foto) — p/ dedup E enriquecimento
    try:
        recent = conn.execute(
            "SELECT id, title, image_url FROM news WHERE created_at > datetime('now','-3 days')"
        ).fetchall()
        vistos = [{'id': r['id'], 'title': r['title'], 'image_url': r['image_url']}
                  for r in recent if r['title']]
    except Exception:
        vistos = []

    for art in articles:
        try:
            if conn.execute('SELECT id FROM news WHERE link = ?', (art['link'],)).fetchone():
                continue

            # acha a gêmea (mesmo fato) já salva
            gemea = next((v for v in vistos if _overlap(art['title'], v['title']) >= 0.6), None)

            if gemea:
                # FOTO (Fase 2): se a salva está SEM foto e dá pra achar uma, preenche
                if not gemea.get('image_url') and not _image_blocked(art.get('link'), art.get('source')):
                    foto = art.get('image_url') or (fetch_og_image(art['link']) if art.get('link') else None)
                    if foto:
                        conn.execute('UPDATE news SET image_url=? WHERE id=?', (foto, gemea['id']))
                        gemea['image_url'] = foto
                        logger.info(f"📷 enriqueci gêmea #{gemea['id']} com foto de '{art['title'][:40]}'")
                logger.info(f"♻ Duplicada (mesmo fato) ignorada: {art['title'][:60]}")
                continue

            # NOVA notícia -> og:image se vier sem foto (Fase 1), depois insere
            if not art.get('image_url') and art.get('link') and not _image_blocked(art.get('link'), art.get('source')):
                art['image_url'] = fetch_og_image(art['link'])
                if art['image_url']:
                    logger.info(f"📷 og:image achada p/ '{art['title'][:45]}'")

            # TEXTO: resumo vazio/curto -> puxa o corpo da matéria (carrossel deixa de ser raso)
            if len((art.get('summary') or '').strip()) < 180 and art.get('link'):
                corpo = fetch_article_text(art['link'])
                if corpo and len(corpo) > len((art.get('summary') or '').strip()):
                    art['summary'] = corpo[:2000]
                    logger.info(f"📝 texto enriquecido p/ '{art['title'][:45]}' ({len(corpo)} chars)")

            # TEXTO NOSSO: reescreve no tom da Rádio (anti-strike + emoção). Site/Insta usam o nosso.
            title_own, resumo_own = _reescreve(art)
            if title_own:
                logger.info(f"✍️ reescrito p/ '{art['title'][:45]}' -> '{title_own[:45]}'")
            # MATÉRIA COMPLETA nossa pro site (SEO/Discover) — None se fonte curta/IA off
            materia_own = _gerar_materia(art)

            cur = conn.execute('''
                INSERT INTO news (title, summary, title_own, resumo_own, materia_own, link, source,
                                  city, category, published_at, image_url, priority, audio_file, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
            ''', (
                art['title'], art['summary'], title_own, resumo_own, materia_own, art['link'],
                art['source'], art['city'], art['category'],
                art['published_at'], art.get('image_url'), int(art.get('priority', False)),
                datetime.now().isoformat()
            ))
            vistos.append({'id': cur.lastrowid, 'title': art['title'], 'image_url': art.get('image_url')})
            saved += 1
        except Exception as e:
            logger.error(f"Erro ao salvar notícia: {e}")

    conn.commit()  # commita inserts E enriquecimentos
    conn.close()
    logger.info(f"Salvas {saved} novas notícias.")
    return saved


def clear_blocked_images(conn):
    """Apaga imagens JÁ salvas de fontes bloqueadas (OCP/Schroeder) — fica só o texto. Idempotente."""
    try:
        rows = conn.execute(
            "SELECT id, link, source FROM news WHERE image_url IS NOT NULL AND image_url!=''"
        ).fetchall()
        n = 0
        for r in rows:
            if _image_blocked(r['link'], r['source']):
                conn.execute("UPDATE news SET image_url=NULL WHERE id=?", (r['id'],))
                n += 1
        if n:
            conn.commit()
            logger.info(f"🧹 {n} imagem(ns) de fonte bloqueada (OCP/Schroeder) limpa(s).")
        return n
    except Exception as e:
        logger.error(f"clear_blocked_images falhou: {e}")
        return 0


def backfill_text(conn, limit=8):
    """Reescreve aos poucos as notícias ANTIGAS sem o nosso texto (title_own) — converte a base
    inteira p/ o nosso tom sem rodar tudo de uma vez (um punhado por coleta). Trava BACKFILL_ON."""
    if os.environ.get("BACKFILL_ON", "1").strip() == "0":
        return 0
    try:
        rows = conn.execute(
            "SELECT id, title, summary, source, city FROM news "
            "WHERE active=1 AND (title_own IS NULL OR title_own='') "
            "ORDER BY datetime(published_at) DESC LIMIT ?", (limit,)
        ).fetchall()
    except Exception:
        return 0
    n = 0
    for r in rows:
        art = {'title': r['title'], 'summary': r['summary'],
               'source': r['source'], 'city': r['city']}
        t, c = _reescreve(art)
        if t:
            m = _gerar_materia(art)      # matéria completa junto (SEO das páginas antigas)
            conn.execute("UPDATE news SET title_own=?, resumo_own=?, materia_own=? WHERE id=?",
                         (t, c, m, r['id']))
            n += 1
    # 2º passe: notícia que JÁ tem o texto curto mas ainda NÃO tem matéria completa
    # (as páginas antigas que o Google vai visitar) — um punhado por coleta.
    try:
        rows2 = conn.execute(
            "SELECT id, title, summary, source, city FROM news "
            "WHERE active=1 AND title_own IS NOT NULL AND title_own != '' "
            "AND (materia_own IS NULL OR materia_own='') "
            "AND length(COALESCE(summary,'')) >= 350 "
            "ORDER BY datetime(published_at) DESC LIMIT 4"
        ).fetchall()
        for r in rows2:
            m = _gerar_materia({'title': r['title'], 'summary': r['summary'],
                                'source': r['source'], 'city': r['city']})
            if m:
                conn.execute("UPDATE news SET materia_own=? WHERE id=?", (m, r['id']))
                n += 1
    except Exception:
        pass
    if n:
        conn.commit()
        logger.info(f"✍️ backfill: {n} notícia(s) antiga(s) reescrita(s) no nosso tom.")
    return n


def collect_all():
    """Coleta de todos os feeds RSS configurados."""
    # limpeza idempotente: tira imagem de OCP/Schroeder que tenha entrado antes do bloqueio
    try:
        _c = get_db()
        clear_blocked_images(_c)
        _c.close()
    except Exception:
        pass
    total = 0
    for feed_config in RSS_FEEDS:
        articles = fetch_feed(feed_config)
        saved = save_articles(articles)
        total += saved
    # 🏛️ FONTES OFICIAIS (12/ago, carta branca do dono): prefeitura direto da fonte —
    # ato oficial é livre (Art. 8º da 9.610) e vira SERVIÇO exclusivo (interdição/obra/
    # prazo). Já vem só das 5 cidades por construção; categoria detectada aqui.
    try:
        import fontes_oficiais
        oficiais = fontes_oficiais.coletar()
        for art in oficiais:
            art['category'] = art.get('category') or detect_category(art['title'])
        saved = save_articles(oficiais)
        total += saved
        if saved:
            logger.info(f"🏛️ fontes oficiais: {saved} novas")
    except Exception as e:
        logger.warning(f"🏛️ fontes oficiais falharam: {e}")
    logger.info(f"Coleta concluída. Total de novas notícias: {total}")
    # backfill gradual do texto antigo (converte a base p/ o nosso tom, um pouco por coleta)
    try:
        _c = get_db()
        _ensure_text_cols(_c)
        backfill_text(_c)
        _c.close()
    except Exception:
        pass
    return total


if __name__ == '__main__':
    collect_all()
