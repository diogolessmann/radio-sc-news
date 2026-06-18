# 🗺️ PLANO MESTRE — Rádio SC News

Documento único pra parar a bagunça. Tudo organizado por PILAR.
Status: ✅ feito · 🔨 fazendo agora · ⏳ próximo · 🔴 risco aberto · 👤 ação do dono

> Princípio-mãe: **fato livre + NOSSO texto + NOSSA imagem.** Nunca foto nem texto de terceiro.
> Foco: Jaraguá do Sul · Schroeder · Guaramirim · Joinville · Corupá.

---

## 🖼️ PILAR 1 — IMAGEM (nunca foto de terceiro)
Cascata final: **foto do admin → NOSSA imagem (arsenal) → Street View/mapa → card de marca**.

- ✅ Card de marca quando não há foto (acabou foto gringa do Pexels sem nexo)
- ✅ Street View + mapa do Google (foto real do local, layout foto+faixa legal) — chave no ar
- ✅ Arsenal próprio `static/bg/` (escolhe por situação > cidade > categoria)
- ✅ Bloqueio de imagem de fonte litigiosa (OCP + Portal de Schroeder/Gabriel). G1 mantido.
- ⏳👤 Gerar as imagens do arsenal no Nano Banana (textless) e salvar em `static/bg/`
- ⏳👤 Validar o Street View num post real (mandar print)

## ✍️ PILAR 2 — TEXTO (sempre nosso, com emoção)
- ✅ Insta já reescreve (Motor de Emoção)
- 🔨 **Site passa a mostrar NOSSO texto** (reescrita na coleta → `title_own`/`resumo_own`)
- ⏳ (opcional) Insta usar o mesmo texto guardado, pra ficar 100% igual ao site
- ⏳ Áudio do site narrar o nosso texto também

## 🌐 PILAR 3 — SITE (radioscnews.com.br)
- ✅ Não mostra mais imagem de OCP/Schroeder
- 🔨 Mostra o nosso texto (junto do Pilar 2)
- ⏳ Decidir imagem do site sem foto própria (hoje: G1 fica; resto cai p/ card?) — alinhar

## 📱 PILAR 4 — INSTAGRAM
- ✅ Modo TikTok (notícia em 2 linhas), CTA de engajamento (salva/comenta/marca)
- ✅ alt_text (SEO de imagem), gancho na narração do Reel, hashtags enxutas
- ✅ Anti-strike total (nunca usa foto da fonte) + nova cascata de imagem
- ⏳👤 Validar Street View no 1º post

## 🛡️ PILAR 5 — EDITORIAL / SEGURANÇA
- ✅ **Filtro de morte/tragédia blindado** (morre/morreu/morrer/tragédia/fatal/"perdeu a vida" → segura p/ revisão; não casa "morro"=monte)
- ✅ **Corta notícia de fora da região** (Araranguá/Seara/Gaspar/Blumenau… fora do autopost; genérico SC e esporte ficam)
- ✅ `.env` fora do git · `_mask()` esconde chave dos logs · trava SOCIAL_AUTOPOST

## 💰 PILAR 6 — MONETIZAÇÃO
- ✅ Página `/anuncie` (113k views) + material de venda pronto (imagens promo)
- ⏳👤 Vender o 1º patrocinador local · cadastrar em `/admin/patrocinadores`

## 📡 PILAR 7 — FONTES / CONTEÚDO
- ✅ 14 feeds regionais + esporte; dedup; enriquecimento de texto
- ⏳ Fontes oficiais (Prefeituras, PMSC, Bombeiros, Câmaras) = conteúdo + foto legal

---

## 🎯 ORDEM DE EXECUÇÃO (o que vem agora)
1. ✅ Texto nosso no site
2. ✅ Filtro de morte/tragédia
3. ✅ Cortar fora-de-região
4. 👤 **Arsenal de imagens** (você gera) + validar Street View
5. ⏳ Fontes oficiais (prefeitura/PM) — conteúdo + foto legal
6. ⏳ Áudio do site narrar o nosso texto · backfill do texto antigo

*Atualizar este arquivo a cada avanço. Detalhe técnico fica no KAIZEN.md.*
