# -*- coding: utf-8 -*-
"""
tempo_pauta.py — 🌦️ PAUTAS DE PREVISÃO own (30/jul, pedido do dono: "clima é o que tá
bombando" + "previsão da semana no domingo").

A prova nos números: "Bom dia, Vale" genérico = 120-320 views · "PREPARE O CASACO" = 36,2 MIL
· "Virada brusca na semana" = 136.443 (o MAIOR da história). Mesma info — manchete-IMPACTO.

UM job diário às 16h20, TRÊS modos conforme o dia:
  seg-qui  → PREVISÃO DE AMANHÃ  (o dia seguinte, manchete-alerta)
  sexta    → O TEMPO DO FIM DE SEMANA (sábado+domingo juntos — "vai dar praia?")
  domingo  → A SEMANA QUE VEM (5 dias úteis — o formato do post de 136 mil)
  sábado   → previsão de amanhã (domingo)

Forecast REAL (OpenWeather 5 dias/3h, mesma chave do Bom dia) → IA escreve manchete só com
os números (drama proporcional; geada = alerta agro — Corupá é a capital da banana) → INSERT
matéria own category=clima priority → o passa-tudo de 20min posta com capa do NOSSO arsenal.
Conteúdo 100% próprio, custo ~zero, idempotente por dia. TEMPO_PAUTA_ON=0 desliga.
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
_DOW = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def _forecast_bruto():
    if not API_KEY:
        return None
    try:
        r = requests.get("https://api.openweathermap.org/data/2.5/forecast",
                         params={"q": CIDADE_ANCORA, "appid": API_KEY,
                                 "units": "metric", "lang": "pt_br"}, timeout=25)
        r.raise_for_status()
        return r.json().get("list", [])
    except Exception as e:
        print(f"[tempo] forecast falhou: {e}")
        return None


def _agg(bs):
    temps = [b["main"]["temp_min"] for b in bs] + [b["main"]["temp_max"] for b in bs]
    conds = [b["weather"][0]["description"] for b in bs]
    return {"min": round(min(temps)), "max": round(max(temps)),
            "chuva_mm": round(sum((b.get("rain") or {}).get("3h", 0) for b in bs), 1),
            "vento_kmh": round(max(b["wind"]["speed"] * 3.6 for b in bs)),
            "condicao": max(set(conds), key=conds.count)}


def previsao_dias(n=6):
    """Lista de dias futuros agregados: [{data, dow, min, max, chuva_mm, vento_kmh, condicao}]."""
    blocos = _forecast_bruto()
    if not blocos:
        return None
    dias = []
    for delta in range(1, n + 1):
        d = date.today() + timedelta(days=delta)
        ds = d.strftime("%Y-%m-%d")
        bs = [b for b in blocos if b["dt_txt"].startswith(ds)]
        if not bs:
            continue
        a = _agg(bs)
        a["data"] = ds
        a["dow"] = _DOW[d.weekday()]
        dias.append(a)
    return dias or None


def _fatos_dia(a):
    return (f"{a['dow']}: {a['min']}°C a {a['max']}°C, chuva {a['chuva_mm']}mm, "
            f"vento até {a['vento_kmh']} km/h, {a['condicao']}")


def _ia_manchete(prompt):
    try:
        import cerebro
        import re
        txt = cerebro.completar(prompt) or ""
        m = re.search(r"(?is)titulo:\s*(.+?)\s*resumo:\s*(.+)$", txt)
        if m:
            return m.group(1).strip().strip('"'), m.group(2).strip().strip('"')
    except Exception as e:
        print(f"[tempo] IA indisponivel ({e}) — template local")
    return None


_REGRAS = ("REGRAS: use SO os numeros fornecidos (PROIBIDO inventar); drama proporcional ao "
           "dado (chuva >15mm ou vento >50km/h ou queda brusca = tom de ALERTA; minima <=3°C = "
           "ALERTA DE GEADA, avise produtores rurais — regiao de bananais; dia tranquilo = "
           "servico util); cite numeros na manchete; nada de clickbait falso.\n")


def _pauta_amanha(dias):
    a = dias[0]
    prompt = ("Voce e o editor de CLIMA da Radio SC News (Vale do Itapocu, Norte de SC). "
              "Escreva a previsao de AMANHA como POST DE IMPACTO estilo 'PREPARE O CASACO'.\n"
              + _REGRAS + f"\nDADOS REAIS de amanha: {_fatos_dia(a)}\n\n"
              "Responda EXATAMENTE neste formato:\nTITULO: <manchete curta de impacto>\n"
              "RESUMO: <4 linhas curtas, numeros + 1 dica pratica>")
    r = _ia_manchete(prompt)
    if r:
        return r
    if a["min"] <= 3:
        t = f"ALERTA DE GEADA: mínima de {a['min']}°C amanhã — proteja plantas e animais"
    elif a["chuva_mm"] >= 15 or a["vento_kmh"] >= 50:
        t = f"Atenção, Vale: {a['dow']} tem chuva de {a['chuva_mm']}mm e vento de até {a['vento_kmh']} km/h"
    elif a["min"] <= 8:
        t = f"Prepare o casaco: mínima de {a['min']}°C amanhã no Vale"
    else:
        t = f"Como fica o tempo amanhã no Vale: {a['min']}°C a {a['max']}°C"
    resumo = (f"Mínima de {a['min']}°C e máxima de {a['max']}°C.\nChuva prevista: {a['chuva_mm']}mm. "
              f"Vento até {a['vento_kmh']} km/h.\nCondição: {a['condicao']}.\n"
              "Se programa e manda pra quem precisa saber.")
    return t, resumo


def _pauta_fds(dias):
    fds = [a for a in dias if a["dow"] in ("sábado", "domingo")][:2]
    if not fds:
        return _pauta_amanha(dias)
    fatos = " | ".join(_fatos_dia(a) for a in fds)
    prompt = ("Voce e o editor de CLIMA da Radio SC News (Vale do Itapocu). Escreva O TEMPO DO "
              "FIM DE SEMANA como POST DE IMPACTO — o leitor quer saber: da pra fazer churrasco, "
              "praia, passeio? Qual dia sera melhor?\n" + _REGRAS +
              f"\nDADOS REAIS: {fatos}\n\n"
              "Responda EXATAMENTE neste formato:\nTITULO: <manchete curta comparando sabado e domingo>\n"
              "RESUMO: <4-5 linhas: 1-2 por dia com numeros + veredicto de qual dia aproveitar>")
    r = _ia_manchete(prompt)
    if r:
        return r
    s, d = fds[0], (fds[1] if len(fds) > 1 else fds[0])
    t = f"Fim de semana no Vale: sábado {s['min']}-{s['max']}°C, domingo {d['min']}-{d['max']}°C"
    resumo = (f"Sábado: {_fatos_dia(s)}.\nDomingo: {_fatos_dia(d)}.\n"
              "Se programa e compartilha com a família.")
    return t, resumo


def _pauta_semana(dias):
    uteis = dias[:5]
    fatos = " | ".join(_fatos_dia(a) for a in uteis)
    minimo = min(a["min"] for a in uteis)
    maximo = max(a["max"] for a in uteis)
    prompt = ("Voce e o editor de CLIMA da Radio SC News (Vale do Itapocu). Escreva A PREVISAO "
              "DA SEMANA (o post que o Vale SALVA pra planejar a semana — nosso maior formato: "
              "'virada brusca' com frio e calor na mesma semana fez 136 mil de alcance quando "
              "os dados justificavam).\n" + _REGRAS +
              f"\nDADOS REAIS da semana: {fatos}\n"
              f"Amplitude da semana: minima {minimo}°C, maxima {maximo}°C.\n\n"
              "Responda EXATAMENTE neste formato:\nTITULO: <manchete de impacto da SEMANA, com numeros>\n"
              "RESUMO: <5-6 linhas: o resumo dia a dia bem curto + destaque do dia mais critico>")
    r = _ia_manchete(prompt)
    if r:
        return r
    t = f"A semana no Vale: de {minimo}°C a {maximo}°C — veja o dia a dia"
    resumo = "\n".join(_fatos_dia(a).capitalize() for a in uteis)
    return t, resumo


def run(modo=None):
    """Gera a pauta do dia (modo automático pelo dia da semana) e insere no banco."""
    if os.environ.get("TEMPO_PAUTA_ON", "1").strip() == "0":
        return {"ok": False, "motivo": "TEMPO_PAUTA_ON=0"}
    stamp = date.today().strftime("%Y%m%d")
    marker = os.path.join(_MARKER_DIR, f".tempo_{stamp}.done")
    if os.path.exists(marker):
        return {"ok": False, "motivo": "ja gerou hoje"}
    dias = previsao_dias()
    if not dias:
        return {"ok": False, "motivo": "sem forecast (chave/API)"}
    dow = date.today().weekday()          # 0=seg ... 4=sex, 5=sab, 6=dom
    modo = modo or ("semana" if dow == 6 else "fds" if dow == 4 else "amanha")
    if modo == "semana":
        titulo, resumo = _pauta_semana(dias)
    elif modo == "fds":
        titulo, resumo = _pauta_fds(dias)
    else:
        titulo, resumo = _pauta_amanha(dias)
    import distribuidor as dist
    conn = dist.get_db()
    dist.ensure_column(conn)
    # 🔐 idempotência pelo BANCO (8/ago): o marker morre a cada deploy do Railway — se a
    # pauta do dia já existe no banco, não insere de novo (senão IntegrityError no link).
    if conn.execute("SELECT 1 FROM news WHERE link=?",
                    (f"own://tempo/{modo}/{stamp}",)).fetchone():
        conn.close()
        return {"ok": False, "motivo": "ja gerou hoje (banco)"}
    # link sintético único (fix 5/ago — news.link é UNIQUE; '' colidia entre matérias próprias)
    conn.execute(
        "INSERT INTO news (title, summary, title_own, resumo_own, link, source, city, category, "
        "published_at, priority, created_at) "
        "VALUES (?, ?, ?, ?, ?, 'Radio SC News — Previsao do Tempo', 'Santa Catarina', 'clima', ?, 1, ?)",
        (titulo[:500], resumo, titulo[:500], resumo, f"own://tempo/{modo}/{stamp}",
         datetime.now().isoformat(), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    os.makedirs(_MARKER_DIR, exist_ok=True)
    with open(marker, "w") as f:
        f.write(f"{modo}: {titulo}")
    print(f"[tempo] 🌦️ pauta '{modo}' criada: {titulo}")
    return {"ok": True, "modo": modo, "titulo": titulo}


if __name__ == "__main__":
    import sys as _s
    print(run(_s.argv[1] if len(_s.argv) > 1 else None))
