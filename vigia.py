# -*- coding: utf-8 -*-
"""
vigia.py — O VIGIA da fábrica (dead-man switch + backup via WhatsApp).

A fábrica posta sozinha — e falha CALADA (token Meta vencido, bug, deploy ruim).
O Vigia confere todo dia se os posts saíram e manda ZAP pro dono na hora se a
fábrica parou. Domingo manda o resumo da semana + BACKUP do banco (o único
backup fora do Railway).

Usa a Evolution API que o dono já roda no 4kitem — zero dependência nova.

DORMENTE até configurar no Railway:
  EVOLUTION_URL       ex: https://evolution-xxxx.up.railway.app
  EVOLUTION_APIKEY    a apikey global da Evolution
  EVOLUTION_INSTANCE  nome da instância conectada (ex: a do 4kitem)
  VIGIA_ZAP           número do dono com DDI, ex: 5547999606998
Opcional: VIGIA_MIN_POSTS (default 4) — mínimo esperado de posts/dia.
"""
import base64
import gzip
import os
import sqlite3
from datetime import datetime

import requests

DB_PATH = os.environ.get("DB_PATH", "radio_sc.db")


def _cfg():
    url = (os.environ.get("EVOLUTION_URL") or "").rstrip("/")
    key = os.environ.get("EVOLUTION_APIKEY") or ""
    inst = os.environ.get("EVOLUTION_INSTANCE") or ""
    num = os.environ.get("VIGIA_ZAP") or ""
    if url and key and inst and num:
        return {"url": url, "key": key, "inst": inst, "num": num}
    return None


def ligado():
    return _cfg() is not None


def _post(cfg, path, body):
    r = requests.post(f"{cfg['url']}/{path}/{cfg['inst']}",
                      headers={"apikey": cfg["key"], "Content-Type": "application/json"},
                      json=body, timeout=30)
    return r.ok, r.text[:200]


def _instancia_viva(cfg):
    """Pergunta à Evolution qual instância está CONECTADA agora.
    O nome da instância MUDA quando ela é recriada — em 18/jul o Vigia (e o Inspetor)
    ficaram MUDOS por dias porque EVOLUTION_INSTANCE apontava p/ 'mz1n12', que não existia
    mais, e o send_zap engolia o 404 em silêncio. Um dead-man switch que morre calado é pior
    que não ter dead-man switch."""
    try:
        r = requests.get(f"{cfg['url']}/instance/fetchInstances",
                         headers={"apikey": cfg["key"]}, timeout=20)
        if not r.ok:
            return None
        d = r.json()
        for i in (d if isinstance(d, list) else d.get("instances", [])):
            inst = i.get("instance") if isinstance(i.get("instance"), dict) else i
            nome = inst.get("name") or inst.get("instanceName")
            st = (inst.get("connectionStatus") or inst.get("status") or "").lower()
            if nome and st == "open":
                return nome
    except Exception:
        pass
    return None


def _enviar(cfg, texto):
    ok, resp = _post(cfg, "message/sendText", {"number": cfg["num"], "text": texto})
    if not ok:       # formato v1 da Evolution
        ok, resp = _post(cfg, "message/sendText",
                         {"number": cfg["num"], "textMessage": {"text": texto}})
    return ok, resp


def send_zap(texto):
    """Manda texto pro dono. True/False — NUNCA levanta (o Vigia não pode derrubar nada).
    Falha agora é BARULHENTA no log + auto-recupera se a instância foi recriada."""
    cfg = _cfg()
    if not cfg:
        return False
    try:
        ok, resp = _enviar(cfg, texto)
        if not ok and "does not exist" in (resp or ""):
            nova = _instancia_viva(cfg)
            if nova and nova != cfg["inst"]:
                print(f"⚠️ VIGIA: instância '{cfg['inst']}' não existe mais — enviando por "
                      f"'{nova}'. CORRIJA EVOLUTION_INSTANCE no Railway.")
                cfg = {**cfg, "inst": nova}
                ok, resp = _enviar(cfg, texto)
        if not ok:
            print(f"⚠️ VIGIA: Evolution recusou o envio — {str(resp)[:200]}")
        return ok
    except Exception as e:
        print(f"⚠️ VIGIA: falha ao enviar zap — {e}")
        return False


