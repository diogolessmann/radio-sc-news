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
- [ ] **Categoria errada** — vi "Caropreso convênio hospital" marcado como POLICIAL. Afinar
      detect_category (palavras-chave) — pequeno, mas melhora a precisão das pills.

### Medir pra guiar o kaizen
- [ ] **Health check / métricas** — relatório simples: posts/dia, % com foto, % por cidade,
      erros no log, qual categoria bomba. Sem medir, kaizen é chute.

### 🔍 Da AUDITORIA MONSTRO (skill auditing-instagram-engine, jun/2026) — placar 6.2/10
- [ ] **🔴 Geotag por cidade (location_id)** — hoje NENHUM post tem geotag (grep: 0 ocorrências).
      É o sinal nº1 de busca "perto de mim"/cidade e é o nosso maior eixo (hiperlocal). Buscar o
      FB Place id de cada cidade e mandar `location_id` no container IG. + front-load de keyword
      (cidade+tema) na 1ª linha da legenda (legenda virou conteúdo de busca em 2026).
- [ ] **🔴 Gancho VISUAL na capa** — slide_1 usa o título cru do RSS (gen_instagram.py:281). A capa
      é ~80% do peso. Gerar um gancho curto (reusa cerebro) pra capa, não só pra legenda.
- [ ] **🟡 Slide CTA visual desatualizado** — slide_cta ainda diz "LEIA E OUÇA / LINK NA BIO"
      (gen_instagram.py:334-371), contradizendo o CTA de engajamento da legenda. Trocar p/
      salvar/comentar/marcar.
- [ ] **🟡 Carrossel raso (4 slides)** — capa+2+CTA. Ótimo de 2026 é 8-10 slides. Aumentar
      profundidade (ex: slide "o que muda pra você", contexto) — carrossel é o formato de maior
      engajamento.
- [ ] **🔴 Render de Reels no worker web** — moviepy roda no gunicorn 1-worker/120s (reels.py:93).
      Risco de travar/timeout o site. Mover render p/ fora quando escalar vídeo (já no backlog infra).

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
