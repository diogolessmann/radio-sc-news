# 🦖 PLANO GODZILLA — Rádio SC News (próxima sessão)

> Frankenstein → **Monstrão** (hoje, 15/jun/2026) → **GODZILLA** (amanhã).
> Hoje a gente fez a FÁBRICA produzir lindo. Amanhã ela vira VOLANTE (flywheel): aprende
> com cada post e gira sozinha. E começa a furar o teto da "notícia-commodity".

---

## 🎯 A tese (o pulo do gato)
1. **Fábrica → Volante:** hoje produzimos no escuro (medimos produção, não resultado). O
   Godzilla MEDE o que a audiência faz (alcance/saves/seguidor por post) e dobra no que funciona.
2. **Commodity → Comunidade:** notícia qualquer um agrega. O moat é a voz do Vale + a audiência
   virar conteúdo (UGC, enquete, franquia com nome/dia).
3. **Alugado → Próprio:** IG é terra alugada (risco de bloqueio). Canal WhatsApp + lista própria
   = terra nossa.

---

## 📍 ONDE PARAMOS (fim da sessão de 15/jun)
- Skill `auditing-instagram-engine` criada + auditoria (placar 6.2/10).
- **6 fixes no ar:** CTA engajamento · gancho sóbrio na capa · carrossel adaptativo (até 7 slides)
  · geotag por cidade (modo AUTOMÁTICO, GEO_LOCATIONS vazio) · `/admin/saude` · enriquecimento de
  texto (puxa corpo da matéria, fura 403 com _BROWSER_HEADERS).
- Cascata de foto completa (og:image → fotobusca → stock → card).
- Decisões travadas: IA de imagem OFF p/ notícia dura · geotag automático · não rotacionar chaves.
- 🔴 Risco aberto: render de Reels no worker web.

---

## ✅ FASE 1 — LOOP DE INSIGHTS — FEITA E NO AR (commit e8e683c, 16/jun)
> Salva ig_media_id no post · insights.py puxa reach/saved/shares · job 23h30 · bloco "Top posts"
> no /admin/saude. Quick win categoria também fechado (match por palavra inteira, 6/6). FALTA SÓ:
> os posts NOVOS rodarem na prod (autopost) p/ popular o painel. Detalhe original abaixo. ↓

## 🔥 FASE 1 — LOOP DE INSIGHTS (a pedrada — faz isso PRIMEIRO)
**Por que:** vale mais que os 6 fixes juntos. Sem saber o que performa, todo kaizen é chute.
Usa a Graph API que já temos (mesmo token), custo zero.

**1a. Capturar o media id no post (pré-requisito).**
- Hoje a gente posta e recebe o id de volta, mas joga fora. Salvar.
- Nova coluna em `news`: `ig_media_id` (e `ig_permalink` opcional). Preencher em
  `process_one`/`make_reel_for` no sucesso (o retorno de `media_publish` traz o `id`).

**1b. Puxar os insights (novo `insights.py`).**
- Mídia: `GET /{ig-media-id}/insights?metric=reach,saved,shares,likes,comments,total_interactions`
  (Reels: `plays`/`ig_reels_video_view_total`, `ig_reels_avg_watch_time`).
- Conta: `GET /{ig-user-id}/insights?metric=follower_count,reach,profile_views&period=day`.
- Tabela `post_insights` (news_id, reach, saved, shares, interactions, coletado_em).
- Job no scheduler 1x/dia (ex: 23h) puxa insights dos posts dos últimos 3 dias (métrica amadurece).

**1c. Mostrar no `/admin/saude`.**
- Bloco "🏆 Top posts da semana" (por saves+shares), "por cidade que mais alcança",
  "melhor horário", "carrossel x Reels x foto". Aí a decisão de conteúdo vira DADO.

**Feito quando:** abro /admin/saude e vejo o ranking real de alcance/saves por post + cidade.

---