def send_arquivo(caminho, nome, legenda=""):
    """Manda um documento (ex: backup do banco) pro zap do dono."""
    cfg = _cfg()
    if not cfg:
        return False
    try:
        with open(caminho, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        ok, _ = _post(cfg, "message/sendMedia", {
            "number": cfg["num"], "mediatype": "document",
            "media": b64, "fileName": nome, "caption": legenda})
        return ok
    except Exception:
        return False


def _q(sql):
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        v = conn.execute(sql).fetchone()[0]
        conn.close()
        return v or 0
    except Exception:
        return 0


def checar_dia():
    """Dead-man switch: se a fábrica postou menos que o mínimo hoje, alerta no zap.
    Só alerta com autopost LIGADO (senão 'zero post' é o esperado, não falha)."""
    if not ligado():
        return {"ok": False, "motivo": "vigia off (faltam env vars)"}
    if os.environ.get("SOCIAL_AUTOPOST", "0") != "1":
        return {"ok": False, "motivo": "autopost off"}
    minimo = int(os.environ.get("VIGIA_MIN_POSTS", "4") or 4)
    # Janela ROLANTE de 24h, não "dia calendário": o container roda em UTC — às 21h30 de
    # Brasília já é "amanhã" em UTC e a contagem zerava (alarme falso no 1º disparo real).
    # replace(T->espaço): social_posted_at é isoformat com 'T'; datetime() do SQLite usa espaço.
    posts24 = _q("SELECT COUNT(*) FROM news WHERE replace(social_posted_at,'T',' ') "
                 ">= datetime('now','-24 hours')")
    fila = _q("SELECT COUNT(*) FROM news WHERE social_hold IS NOT NULL AND social_hold != '' "
              "AND (social_posted_at IS NULL OR social_posted_at='') AND active=1")
    if posts24 < minimo:
        send_zap(f"🚨 VIGIA Rádio SC: só {posts24} post(s) nas últimas 24h (mínimo esperado: {minimo}).\n"
                 f"A fábrica pode ter PARADO — confere o token Meta e os logs do Railway."
                 + (f"\n📋 E tem {fila} matéria(s) esperando na fila /revisar." if fila else ""))
        return {"ok": True, "alerta": True, "posts": posts24}
    if fila >= 5:
        send_zap(f"📋 VIGIA Rádio SC: {fila} matérias paradas na fila /revisar — "
                 f"dá uma olhada (aprovar ou descartar).")
    return {"ok": True, "alerta": False, "posts": posts24, "fila": fila}


def resumo_semana():
    """Domingo: resumo da semana no zap + BACKUP do banco (gzip) como documento.
    É o único backup FORA do Railway — guarda o arquivo que chegar."""
    if not ligado():
        return {"ok": False, "motivo": "vigia off"}
    posts7 = _q("SELECT COUNT(*) FROM news WHERE replace(social_posted_at,'T',' ') "
                ">= datetime('now','-7 days')")
    novas7 = _q("SELECT COUNT(*) FROM news WHERE replace(created_at,'T',' ') "
                ">= datetime('now','-7 days')")
    fila = _q("SELECT COUNT(*) FROM news WHERE social_hold IS NOT NULL AND social_hold != '' "
              "AND (social_posted_at IS NULL OR social_posted_at='') AND active=1")
    send_zap(f"📊 VIGIA Rádio SC — resumo da semana:\n"
             f"✅ {posts7} posts publicados\n"
             f"📰 {novas7} notícias coletadas\n"
             f"📋 {fila} na fila de revisão\n"
             f"💾 backup do banco a caminho...")
    try:
        import tempfile
        stamp = datetime.now().strftime("%Y%m%d")
        tmp = os.path.join(tempfile.gettempdir(), f"radio_sc_{stamp}.db")
        try:
            os.remove(tmp)
        except Exception:
            pass
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("VACUUM INTO ?", (tmp,))
        conn.close()
        gz = tmp + ".gz"
        with open(tmp, "rb") as f_in, gzip.open(gz, "wb") as f_out:
            f_out.write(f_in.read())
        ok = send_arquivo(gz, f"radio_sc_backup_{stamp}.db.gz",
                          "💾 Backup semanal do banco da Rádio — guarda este arquivo.")
        for p in (tmp, gz):
            try:
                os.remove(p)
            except Exception:
                pass
        if not ok:
            send_zap("⚠️ VIGIA: não consegui anexar o backup (Evolution recusou o arquivo).")
    except Exception as e:
        send_zap(f"⚠️ VIGIA: backup falhou: {e}")
    return {"ok": True, "posts7": posts7, "novas7": novas7}


if __name__ == "__main__":
    print("Vigia ligado?", ligado())
    print("checar_dia:", checar_dia())
