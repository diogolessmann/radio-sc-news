# -*- coding: utf-8 -*-
"""🗂️ MIDIATECA — o cofre de mídia da marca com motor de venda embutido (18/ago/2026).

Visão do dono: "um painel admin que tem tudo — foto, vídeo — e o motor cria o texto
mais adequado para venda; se eu quiser postar na Rádio já tá ali; uma ferramenta que
no futuro posso usar para outros sites/instas". Ou seja: MARCA É CONFIGURAÇÃO.
Hoje roda a DL Mobilidade; amanhã qualquer cliente do motor-como-serviço é um bloco
novo em MARCAS_MIDIA + tokens no env — zero código novo.

Arquitetura:
- Prateleira em disco (fonte da verdade): vídeos em static/videos/dlmob (URL público
  que o Instagram baixa), fotos em static/midia/dlmob. Uploads do painel caem no
  VOLUME (DATA_DIR/midia_uploads/<marca>) e são servidos por /midia-up/<marca>/<arq>.
- Metadados leves em JSON no volume (titulo/contexto/preço/legendas/publicações) —
  sem migração de banco, sobrevive a deploy.
- Legendas por IA com DOIS dialetos: VENDA (IG da marca — emoção abre, razão fecha,
  CTA no zap) e VITRINE (IG da Rádio — tom de jornal apresentando o parceiro).
  Resposta com meta-fala ("Atenção: houve um equívoco...") é DESCARTADA (lição de
  12/ago: o prompt não vaza) e cai no fallback construído.
- Publicação reusa o arsenal do marcas.py: reel por destino e foto avulsa por destino.
"""
import json
import os
import re
import threading
import time
from datetime import datetime

import distribuidor as dist
import marcas

# ------------------------------------------------------------------ configuração por marca
MARCAS_MIDIA = {
    "dlmob": {
        "label": "DL Mobilidade · Despachante Lessmann",
        "telefone_loja": "(47) 99776-6831",
        "endereco": "R. Mal. Castelo Branco, 2838 — Centro, Schroeder/SC",
        "video_dir": os.path.join("static", "videos", "dlmob"),
        "foto_dir": os.path.join("static", "midia", "dlmob"),
        "video_url_prefix": "dlmob/",         # _publish_reel monta static/videos/<isso><arquivo>
        "hashtags": "#scootereletrica #Schroeder #JaraguaDoSul #ValeDoItapocu #DLMobilidade",
        "disclaimer": "*sujeito a análise de crédito",
        # destinos de publicação: rótulo -> como publicar
        "destinos": {"desp": "🏛️ IG Despachante", "radio": "📻 IG Rádio"},
    },
}

_DATA = os.environ.get("DATA_DIR", ".")
_UP_BASE = os.path.join(_DATA, "midia_uploads")
_META_PATH = os.path.join(_DATA, "midiateca_meta.json")
_LOG_PATH = os.path.join("static", "social", "midiateca_log.json")

_EXT_FOTO = (".jpg", ".jpeg", ".png", ".webp")
_EXT_VIDEO = (".mp4",)