## ✅ FASE 2 — REELS QUE RETÉM — FEITA (commit d6aa2ef, 16/jun)
> `build_reel` sobrepõe legenda palavra-a-palavra (PIL desenha transparente, moviepy compõe —
> sem ImageMagick). Toggle REELS_CAPTIONS. Verificado no frame; render real só na Railway (moviepy
> 1.0.3, não está no venv local). FALTA ver num Reels real e julgar se fica busy demais sobre os
> slides de texto (se sim, REELS_CAPTIONS=0 ou simplificar os slides). Detalhe original abaixo ↓

## 🎬 FASE 2 — REELS QUE RETÉM (legenda na tela)
**Por que:** Reels é o motor de alcance; retenção nos 3s e legenda na tela é o sinal nº1.
- Adicionar legenda **palavra-por-palavra sincronizada** (estilo CapCut) no `reels.py` — já
  temos o texto narrado e o tempo do áudio; queimar as palavras no vídeo (moviepy TextClip).
- Capa do Reel com o **gancho** (reusar `cover_hook`) já no 1º frame.
- Trilha/áudio: manter edge-tts; avaliar música de fundo suave (royalty-free) em volume baixo.
**Feito quando:** o Reel sai com texto aparecendo conforme a narração.

---

## ✅ FASE 3 — AUDIÊNCIA PRÓPRIA — FEITA (commit 0cd812c, 16/jun)
> Legenda: engajamento in-feed 1º, depois Canal do WhatsApp em destaque com FOMO, site no rodapé.
> Slide final ganhou pill VERDE do WhatsApp ("recebe 1º · link na bio"). FALTA: story com figurinha
> de link (API de Stories não expõe link sticker fácil — fica manual por ora) + medir Canal manual.

## 📲 FASE 3 — AUDIÊNCIA PRÓPRIA (Canal WhatsApp como destino nº1)
**Por que:** terra nossa, à prova de bloqueio do IG.
- CTA do Canal WhatsApp mais forte e em TODO formato (carrossel, Reels, story).
- Story-capa com **figurinha de link** pro Canal.
- Medir crescimento do Canal (anotar manual por ora; sem API pública boa).
**Feito quando:** todo post empurra o Canal de forma clara e some o "link na bio" como CTA principal.

---

## 🤝 FASE 4 — ENGINE DE COMUNIDADE (fura o teto da commodity)
**Por que:** o que explode conta hiperlocal.
- **Franquias com nome + dia fixo:** "Quinta da Saudade" (foto antiga do Vale), "Sexta do Flagra"
  (trânsito/cotidiano), enquete semanal. Reaproveitar `gen_carrossel.py` (decks editoriais).
- **Stories interativos:** enquete / caixinha de pergunta / quiz (a figurinha que o algoritmo come).
- **UGC:** "manda teu flagra no direct" → fila de revisão → repost com crédito.
**Feito quando:** existe ao menos 1 franquia recorrente agendada no scheduler.

---

## 💰 FASE 5 — MONETIZAR CEDO (caixa financia o crescimento)
**Por que:** comércio local paga por alcance hiperlocal + confiança, não por 100k.
- Ativar de verdade o `sponsors.py` (Selo Patrocinador): 1 cota de teste com comércio do Vale.
- Pacote simples: selo no Bom dia + 1 publipost/semana + story. Preço de entrada baixo.
**Feito quando:** 1 patrocinador rodando (mesmo que de graça no teste) com selo aparecendo.

---

## ⚡ QUICK WINS (paralelos, baratos)
- [ ] **Categoria errada** — afinar `detect_category` (vi POLICIAL em pauta de hospital).
- [ ] **Cross-post Shorts/TikTok** — mesmo mp4 9:16 = alcance triplo de graça (manual ou API).
- [ ] **Render de Reels fora do worker web** 🔴 — tirar o moviepy do gunicorn (fila/processo à parte).
- [ ] **Backfill** das ~44 notícias antigas sem summary (rodar enriquecimento na PROD).

