# 🔧 KAIZEN — Melhoria contínua do motor (Rádio SC News + Instagram)
*Filosofia: 1% melhor por dia. Pequenas melhorias constantes > grandes reformas raras.
A cada sessão, a gente tira 1-2 itens daqui. Foco regional: Jaraguá · Schroeder · Guaramirim · Joinville.*

**Marco:** 600 → 2.297 seguidores (jun/2026). Snowball rolando.

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
- [ ] **Health check / métricas** — relatório simples: posts/dia, % com foto, % por cidade,
      erros no log, qual categoria bomba. Sem medir, kaizen é chute.

### 🔍 Da AUDITORIA 2 (skill auditing-instagram-engine, 17/jun/2026) — placar 8.2/10 ⬆️
- [ ] **🟡 alt_text (SEO de imagem)** — nenhum post manda `alt_text` (distribuidor.py:566,
      reels.py:162). IG indexa a descrição da imagem → alcance em busca. Add tema+cidade nos
      filhos do carrossel e no Reels. Fix barato, impacto direto em descoberta.
- [ ] **🟡 Abrir a narração do Reel com o gancho** — `_narration_script` começa "Cidade.
      Título." (reels.py:67). Os 3 primeiros seg decidem retenção → abrir com `flash_manchete`.
- [ ] **🟢 Enxugar BASE_TAGS** — hoje ~8-10 hashtags/post (gen_instagram.py:96); playbook 2026
      pede 3-5. Menos genérica, mais peso na local.
- [x] **OBSOLETO: cover_hook (gancho dourado)** — REMOVIDO na faxina de 17/jun. O TikTok mode
      (flash_manchete: notícia inteira em 2 linhas na capa) virou o gancho — melhor que o kicker.
- [ ] **(DONO) GEO_LOCATIONS no Railway** — pôr os 4 Place ids (Schroeder/Jaraguá/Guaramirim/
      Joinville) p/ garantir geotag certo, em vez de depender da busca automática.
- [ ] **(DONO) /anuncie 99k→113k** — atualizar o número de views na página de venda (app.py:995).

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