# ------------------------------------------------------------------ metadados (JSON no volume)
def _meta_all():
    try:
        with open(_META_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _meta_save(d):
    try:
        os.makedirs(os.path.dirname(_META_PATH) or ".", exist_ok=True)
        with open(_META_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except Exception as e:
        print(f"   ! meta da midiateca não salvou: {e}")


def meta_get(marca, arquivo):
    return _meta_all().get(f"{marca}/{arquivo}", {})


def meta_set(marca, arquivo, **campos):
    d = _meta_all()
    k = f"{marca}/{arquivo}"
    d.setdefault(k, {}).update({c: v for c, v in campos.items() if v is not None})
    _meta_save(d)
    return d[k]


# ------------------------------------------------------------------ prateleira
def upload_dir(marca):
    p = os.path.join(_UP_BASE, marca)
    os.makedirs(p, exist_ok=True)
    return p


def listar(marca):
    """Todos os itens da marca (repo + uploads), novos primeiro. [{arquivo,tipo,origem,url,meta}]"""
    cfg = MARCAS_MIDIA[marca]
    itens = []

    def _scan(pasta, origem):
        try:
            for f in os.listdir(pasta):
                low = f.lower()
                if low.endswith(_EXT_FOTO):
                    tipo = "foto"
                elif low.endswith(_EXT_VIDEO):
                    tipo = "video"
                else:
                    continue
                caminho = os.path.join(pasta, f)
                if origem == "upload":
                    url = f"/midia-up/{marca}/{f}"
                elif tipo == "video":
                    url = "/" + cfg["video_dir"].replace(os.sep, "/") + "/" + f
                else:
                    url = "/" + cfg["foto_dir"].replace(os.sep, "/") + "/" + f
                itens.append({"arquivo": f, "tipo": tipo, "origem": origem, "url": url,
                              "mtime": os.path.getmtime(caminho),
                              "meta": meta_get(marca, f)})
        except Exception:
            pass

    _scan(cfg["video_dir"], "repo")
    _scan(cfg["foto_dir"], "repo")
    _scan(upload_dir(marca), "upload")
    # 🗑️ excluídos pelo dono somem do grid (marca no meta — sobrevive a deploy;
    # arquivo de repo só sai de verdade num commit posterior de limpeza)
    itens = [i for i in itens if not i["meta"].get("excluido")]
    itens.sort(key=lambda x: -x["mtime"])
    return itens


def excluir(marca, arquivo):
    """Upload: apaga o arquivo. Item do repo: marca 'excluido' no meta (deploy não ressuscita)."""
    up = os.path.join(upload_dir(marca), arquivo)
    if os.path.exists(up):
        os.remove(up)
    meta_set(marca, arquivo, excluido=True)
    _log(f"🗑️ excluído do grid: {arquivo}")
    return True


def _acha(marca, arquivo):
    """Localiza o item e devolve (caminho_local, url_publica_absoluta, tipo)."""
    cfg = MARCAS_MIDIA[marca]
    base = dist.PUBLIC_BASE_URL
    for pasta, origem in ((cfg["video_dir"], "repo"), (cfg["foto_dir"], "repo"),
                          (upload_dir(marca), "upload")):
        p = os.path.join(pasta, arquivo)
        if os.path.exists(p):
            tipo = "video" if arquivo.lower().endswith(_EXT_VIDEO) else "foto"
            if origem == "upload":
                url = f"{base}/midia-up/{marca}/{arquivo}"
            elif tipo == "video":
                url = f"{base}/" + cfg["video_dir"].replace(os.sep, "/") + "/" + arquivo
            else:
                url = f"{base}/" + cfg["foto_dir"].replace(os.sep, "/") + "/" + arquivo
            return p, url, tipo
    raise FileNotFoundError(arquivo)


# ------------------------------------------------------------------ legendas (o motor de venda)
def _fallback_venda(cfg, titulo, contexto, preco):
    linhas = [f"🛵 {titulo or 'Scooter elétrica'} na DL Mobilidade — Schroeder!", ""]
    if contexto:
        linhas += [contexto, ""]
    linhas += ["✅ Sem CNH e sem emplacamento (CONTRAN 996)",
               "✅ Zero gasolina — recarrega na tomada de casa",
               "💳 Até 48x ViaCredi · parcelas a partir de R$ 200*"]
    if preco:
        linhas.insert(2, f"💰 {preco}")
    linhas += ["", "🏁 TEST-RIDE GRÁTIS: vem dar uma volta antes de decidir!",
               f"📍 {cfg['endereco']}", f"📲 WhatsApp {cfg['telefone_loja']}", "",
               cfg["disclaimer"], "", cfg["hashtags"]]
    return "\n".join(linhas)


def _fallback_vitrine(cfg, titulo, contexto):
    return (f"🛵 Novidade na região: {titulo or 'scooters elétricas'} na DL Mobilidade, "
            "em Schroeder.\n\n"
            f"{(contexto + chr(10) + chr(10)) if contexto else ''}"
            "Dá pra andar sem CNH (CONTRAN 996), sem gasolina, e parcelar em até 48x "
            "pela ViaCredi — com test-ride grátis na loja.\n\n"
            f"📲 WhatsApp {cfg['telefone_loja']}\n"
            "🤝 Parceiro do Vale · @despachantelessmann")


def gerar_legendas(marca, arquivo):
    """Gera as DUAS legendas (venda + vitrine) por IA, com fallback construído.
    Salva no meta e devolve (venda, vitrine)."""
    cfg = MARCAS_MIDIA[marca]
    m = meta_get(marca, arquivo)
    titulo = m.get("titulo") or arquivo.rsplit(".", 1)[0].replace("-", " ").replace("_", " ").title()
    contexto = m.get("contexto") or ""
    preco = m.get("preco") or ""

    base_info = (f"PRODUTO/CENA: {titulo}\n"
                 f"CONTEXTO DO DONO: {contexto or '(nenhum)'}\n"
                 f"PREÇO: {preco or '(não citar valor)'}\n"
                 f"LOJA: DL Mobilidade, {cfg['endereco']} — WhatsApp {cfg['telefone_loja']}\n"
                 "FATOS FIXOS: scooters elétricas NXT; sem CNH e sem emplacamento (CONTRAN 996); "
                 "zero gasolina; até 48x ViaCredi; parcelas a partir de R$ 200 (com asterisco de "
                 "análise de crédito); test-ride grátis na loja.")

    p_venda = (
        "Você escreve legendas de Instagram que VENDEM para uma loja de scooters elétricas "
        "em Schroeder/SC. Escreva UMA legenda pronta (sem opções, sem comentários) sobre a "
        "mídia abaixo. Método: EMOÇÃO ABRE (a cena da vida melhor: sem fila de ônibus, sem "
        "gasolina, liberdade no dia a dia), RAZÃO FECHA (48x ViaCredi, parcela a partir de "
        "R$ 200*, sem CNH pela CONTRAN 996). 6-10 linhas curtas com emojis com gosto, "
        "TERMINE com test-ride + endereço + WhatsApp + '*sujeito a análise de crédito' + as "
        "hashtags. PROIBIDO: 'boleto', promessa falsa, preço inventado, meta-comentário. "
        "Sua resposta vai DIRETO pro ar.\n\n" + base_info +
        f"\nHASHTAGS: {cfg['hashtags']}"
    )
    p_vitrine = (
        "Você é o editor da Rádio SC News (jornal local do Vale do Itapocu) apresentando um "
        "PARCEIRO da região no Instagram do jornal. Escreva UMA legenda curta (4-7 linhas) "
        "em tom de vitrine jornalística — informativa e simpática, SEM cara de anúncio "
        "gritado: o que é, onde fica, por que o morador pode se interessar (sem CNH pela "
        "CONTRAN 996, sem gasolina, até 48x ViaCredi), fecha com o WhatsApp da loja e a "
        "menção @despachantelessmann. PROIBIDO: 'boleto', 'imperdível', caps lock excessivo, "
        "meta-comentário. Sua resposta vai DIRETO pro ar.\n\n" + base_info
    )

    venda = vitrine = None
    try:
        import cerebro
        v = (cerebro.completar(p_venda) or "").strip()
        if v and not dist._fala_de_ia(v):
            venda = v
        w = (cerebro.completar(p_vitrine) or "").strip()
        if w and not dist._fala_de_ia(w):
            vitrine = w
    except Exception as e:
        print(f"   ! IA das legendas indisponível ({e}) — fallback")
    venda = venda or _fallback_venda(cfg, titulo, contexto, preco)
    vitrine = vitrine or _fallback_vitrine(cfg, titulo, contexto)
    meta_set(marca, arquivo, legenda_venda=venda, legenda_vitrine=vitrine)
    return venda, vitrine


# ------------------------------------------------------------------ publicação
def _log(linha):
    try:
        os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
        try:
            with open(_LOG_PATH, encoding="utf-8") as f:
                hist = json.load(f)
        except Exception:
            hist = []
        hist.insert(0, {"quando": datetime.now().strftime("%d/%m %H:%M"), "msg": linha})
        with open(_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(hist[:24], f, ensure_ascii=False)
    except Exception:
        pass


def publish_photo_dest(dest, image_url, caption):
    """Foto AVULSA no IG do destino ('radio' usa META_*, 'desp' usa tokens da marca)."""
    if dest == "radio":
        token, ig_id = dist.META_PAGE_TOKEN, dist.META_IG_USER_ID
    else:
        token, ig_id, _ = marcas._brand_tokens(marcas.BRANDS["dl_mobilidade"])
    if not (token and ig_id):
        raise RuntimeError(f"Tokens do destino '{dest}' ausentes.")
    GRAPH = dist.GRAPH
    cont = dist._graph_post(f"{GRAPH}/{ig_id}/media",
                            {"image_url": image_url, "caption": caption,
                             "access_token": token})["id"]
    time.sleep(3)
    return dist._graph_post(f"{GRAPH}/{ig_id}/media_publish",
                            {"creation_id": cont, "access_token": token})


def publicar(marca, arquivo, dest, caption):
    """Publica o item no destino, com rastro etapa-a-etapa no log (lição da videoteca:
    thread sem rastro é miragem). Roda em thread — devolve na hora."""
    def _job():
        _log(f"⏳ iniciando: {arquivo} -> {dest}")
        try:
            caminho, url, tipo = _acha(marca, arquivo)
            if tipo == "video":
                cfg = MARCAS_MIDIA[marca]
                if os.path.dirname(caminho).endswith(os.path.join("videos", marca)):
                    r = marcas.publish_reel_dest(dest, cfg["video_url_prefix"] + arquivo, caption)
                else:
                    r = marcas.publish_reel_dest(dest, arquivo, caption, video_url=url)
            else:
                r = publish_photo_dest(dest, url, caption)
            pubs = meta_get(marca, arquivo).get("publicados", [])
            pubs.append({"dest": dest, "quando": datetime.now().strftime("%d/%m %H:%M"),
                         "id": (r or {}).get("id")})
            meta_set(marca, arquivo, publicados=pubs)
            _log(f"✅ publicado: {arquivo} -> {dest} (id {(r or {}).get('id')})")
        except Exception as e:
            _log(f"❌ falhou: {arquivo} -> {dest} — {e}")
    threading.Thread(target=_job, daemon=True).start()
    return True


def log_recente(n=8):
    try:
        with open(_LOG_PATH, encoding="utf-8") as f:
            return json.load(f)[:n]
    except Exception:
        return []