---

## 🔧 EXECUÇÃO DETALHADA — FASE 1 (passo a passo, pra mandar sem pensar)

**Passo 1 — migração do banco (salvar o id do Instagram).**
- Em `distribuidor.ensure_column`: adicionar colunas `ig_media_id TEXT` e `ig_permalink TEXT`.
- Em `process_one` (carrossel) e `make_reel_for` (reels): no sucesso do `media_publish`, o retorno
  traz `{"id": "<media-id>"}`. Salvar: `UPDATE news SET ig_media_id=? WHERE id=?`.
- ✅ Critério: depois de 1 post, a coluna `ig_media_id` vem preenchida.

**Passo 2 — `insights.py` (puxa as métricas).**
- `coletar_post(media_id, token)` → `GET {GRAPH}/{media_id}/insights`
  `?metric=reach,saved,shares,likes,comments,total_interactions&access_token=...`
  (Reels também: `ig_reels_video_view_total,ig_reels_avg_watch_time`). Devolve dict {metric: valor}.
- `coletar_conta(ig_user_id, token)` → `GET {GRAPH}/{ig_user_id}/insights`
  `?metric=follower_count,reach,profile_views&period=day`.
- Tabela nova `post_insights(news_id, reach, saved, shares, interactions, plays, coletado_em)`
  (criar no próprio módulo, `CREATE TABLE IF NOT EXISTS`).
- `atualizar_recentes(dias=3)`: pega news com `ig_media_id` dos últimos N dias, puxa e faz UPSERT.
- ✅ Critério: rodar `python insights.py` e ver linhas em `post_insights` com reach/saves reais.

**Passo 3 — job no scheduler.**
- `add_job(insights_job, CronTrigger(hour=23, minute=30))` → chama `insights.atualizar_recentes()`.
- Métrica amadurece com o tempo → puxar posts dos últimos 3 dias todo dia às 23h30.
- ✅ Critério: job aparece no `/admin` (status do scheduler) com próximo run.

**Passo 4 — mostrar no `/admin/saude`.**
- `metricas.coletar()` ganha: `top_posts` (ORDER BY saved+shares DESC LIMIT 5, JOIN news p/ título/cidade),
  `alcance_por_cidade`, `melhor_formato` (foto vs carrossel vs reels por média de saves).
- Bloco "🏆 Top da semana" + "📈 cidade que mais alcança" no template `_SAUDE_HTML`.
- ✅ Critério: abro /admin/saude e vejo o RANKING real — qual post/cidade/formato performou.

**Cuidados:** métricas de conta (`follower_count`) exigem a conta como Business/Creator (já é).
Alguns metrics mudam de nome por versão da API — se vier erro, logar o `error` da Graph e ajustar
o metric. Tudo via `requests` (zero dep). Não quebra post se o insights falhar (try/except + log).

---

## 🧭 ORDEM DE EXECUÇÃO AMANHÃ
1. **FASE 1 inteira** (Insights) — é a alavanca-mãe. Começa por 1a (salvar media id).
2. **Quick win categoria** (rápido, melhora o targeting que o Insights vai medir).
3. **FASE 2** (Reels legenda) se sobrar fôlego.
4. Resto vira backlog priorizado pelo que o Insights mostrar.

## 🛡️ GUARDRAILS (não esquecer)
- Railway, 1 worker, zero SDK novo (IA/HTTP via requests). Não quebrar deploy.
- Só posta com SOCIAL_AUTOPOST=1 + tokens. Filtro editorial mantém o sensível na revisão.
- Respeitar decisões: IA de imagem OFF p/ notícia dura · geotag automático · sem clickbait.
- Commitar só código (sem segredo, sem .env, sem previews de teste).
- Testar e MOSTRAR o resultado (o dono gosta de ver a imagem/o número).
