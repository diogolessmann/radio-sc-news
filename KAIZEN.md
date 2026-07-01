# 🔧 KAIZEN — Melhoria contínua do motor (Rádio SC News + Instagram)
*Filosofia: 1% melhor por dia. Pequenas melhorias constantes > grandes reformas raras.
A cada sessão, a gente tira 1-2 itens daqui. Foco regional: Jaraguá · Schroeder · Guaramirim · Joinville.*

**Marco:** 600 → 6.242 seguidores · 842 mil views/30d (01/jul/2026). Avalanche rolando.

---

## 🎯 AGORA / próximos (o que atacar primeiro)

### Foto certa em todo post (ver ULTRA_PLAN_FOTOS.md)
- [x] **Fase 1 ⭐ og:image da matéria-fonte** — FEITO (commit fed4499). Testado: 12/12 acharam
      foto; card de Jaraguá com foto real ficou profissional. ⚠️ só vale p/ notícia NOVA (coleta
      daqui pra frente). Eventual: backfill das antigas sem foto.
- [x] **Fase 2 — enriquecer no scraper** — FEITO (commit 8698223). Duplicata com foto preenche
      a gêmea sem foto (UPDATE) em vez de descartar. Testado em banco-cópia: OK.
- [x] **Fase 3 — stock regional** — MECANISMO FEITO (commit 10e4f36). stockfoto.py mapeia
      cidade→foto em static/stock/. Testado: card de Schroeder com foto regional ficou ótimo.
      ⏳ FALTA O DONO pôr as fotos das cidades em static/stock/ (schroeder.jpg, jaragua-do-sul.jpg,
      guaramirim.jpg, joinville.jpg, sc.jpg) — ver README lá. Até lá, cai no card preto.
- [x] fotobusca (gêmea no banco, matching estrito) — FEITO.
- [x] **Categoria errada** — FEITO. detect_category agora casa por PALAVRA INTEIRA (\b) e pega a
      categoria com MAIS acertos. Bug era substring: "preso" casava dentro de "Caropreso". Testado 6/6.

### Medir pra guiar o kaizen
- [x] **Health check / métricas** — FEITO (metricas.py + /admin/saude + placar.py + insights.py).
      ⏳ O DADO real ainda não flui: abrir /admin/insights-debug e validar o token (ver Auditoria 3).

### 🔍 Da AUDITORIA 3 (skill auditing-instagram-engine, 01/jul/2026) — placar 7.7/10
*(nota caiu vs 8.2 porque agora SABEMOS que o loop de dados está quebrado — antes era invisível)*
- [ ] **🔴 (DONO, 1 clique) Fechar o loop de dados** — abrir `/admin/insights-debug` e colar o
      JSON; se faltar permissão `instagram_manage_insights`, regenerar META_PAGE_TOKEN. Sem isso
      Placar=0, LEARN_ON cego, horário-por-dado impossível, relatório de patrocinador impossível.
- [ ] **🟡 Cidade REAL no TEXTO (mesmo bug da imagem, agora no texto)** — a legenda usa
      `news["city"]` cru ("Marca quem é de X" + 📍, distribuidor.py:508) e a NARRAÇÃO do Reels
      fala a cidade errada (reels.py:73). A imagem já usa `gi._cidade_real` (detecta pelo título);
      aplicar nos dois. 2 linhas, pertencimento = gatilho nº1 de share.
- [ ] **🟡 Filtro sensível prende notícia POSITIVA com criança** — "criança/menino/menina" sozinhos
      seguram "menina de Jaraguá ganha medalha" (distribuidor.py:95-106). Exigir termo-de-menor +
      termo-de-crime/tragédia JUNTOS. Libera o conteúdo positivo que o dono QUER postar.
- [x] **Teto de posts → FUSÍVEL anti-bug (decisão do dono: "mais é mais")** — teto editorial
      REJEITADO (o volume ~10/dia é o que fez crescer). POSTS_MAX_DIA=30 default só segura job
      em loop por bug; 0 desliga. Lição gravada no PLAYBOOK_2026.md (não relitigar).
- [ ] **🟡 (DONO) Ligar "O Vale em 60s"** — RESUMO_ON=1 já gera todo dia 20h30 pra revisão em
      /admin/resumo; revisar uns dias e setar RESUMO_POST=1. Reels diário de HÁBITO, zero código.
- [ ] **🟢 gen_instagram.py:606 ainda promete "OUÇA em áudio no site"** — áudio foi removido do
      site; trocar por "mais notícias no site" (caminho Redação/CLI; o autopost já foi corrigido).
- [ ] **🟢 bom_dia.py:298 com 8 hashtags** — enxugar pra 4-5 e incluir #joinville/#corupa.
- [ ] **🟢 Carrossel até 7 slides** — ótimo 2026 é 8-10; esticar +1 corpo quando a notícia é rica.
- [ ] **📖 TÁTICAS MANUAIS (API não faz):** Trial Reels (toggle no app, 1-2/semana — 80% mais
      alcance de não-seguidor) · post COLLAB com marca local (dobra alcance — usar quando fechar
      patrocinador) · sticker de enquete diário (a arte já sai pronta em /admin/enquete).

### 🔍 Da AUDITORIA 2 (skill auditing-instagram-engine, 17/jun/2026) — placar 8.2/10 ⬆️
- [x] **🟡 alt_text (SEO de imagem)** — FEITO (commit f1b3dcf): alt tema+cidade no carrossel/foto
      (distribuidor.alt_text:540, publish_real:735). Reels não suporta alt na Graph.
