# -*- coding: utf-8 -*-
"""
tempo_pauta.py — 🌦️ PAUTA DIÁRIA DE PREVISÃO own (30/jul, pedido do dono: "clima é o que
tá bombando").

A prova nos números: "Bom dia, Vale" genérico = 120-320 views · "PREPARE O CASACO: massa
de ar frio" = 36,2 MIL. Mesma informação — a diferença é a MANCHETE DE IMPACTO.

Todo dia às 16h20: puxa o forecast REAL (OpenWeather, mesma chave do Bom dia) → a IA
transforma os NÚMEROS em manchete-alerta (drama só quando o dado justifica) → insere no
banco como matéria own de CLIMA → o passa-tudo (20 min) posta sozinho com capa do arsenal.

Conteúdo 100% nosso: dado da API + texto nosso + foto nossa. Custo ~zero. TEMPO_PAUTA_ON=0 desliga.
"""
import os
import sys
from datetime import date, datetime, timedelta

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

API_KEY = os.environ.get("OPENWEATHER_API_KEY", "")
CIDADE_ANCORA = "Jaragua do Sul,SC,BR"
_MARKER_DIR = os.path.join("static", "social")


def previsao_amanha():
    """Forecast de AMANHÃ pro Vale (blocos 3h da OpenWeather agregados). None se sem chave/falha."""
    if not API_KEY:
        return None
    try:
        r = requests.get("https://api.openweathermap.org/data/2.5/forecast",
                         params={"q": CIDADE_ANCORA, "appid": API_KEY,
                                 "units": "metric", "lang": "pt_br"}, timeout=25)
        r.raise_for_status()
        blocos = r.json().get("list", [])
        amanha = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        hoje = date.today().strftime("%Y-%m-%d")
        b_amanha = [b for b in blocos if b["dt_txt"].startswith(amanha)]
        b_hoje = [b for b in blocos if b["dt_txt"].startswith(hoje)]
        if not b_amanha:
            return None

        def agg(bs):
            temps = [b["main"]["temp_min"] for b in bs] + [b["main"]["temp_max"] for b in bs]
            chuva = sum((b.get("rain") or {}).get("3h", 0) for b in bs)
            vento = max((b["wind"]["speed"] * 3.6) for b in bs)          # m/s -> km/h
            conds = [b["weather"][0]["description"] for b in bs]
            return {"min": round(min(temps)), "max": round(max(temps)),
                    "chuva_mm": round(chuva, 1), "vento_kmh": round(vento),
                    "condicao": max(set(conds), key=conds.count)}
        d_am = agg(b_amanha)
        d_hj = agg(b_hoje) if b_hoje else d_am
        d_am["delta_max"] = round(d_am["max"] - d_hj["max"])
        return d_am
    except Exception as e:
        print(f"[tempo] forecast falhou: {e}")
        return None


def _manchete(d):
    """IA escreve manchete-impacto SÓ com os números reais. Fallback: templates locais."""
    dia = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"][
        (date.today() + timedelta(days=1)).weekday()]
    fatos = (f"amanhã ({dia}-feira) no Vale do Itapocu: mínima {d['min']}°C, máxima {d['max']}°C, "
             f"chuva prevista {d['chuva_mm']}mm, vento até {d['vento_kmh']} km/h, "
             f"condição predominante: {d['condicao']}, variação da máxima vs hoje: {d['delta_max']}°C")
    prompt = (
        "Voce e o editor de CLIMA da Radio SC News (Vale do Itapocu, Norte de SC). Com base "
        "APENAS nos dados abaixo, escreva a previsao de AMANHA como POST DE IMPACTO estilo "
        "'PREPARE O CASACO' — manchete que faz o leitor SALVAR e MANDAR pro grupo da familia.\n"
        "REGRAS: use SO os numeros fornecidos (PROIBIDO inventar); drama proporcional ao dado "
        "(chuva >15mm ou vento >50km/h ou queda >5°C = tom de ALERTA; dia tranquilo = tom de "
        "servico util, ex 'aproveita o sol'); cite 1-2 numeros na manchete; nada de clickbait falso.\n\n"
        f"DADOS REAIS: {fatos}\n\n"
        "Responda EXATAMENTE neste formato:\n"
        "TITULO: <manchete de impacto curta, SEM ponto final>\n"
        "RESUMO: <4 linhas curtas, 1 frase por linha, com os numeros e 1 dica pratica>"
    )
    try:
        import cerebro
        import re
        txt = cerebro.completar(prompt) or ""
        m = re.search(r"(?is)titulo:\s*(.+?)\s*resumo:\s*(.+)$", txt)
        if m:
            return m.group(1).strip().strip('"'), m.group(2).strip().strip('"')
    except Exception as e:
        print(f"[tempo] IA indisponivel ({e}) — template local")
    # fallback determinístico
    if d["chuva_mm"] >= 15 or d["vento_kmh"] >= 50:
        t = f"Atenção, Vale: {dia} tem chuva de {d['chuva_mm']}mm e vento de até {d['vento_kmh']} km/h"
    elif d["delta_max"] <= -5:
        t = f"Prepare o casaco: máxima despenca para {d['max']}°C amanhã no Vale"
    elif d["min"] <= 8:
        t = f"Friozinho chegando: mínima de {d['min']}°C amanhã no Vale"
    else:
        t = f"Como fica o tempo amanhã no Vale: {d['min']}°C a {d['max']}°C"
    r = (f"Mínima de {d['min']}°C e máxima de {d['max']}°C.\n"
         f"Chuva prevista: {d['chuva_mm']}mm. Vento até {d['vento_kmh']} km/h.\n"
         f"Condição: {d['condicao']}.\nSe programa e compartilha com quem precisa saber.")
    return t, r


def run():
    """Gera a pauta de previsão de amanhã e insere no banco (o passa-tudo de clima posta)."""
    if os.environ.get("TEMPO_PAUTA_ON", "1").strip() == "0":
        return {"ok": False, "motivo": "TEMPO_PAUTA_ON=0"}
    stamp = date.today().strftime("%Y%m%d")
    marker = os.path.join(_MARKER_DIR, f".tempo_{stamp}.done")
    if os.path.exists(marker):
        return {"ok": False, "motivo": "ja gerou hoje"}
    d = previsao_amanha()
    if not d:
        return {"ok": False, "motivo": "sem forecast (chave/API)"}
    titulo, resumo = _manchete(d)
    import distribuidor as dist
    conn = dist.get_db()
    dist.ensure_column(conn)
    conn.execute(
        "INSERT INTO news (title, summary, title_own, resumo_own, link, source, city, category, "
        "published_at, priority, created_at) "
        "VALUES (?, ?, ?, ?, '', 'Radio SC News — Previsao do Tempo', 'Santa Catarina', 'clima', ?, 1, ?)",
        (titulo[:500], resumo, titulo[:500], resumo,
         datetime.now().isoformat(), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    os.makedirs(_MARKER_DIR, exist_ok=True)
    with open(marker, "w") as f:
        f.write(titulo)
    print(f"[tempo] 🌦️ pauta criada: {titulo}")
    return {"ok": True, "titulo": titulo, "dados": d}


if __name__ == "__main__":
    print(run())
