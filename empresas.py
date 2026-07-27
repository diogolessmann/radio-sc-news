# -*- coding: utf-8 -*-
"""
empresas.py — 🏭 EMPRESAS DO VALE (pedido do dono, 27/jul/2026).

1x por semana (quinta 17h — o horário-rei do Placar), uma matéria CELEBRANDO uma empresa
da região: história, crescimento, investimento — "coisas boas de empresas da região".
REGRA DO DONO: só Jaraguá do Sul, Guaramirim, Schroeder ou Corupá.

⚠️ REGRA DE AÇO (anti-processo/anti-vergonha): matéria sobre empresa NOMEADA **NUNCA
posta sozinha** — sempre entra na fila /revisar (social_hold) pro dono aprovar com 1
clique. E a IA escreve APENAS com os fatos do banco abaixo (curados) — é PROIBIDO
inventar data, número, prêmio ou nome de fundador.

Estratégia (além do conteúdo): é o funil de venda editorial — a empresa destacada
compartilha, agradece, e vira lead quente pro pacote "sua história vira reportagem".
"""
import os
import sys
from datetime import date, datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Fatos CURADOS (só o que é público e sólido; onde não há certeza, não há fato).
# O dono pode adicionar empresas aqui — em especial de Schroeder e Guaramirim.
EMPRESAS = [
    {"nome": "WEG", "cidade": "Jaraguá do Sul", "setor": "motores elétricos e energia",
     "fatos": ["fundada em 1961 em Jaraguá do Sul pelos três fundadores cujas iniciais formam o nome: Werner, Eggon e Geraldo",
               "é uma das maiores fabricantes de motores elétricos do mundo",
               "presente em mais de 100 países, com o coração e a sede em Jaraguá do Sul",
               "um dos maiores orgulhos industriais de Santa Catarina e do Brasil"]},
    {"nome": "Duas Rodas", "cidade": "Jaraguá do Sul", "setor": "ingredientes para alimentos",
     "fatos": ["fundada em 1925 em Jaraguá do Sul — uma empresa CENTENÁRIA",
               "líder na América Latina em ingredientes e essências para a indústria de alimentos",
               "de Jaraguá do Sul para o mundo: seus ingredientes estão em produtos que o brasileiro consome todo dia"]},
    {"nome": "Malwee", "cidade": "Jaraguá do Sul", "setor": "moda e confecção",
     "fatos": ["uma das maiores empresas de moda do Brasil, de raiz familiar jaraguaense",
               "mantém o Parque Malwee, um dos maiores parques privados abertos à comunidade da região",
               "referência nacional em moda com produção mais sustentável"]},
    {"nome": "Marisol", "cidade": "Jaraguá do Sul", "setor": "vestuário",
     "fatos": ["fundada em 1964 em Jaraguá do Sul",
               "dona de marcas queridas do vestuário infantil brasileiro, como Lilica Ripilica e Tigor T. Tigre",
               "vestiu gerações de crianças brasileiras a partir do Vale do Itapocu"]},
    {"nome": "Urbano Alimentos", "cidade": "Jaraguá do Sul", "setor": "alimentos",
     "fatos": ["um dos maiores beneficiadores de arroz do Brasil, com sede em Jaraguá do Sul",
               "do Vale do Itapocu para a mesa de milhões de famílias brasileiras",
               "referência também em derivados de arroz, como farinhas e snacks"]},
    {"nome": "Menegotti", "cidade": "Jaraguá do Sul", "setor": "metalurgia e máquinas",
     "fatos": ["uma das indústrias mais antigas de Jaraguá do Sul, com mais de um século de história",
               "fabricante tradicional de máquinas para a construção civil",
               "ajudou a construir a vocação metalmecânica do Vale"]},
    {"nome": "Zanotti", "cidade": "Jaraguá do Sul", "setor": "elásticos e componentes têxteis",
     "fatos": ["referência latino-americana na fabricação de elásticos",
               "componente jaraguaense presente em roupas de todo o continente",
               "parte da força têxtil silenciosa do Vale do Itapocu"]},
    {"nome": "Bretzke Alimentos", "cidade": "Jaraguá do Sul", "setor": "alimentos",
     "fatos": ["tradicional fabricante de alimentos de Jaraguá do Sul",
               "conhecida por sobremesas, achocolatados e produtos que estão na despensa do catarinense",
               "história construída por gerações da mesma família"]},
    {"nome": "Breithaupt", "cidade": "Jaraguá do Sul", "setor": "varejo e construção",
     "fatos": ["grupo varejista com mais de 90 anos de história em Jaraguá do Sul",
               "das lojas de materiais de construção aos supermercados, acompanhou o crescimento da cidade",
               "uma marca que virou parte da paisagem do Vale"]},
    {"nome": "Lunender", "cidade": "Guaramirim", "setor": "moda e têxtil",
     "fatos": ["uma das grandes forças da moda catarinense, com operação em Guaramirim",
               "gera milhares de empregos na região do Vale do Itapocu",
               "moda guaramirense vestindo o Brasil"]},
    {"nome": "Banana de Corupá", "cidade": "Corupá", "setor": "agricultura (bananicultura)",
     "fatos": ["Corupá é reconhecida como a capital catarinense da banana",
               "a Banana de Corupá tem Indicação Geográfica (IG) registrada no INPI — reconhecimento oficial de qualidade e origem",
               "produtores familiares cultivam nas encostas do Vale uma das bananas mais doces do Brasil",
               "orgulho agrícola que atravessa gerações de famílias corupaenses"]},
    {"nome": "Polo metalmecânico de Guaramirim", "cidade": "Guaramirim", "setor": "indústria metalmecânica",
     "fatos": ["Guaramirim abriga um polo industrial metalmecânico em constante crescimento",
               "às margens da BR-280, atrai indústrias e distribui empregos pela região",
               "a cidade que mais cresce industrialmente no eixo do Vale do Itapocu"]},
    {"nome": "Facções e confecções de Schroeder", "cidade": "Schroeder", "setor": "têxtil familiar",
     "fatos": ["Schroeder é sustentada por dezenas de facções e confecções familiares",
               "o trabalho têxtil de fundo de quintal que virou motor econômico da cidade",
               "cada galpão familiar é uma história de trabalho e persistência alemã"]},
]