- [x] **🟡 Abrir a narração do Reel com o gancho** — FEITO: `_narration_script` abre com o flash
      punchy e FECHA com CTA "Siga a Rádio SC News" (reels.py:67-81).
- [x] **🟢 Enxugar BASE_TAGS** — FEITO: 3 tags base (gen_instagram.py:98), total 3-6 por post.
- [x] **OBSOLETO: cover_hook (gancho dourado)** — REMOVIDO na faxina de 17/jun. O TikTok mode
      (flash_manchete: notícia inteira em 2 linhas na capa) virou o gancho — melhor que o kicker.
- [ ] **(DONO) GEO_LOCATIONS no Railway** — env está VAZIA (geotag depende da busca automática,
      hit incerto). Pôr os 5 Place ids garante o sinal nº1 de busca local.
- [x] **(DONO) /anuncie 99k→113k** — FEITO (01/jul): 842 mil + preços unificados com o KIT.

### 🔍 Da AUDITORIA MONSTRO (skill auditing-instagram-engine, jun/2026) — placar 6.2/10
- [x] **🔴 Geotag por cidade (location_id)** — FEITO. `geo.py` resolve env GEO_LOCATIONS → cache
      → busca Graph → None (sem geotag). Ligado no carrossel e no Reels. ⏳ falta o dono pôr os
      Place ids: GEO_LOCATIONS="Schroeder=ID,Jaragua do Sul=ID,..." no Railway (ou deixar a busca
      automática tentar). Trava GEO_ON.
- [x] **🔴 Gancho VISUAL na capa** — FEITO. `distribuidor.cover_hook()` gera gancho sóbrio (≤5
      palavras, trava anti-clickbait) via cerebro; renderizado em dourado acima dos pills
      (gen_instagram.slide_cover hook=). None se IA off/suspeito (capa = manchete real).
- [x] **🟡 Slide CTA visual de engajamento** — FEITO. slide_cta agora pede SALVA/COMENTA/
      COMPARTILHA + marca amigo da cidade (commit 0030e32).
- [x] **🟡 Carrossel mais fundo** — FEITO. generate_images adaptativo: ~200 chars/slide, até 5 de
      corpo. Notícia rica → 7 slides; curta → enxuto. (achado: 15% das notícias têm summary vazio
      → carrossel raso; melhorar enriquecimento de texto é o próximo passo.)
- [x] **Health check** — FEITO. `metricas.py` + rota `/admin/saude` (posts/dia, % foto, % por
      cidade/categoria, fila, % sem texto, stock disponível). Agora dá pra guiar por dado.
- [ ] **🔴 Render de Reels no worker web** — moviepy roda no gunicorn 1-worker/120s (reels.py:93).
      Risco de travar/timeout o site. Mover render p/ fora quando escalar vídeo (já no backlog infra).
- [x] **Enriquecer texto da notícia** — FEITO. `scraper.fetch_article_text()` puxa o corpo da
      matéria (stripped_strings, filtra boilerplate) quando o RSS vem sem resumo; ligado no
      save_articles (notícia nova c/ summary <180 chars). Achado/fix: portais regionais (SchPost)
      davam 403 p/ UA de bot → `_BROWSER_HEADERS` (Accept-Language pt-BR + Referer Google) resolve.
      Testado: 8/10 vazias enriquecidas (500-1400 chars, acentos OK). Só vale p/ coleta nova.
      ⏳ opcional: backfill das 44 antigas vazias (rodar na PROD/Railway, não no snapshot local).

---

## 📈 Instagram / conteúdo
- [ ] Observar o **CTA novo** (engajamento: comenta/salva/compartilha) — ajustar se preciso.
- [ ] Testar **formatos interativos** (enquete, "manda tua pauta", caixinha).
- [ ] Considerar **rosto/personagem recorrente** (retenção) — futuro.
- [ ] Afinar prompts/voz do Gemini conforme o que engaja.

## ⚙️ Motor / infra
- [ ] **Reels: render fora do worker web** (quando escalar vídeo — hoje 2/dia ok).
- [ ] **Faxina** dos previews antigos em static/redacao (acumulam).
- [ ] **Redirect do www** (quem digita sem www não entra) — config de domínio.
- [ ] Monitorar **saldo Gemini** (R$60 pré-pago, chave dedicada do Rádio).

## 🔮 Futuro (marcos)
- [ ] Nano Banana (IA imagem) só pra **conteúdo leve** (se voltar) — off por ora.
- [ ] **10k:** ligar vídeo pesado.
- [ ] **100k:** monetização (publi + divulgação + funil 4kitem).

---

## 📜 Histórico (o que já melhorou — pra ver a evolução)
- Redação web (/admin/redacao) no ar.
- Autopost escrevendo com Gemini (híbrido + Groq backup).
- CTA mudou pra engajamento in-feed.
- Reels 1→2/dia.
- Nano Banana testado e desligado (não serve p/ notícia).
- fotobusca (foto real da gêmea, com crédito).

> Regra do kaizen: **sempre adicionar aqui** o que surgir, **sempre tirar 1-2** por sessão,
> e **mover pro histórico** o que for feito. O motor melhora um pouquinho todo dia.
