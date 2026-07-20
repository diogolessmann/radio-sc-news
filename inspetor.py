# -*- coding: utf-8 -*-
"""
inspetor.py — 🔍 O INSPETOR (a "Thais-bot"): revisor noturno do feed.

Nasceu em 17/jul/2026, um dia depois de a editora-chefe honorária achar 3 erros no olho:
tartaruga com foto de cachorro · "que orgulho" em lei polêmica · câmara municipal ilustrando
lavagem de dinheiro. O Inspetor faz essa revisão TODO DIA, em todos os posts, e manda os
SUSPEITOS no WhatsApp do dono — em vez de a família escanear o feed inteiro.

Como funciona (1x/dia, ~22h45):
  1. Pega os posts publicados nas últimas 24h (ig_media_id no banco)
  2. Baixa da Graph API a IMAGEM DE CAPA e a LEGENDA reais que foram AO AR
  3. O Gemini revisa como revisor de jornal (checklist de 5 pontos)
  4. Suspeitos -> WhatsApp do dono (mesma Evolution do Vigia), com link do post

Checklist: imagem×manchete combinam? · opinião em tema político? · lugar identificável em
notícia de crime? · cidade certa? · português.

Travas: INSPETOR_ON (default 1) · INSPETOR_SO_ALERTA=1 (só manda zap se houver suspeito)
        INSPETOR_MODEL (default gemini-2.5-flash)
FAIL-SAFE total: qualquer falha só loga — o Inspetor NUNCA derruba nada. Custo: centavos/dia.
"""
import base64
import json
import os
import re
import sqlite3
import sys

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DB_PATH = os.environ.get("DB_PATH", "radio_sc.db")
GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
# gemini-3-flash: na calibragem (17/jul) foi 4/4; o 2.5-flash implicava com "elemento extra"
# na foto (gato junto do cachorro = falso positivo). Modelo mais esperto segue nuance melhor.
MODEL = (os.environ.get("INSPETOR_MODEL", "gemini-3-flash-preview") or "gemini-3-flash-preview").strip()
META_TOKEN = (os.environ.get("META_PAGE_TOKEN") or "").strip()
GRAPH = "https://graph.facebook.com/v21.0"


def ativo():
    return os.environ.get("INSPETOR_ON", "1").strip() != "0" and bool(GEMINI_API_KEY)


# ---------------------------------------------------------------- coleta
def coletar(conn):
    """Posts publicados nas últimas 24h que têm ig_media_id (dá pra buscar a capa real)."""
    return conn.execute(
        "SELECT id, title, title_own, city, category, ig_media_id, ig_permalink "
        "FROM news WHERE ig_media_id IS NOT NULL AND ig_media_id != '' "
        "AND replace(social_posted_at,'T',' ') >= datetime('now','-24 hours') "
        "ORDER BY social_posted_at DESC LIMIT 40").fetchall()


def _capa_e_legenda(media_id):
    """Graph API: a imagem de CAPA e a LEGENDA reais do post no ar. (None, None, None) se falhar."""
    if not META_TOKEN:
        return None, None, None
    try:
        r = requests.get(f"{GRAPH}/{media_id}",
                         params={"fields": "media_type,media_url,permalink,caption,children{media_url,media_type}",
                                 "access_token": META_TOKEN}, timeout=25)
        r.raise_for_status()
        d = r.json()
        url = d.get("media_url")
        if d.get("media_type") == "CAROUSEL_ALBUM":
            kids = (d.get("children") or {}).get("data") or []
            if kids:
                url = kids[0].get("media_url") or url        # capa = 1º slide
        if not url:
            return None, d.get("caption"), d.get("permalink")
        img = requests.get(url, timeout=25)
        img.raise_for_status()
        return img.content, d.get("caption"), d.get("permalink")
    except Exception as e:
        print(f"[inspetor] graph falhou p/ {media_id}: {e}")
        return None, None, None


# ---------------------------------------------------------------- o revisor (Gemini)
_CHECKLIST = (
    "Você é o REVISOR-CHEFE de um jornal local do Norte de SC. Avalie este post JÁ PUBLICADO "
    "no Instagram (imagem de capa + manchete + legenda).\n\n"
    "RÉGUA (importante): só aponte o que um LEITOR COMUM olharia e diria 'isso está ERRADO'. "
    "O fundo é ILUSTRATIVO — não precisa ser literal: paisagem com sol E nuvens serve para "
    "clima em geral; rua genérica serve para trânsito. APROVE por padrão; num dia normal, "
    "menos de 10% dos posts têm problema de verdade.\n\n"
    "REPROVE APENAS SE:\n"
    "1. IMAGEM CONTRADIZ o fato central: espécie ERRADA de animal (cachorro p/ tartaruga); "
    "trator/e-sports p/ futebol; festa p/ tragédia; sol radiante SEM nuvem p/ tempestade. "
    "Elementos EXTRAS na foto (outro bicho junto, pessoas ao fundo, objetos) NÃO são problema "
    "se o assunto principal da manchete está presente na imagem.\n"
    "2. OPINIÃO em tema político/lei/câmara/religião/costumes: 'que orgulho', 'boa notícia', "
    "'vitória', emoji de festa. (Emoção em esporte/conquista/clima é PERMITIDA.)\n"
    "3. CRIME + LUGAR IDENTIFICÁVEL: notícia policial com prédio público reconhecível "
    "(prefeitura/câmara/escola, nome na fachada) ou cartão-postal óbvio de uma cidade.\n"
    "4. CIDADE TROCADA: o SELO/pill de cidade que aparece NA IMAGEM contradiz a cidade da "
    "manchete. (Julgue só o que o leitor VÊ — ignore o campo 'cidade (banco)', é interno.)\n"
    "5. PORTUGUÊS: erro grosseiro de grafia/concordância na manchete.\n"
    "6. BAIRRISMO FALSO: a notícia é de FORA da região (outro estado, outro país, nacional) "
    "mas o texto chama de 'nosso/nossa', 'do Vale', 'coisa nossa', ou sugere que a pessoa/"
    "empresa/time é daqui. (Ex.: piloto italiano vencendo na Bélgica chamado de 'do Vale'.)\n"
    "7. ELOGIO A AUTORIDADE: matéria policial que elogia ou ataca a polícia/justiça "
    "('trabalho sério da nossa polícia') em vez de só relatar.\n\n"
    "Responda APENAS JSON: {\"ok\": true} se nada grave, ou "
    "{\"ok\": false, \"problemas\": [\"<máx 12 palavras cada>\", ...]}. Problemas CURTOS.\n\n"
)