_MARKER_DIR = os.path.join("static", "social")


def da_semana(quando=None):
    """Empresa da semana — rotação determinística pela semana ISO (sem estado)."""
    d = quando or date.today()
    idx = d.isocalendar()[1] % len(EMPRESAS)
    return EMPRESAS[idx]


def _escrever(emp):
    """IA escreve a matéria SÓ com os fatos curados. Fallback: template local."""
    fatos = "; ".join(emp["fatos"])
    prompt = (
        "Voce e o editor da Radio SC News (Vale do Itapocu, Norte de SC). Escreva uma materia "
        "CURTA e CELEBRATORIA da serie 'EMPRESAS DO VALE' sobre a empresa abaixo — historia, "
        "crescimento, orgulho local. Tom: vizinho orgulhoso + jornalismo (aqui PODE celebrar: "
        "a empresa E daqui).\n"
        "REGRA ABSOLUTA: use APENAS os fatos fornecidos. E PROIBIDO citar datas, numeros, nomes "
        "ou premios que NAO estejam na lista. Nao invente NADA.\n"
        "PROIBIDO: 'que orgulho' (muleta), superlativos vazios, tom de anuncio pago.\n\n"
        f"EMPRESA: {emp['nome']} ({emp['cidade']} — {emp['setor']})\n"
        f"FATOS (a unica fonte permitida): {fatos}\n\n"
        "Responda EXATAMENTE neste formato:\n"
        "TITULO: <manchete celebratoria curta, SEM ponto final, citando a empresa e a cidade>\n"
        "RESUMO: <4 a 5 linhas curtas, 1 frase por linha, contando a historia com emocao>"
    )
    try:
        import cerebro
        txt = cerebro.completar(prompt) or ""
        import re
        m = re.search(r"(?is)titulo:\s*(.+?)\s*resumo:\s*(.+)$", txt)
        if m:
            return m.group(1).strip().strip('"'), m.group(2).strip().strip('"')
    except Exception as e:
        print(f"[empresas] IA indisponivel ({e}) — usando template")
    titulo = f"EMPRESAS DO VALE: a história da {emp['nome']}, orgulho de {emp['cidade']}"
    resumo = "\n".join(f["fatos"][0].capitalize() if isinstance(f, dict) else f.capitalize()
                       for f in emp["fatos"][:4])
    return titulo, resumo


def run(quando=None):
    """Gera a matéria da semana e SEGURA na fila /revisar (nunca auto-posta).
    Idempotente por semana (marker)."""
    if os.environ.get("EMPRESAS_ON", "1").strip() == "0":
        return {"ok": False, "motivo": "EMPRESAS_ON=0"}
    d = quando or date.today()
    stamp = f"{d.isocalendar()[0]}w{d.isocalendar()[1]}"
    marker = os.path.join(_MARKER_DIR, f".empresa_{stamp}.done")
    if os.path.exists(marker):
        return {"ok": False, "motivo": "ja gerou esta semana"}
    emp = da_semana(d)
    titulo, resumo = _escrever(emp)
    import distribuidor as dist
    conn = dist.get_db()
    dist.ensure_column(conn)
    cur = conn.execute(
        "INSERT INTO news (title, summary, title_own, resumo_own, link, source, city, category, "
        "published_at, priority, created_at, social_hold) "
        "VALUES (?, ?, ?, ?, '', 'Radio SC News — Empresas do Vale', ?, 'economia', ?, 0, ?, ?)",
        (titulo[:500], resumo, titulo[:500], resumo, emp["cidade"],
         datetime.now().isoformat(), datetime.now().isoformat(),
         f"empresa: {emp['nome']} — aguardando aprovacao do dono @ {datetime.now().isoformat(timespec='seconds')}"))
    conn.commit()
    nid = cur.lastrowid
    conn.close()
    os.makedirs(_MARKER_DIR, exist_ok=True)
    with open(marker, "w") as f:
        f.write(f"{nid}")
    # avisa o dono no zap (fila espera a aprovação dele)
    try:
        import vigia
        vigia.send_zap(f"🏭 EMPRESAS DO VALE — matéria da semana pronta pra tua aprovação:\n\n"
                       f"{titulo}\n\n📥 Tá na fila /revisar — aprova e ela vai pro ar.")
    except Exception:
        pass
    print(f"[empresas] 🏭 {emp['nome']} -> fila /revisar (id {nid})")
    return {"ok": True, "id": nid, "empresa": emp["nome"], "titulo": titulo}


if __name__ == "__main__":
    emp = da_semana()
    t, r = _escrever(emp)
    print("EMPRESA DA SEMANA:", emp["nome"], f"({emp['cidade']})")
    print("TITULO:", t)
    print("RESUMO:", r)
