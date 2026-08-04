# -*- coding: utf-8 -*-
"""
promo_grupo.py — 📣 PROPAGANDA FIXA DO GRUPO DL (4/ago/2026, pedido do dono:
"propaganda fixa toda SEXTA · DOMINGO · SEGUNDA sobre o link do grupo DL,
pro pessoal acessar e conhecer que tem tudo lá").

Card estático pré-gerado (static/promo/ — trocar a arte = trocar o JPG, zero código)
+ legenda com ângulo do dia. Publica imagem única no IG da Rádio (mesma receita do
versiculo.py: media -> media_publish com os tokens META_*). Idempotente por data.
PROMO_GRUPO_ON=0 desliga.
"""
import os
import sys
from datetime import date, datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

OUT_DIR = os.path.join("static", "social")

# dia da semana -> (arquivo do card, gancho da legenda)
_VARIANTES = {
    4: ("promo_grupo_sex.jpg",   # sexta
        "📌 GUARDA ESSE LINK pro fim de semana: multa pra analisar DE GRAÇA, "
        "scooter elétrica pra test-ride, CNH pra resolver sem fila."),
    6: ("promo_grupo_dom.jpg",   # domingo
        "Amanhã a semana começa. Que tal começar com os documentos em dia? "
        "Multa, CNH, transferência, scooter — resolve tudo num link só."),
    0: ("promo_grupo_seg.jpg",   # segunda
        "Segunda-feira é dia de destravar: aquela multa parada, a CNH vencendo, "
        "a transferência empurrada com a barriga. A gente resolve pelo zap."),
}


def _legenda(gancho):
    return (f"{gancho}\n\n"
            "🏛️ O Grupo DL é a equipe por trás da Rádio SC News — despachante há mais "
            "de 7 anos em Schroeder (credencial DETRAN/SC 2095), com 8 especialidades:\n"
            "◆ Multas e defesa de CNH (análise grátis)\n"
            "◆ Transferência e licenciamento\n"
            "◆ Scooters elétricas (test-ride no escritório)\n"
            "◆ Proteção veicular · MEI e contratos · Frotas\n\n"
            "🔗 dldespachante.com.br (link na bio)\n"
            "📲 WhatsApp (47) 99716-2967\n\n"
            "#GrupoLessmann #Schroeder #JaraguaDoSul #ValeDoItapocu #despachante")


def _marker(stamp):
    return os.path.join(OUT_DIR, f".promo_grupo_{stamp}.done")


def run(post=True, force_dow=None):
    """Posta o card do dia (sex/dom/seg). Fora desses dias: no-op."""
    if os.environ.get("PROMO_GRUPO_ON", "1").strip() == "0":
        return {"ok": False, "motivo": "PROMO_GRUPO_ON=0"}
    dow = force_dow if force_dow is not None else date.today().weekday()
    if dow not in _VARIANTES:
        return {"ok": False, "motivo": f"hoje (dow={dow}) nao e dia de promo"}
    stamp = date.today().strftime("%Y%m%d")
    if os.path.exists(_marker(stamp)):
        return {"ok": False, "motivo": "ja postou hoje"}
    arquivo, gancho = _VARIANTES[dow]
    caminho = os.path.join("static", "promo", arquivo)
    if not os.path.exists(caminho):
        return {"ok": False, "motivo": f"card nao encontrado: {caminho}"}
    import distribuidor as dist
    if not post or os.environ.get("SOCIAL_AUTOPOST", "0") != "1":
        print(f"[promo] (dry) card do dia: {arquivo}")
        return {"ok": True, "dry": True, "card": arquivo}
    import requests
    url = f"{dist.PUBLIC_BASE_URL}/static/promo/{arquivo}"
    base = f"https://graph.facebook.com/v21.0/{dist.META_IG_USER_ID}"
    r = requests.post(f"{base}/media", data={
        "image_url": url, "caption": _legenda(gancho),
        "access_token": dist.META_PAGE_TOKEN}, timeout=60)
    r.raise_for_status()
    cid = r.json()["id"]
    r2 = requests.post(f"{base}/media_publish", data={
        "creation_id": cid, "access_token": dist.META_PAGE_TOKEN}, timeout=60)
    r2.raise_for_status()
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(_marker(stamp), "w") as f:
        f.write(datetime.now().isoformat())
    print(f"[promo] 📣 propaganda do grupo postada ({arquivo})")
    return {"ok": True, "card": arquivo, "ig": r2.json()}


if __name__ == "__main__":
    print(run(post="--post" in sys.argv))