def _auditar(img_bytes, manchete, legenda, cidade, categoria):
    """Devolve dict {'ok': bool, 'problemas': [...]} ou None (falha -> não acusa ninguém)."""
    if not GEMINI_API_KEY:
        return None
    parts = [{"text": _CHECKLIST +
              f"MANCHETE: {manchete}\nCIDADE (banco): {cidade} · CATEGORIA: {categoria}\n"
              f"LEGENDA: {(legenda or '')[:500]}"}]
    if img_bytes:
        parts.append({"inline_data": {"mime_type": "image/jpeg",
                                      "data": base64.b64encode(img_bytes).decode("ascii")}})
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{MODEL}:generateContent?key={GEMINI_API_KEY}")
    cfg = {"temperature": 0.0, "maxOutputTokens": 500}
    b_think = {"contents": [{"parts": parts}], "generationConfig": {**cfg, "thinkingConfig": {"thinkingBudget": 0}}}
    b_plain = {"contents": [{"parts": parts}], "generationConfig": cfg}
    # 503/truncamento do Gemini são INTERMITENTES: tenta 3x (2 formatos + 1 retry) antes de desistir
    for body in (b_think, b_plain, b_think):
        try:
            r = requests.post(url, headers={"Content-Type": "application/json"}, json=body, timeout=40)
            r.raise_for_status()
            cand = (r.json().get("candidates") or [{}])[0]
            if cand.get("finishReason") == "MAX_TOKENS":
                continue
            txt = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []))
            txt = re.sub(r"^```(json)?|```$", "", txt.strip(), flags=re.MULTILINE).strip()
            m = re.search(r"\{.*\}", txt, re.DOTALL)
            if m:
                d = json.loads(m.group(0))
                return {"ok": bool(d.get("ok", True)),
                        "problemas": [str(p)[:140] for p in (d.get("problemas") or [])][:4]}
        except Exception as e:
            print(f"[inspetor] tentativa falhou ({e}) — tentando de novo")
            continue
    return None


# ---------------------------------------------------------------- o turno do inspetor
def run(enviar=True):
    """Revisa os posts do dia e reporta. Devolve {'auditados', 'suspeitos', 'relatorio'}."""
    if not ativo():
        return {"auditados": 0, "suspeitos": 0, "relatorio": "inspetor off"}
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    posts = coletar(conn)
    conn.close()
    suspeitos, auditados = [], 0
    for p in posts:
        try:
            img, caption, permalink = _capa_e_legenda(p["ig_media_id"])
            manchete = p["title_own"] or p["title"] or ""
            veredito = _auditar(img, manchete, caption, p["city"], p["category"])
            if veredito is None:
                continue
            auditados += 1
            if not veredito["ok"] and veredito["problemas"]:
                suspeitos.append({
                    "titulo": manchete[:70],
                    "link": permalink or p["ig_permalink"] or f"(media {p['ig_media_id']})",
                    "problemas": veredito["problemas"],
                })
                print(f"[inspetor] 🚩 suspeito: {manchete[:60]} -> {veredito['problemas']}")
        except Exception as e:
            print(f"[inspetor] post {p['id']} falhou: {e}")
    # relatório
    if suspeitos:
        linhas = [f"🔍 INSPETOR Rádio SC — {auditados} posts revisados, "
                  f"{len(suspeitos)} suspeito(s) pra você conferir:"]
        for s in suspeitos[:6]:
            linhas.append(f"\n🚩 {s['titulo']}\n   → {'; '.join(s['problemas'])}\n   {s['link']}")
        linhas.append("\n(Confere. Se for erro real: edita/apaga o post e manda o print pro Fable "
                      "— aí a raiz vira trava permanente.)")
        rel = "\n".join(linhas)
    else:
        rel = f"🔍 INSPETOR Rádio SC — {auditados} posts revisados hoje: ✅ tudo limpo."
    so_alerta = os.environ.get("INSPETOR_SO_ALERTA", "0").strip() == "1"
    if enviar and (suspeitos or not so_alerta):
        try:
            import vigia
            vigia.send_zap(rel)
        except Exception as e:
            print(f"[inspetor] zap falhou: {e}")
    print(rel)
    return {"auditados": auditados, "suspeitos": len(suspeitos), "relatorio": rel}


if __name__ == "__main__":
    run(enviar=False)
