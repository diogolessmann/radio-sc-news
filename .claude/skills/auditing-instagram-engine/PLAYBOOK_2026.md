# Playbook Instagram 2026 — critérios de auditoria

Base de conhecimento do skill `auditing-instagram-engine`. Cada eixo abaixo traz **o que o
algoritmo de 2026 premia**, **o que pontua alto/baixo** e a **lição do dono** quando houver.

## Contents
- 1. Gancho / Hook
- 2. Formato (Reels × Carrossel)
- 3. Engajamento / CTA
- 4. SEO / Descoberta
- 5. Foto / Qualidade visual
- 6. Cadência / Consistência
- 7. Pesquisa / Conteúdo
- 8. Regionalidade / Voz
- 9. Segurança / Risco editorial
- 10. Métrica / Kaizen
- Constraints técnicas do projeto
- Lições já aprendidas (não relitigar)
- Fontes

---

## 1. Gancho / Hook
O **primeiro slide carrega ~80% do peso** do carrossel; nos Reels, os **3 primeiros segundos**
decidem retenção. O algoritmo de 2026 ranqueia por quem **para o scroll** e **desliza/assiste**.
- **Alto:** capa com promessa/curiosidade/tensão local ("O que muda pra quem mora em Schroeder"),
  número, pergunta, ou "antes/depois". Texto grande, legível no feed pequeno.
- **Baixo:** manchete seca repetida do RSS, título genérico de seção ("Notícias de SC"),
  capa sem foco visual.
- **Checar no código:** como o slide 1 / a primeira frase do Reel é montada (texto, tamanho,
  se reusa só o `title` cru ou se há um gancho gerado).

## 2. Formato (Reels × Carrossel)
- **Reels = alcance** (alcançar gente nova). **Carrossel = retenção/engajamento** — é o formato
  de **maior taxa de engajamento de 2026** (~1.92%; imagem+vídeo no carrossel ~2.33%).
- **Mix recomendado p/ conta pequena (<10k):** tratar Reels como motor de alcance (2–3/semana
  bons > 7 medíocres) + 1–2 carrosséis de alto valor p/ aprofundar com quem já segue.
- **Carrossel:** 8–10 slides é o ponto ótimo; cada slide tem que "puxar" o próximo.
- **Checar:** quantidade/cadência de Reels, nº de slides do carrossel, se há vídeo no mix.

## 3. Engajamento / CTA
**Saves + shares + comments > likes.** Share = sinal mais forte de valor real → mais alcance.
- **Alto:** CTA que pede **salvar** ("guarda pra depois"), **marcar** alguém ("marca quem é de
  Guaramirim"), **comentar** (pergunta no fim), **compartilhar no story**. O post tem que **se
  bastar** no feed — ninguém sai pra clicar em link.
- **Baixo:** "acesse o site", "link na bio" como CTA principal; nenhum pedido de interação.
- **Checar:** o texto do CTA na legenda e no slide final.

## 4. SEO / Descoberta
Instagram virou buscador. **Keywords na legenda > hashtags** (Google/Bing indexam legendas).
- **Alto:** legenda conversacional com os termos que a pessoa busca ("obras na BR-280 em
  Jaraguá do Sul"), **alt text descritivo** com tema + cidade, **location tag** (sinal nº 1 pra
  buscas "perto de mim"/cidade), **3–5 hashtags** hiperlocais/branding (não 30).
- **Baixo:** sem keywords no corpo, sem alt text, sem geotag, enxurrada de hashtag genérica.
- **Checar:** se a legenda inclui cidade+tema em texto corrido; se há alt text; se há location;
  contagem/escolha de hashtags.

## 5. Foto / Qualidade visual
Foto **real** > arte de IA para **notícia dura** (lição do dono, ver abaixo). Cascata de fallback
para nunca postar card feio nem foto errada.
- **Alto:** foto real da matéria (RSS/og:image) → foto da gêmea com crédito → foto regional da
  cidade → card de marca limpo. Texto legível (gradiente), marca consistente, crédito quando devido.
- **Baixo:** IA "storybook" em notícia séria; foto errada (matching frouxo); card ilegível.
- **Checar:** a ordem da cascata de foto, o matching (estrito?), legibilidade/contraste, crédito.

## 6. Cadência / Consistência
**Qualidade consistente > volume.** 3 Reels bons/semana batem 7 fracos.
- **Alto:** horários fixos previsíveis, frequência sustentável, render de vídeo **fora** do worker
  web (não travar o site), dedup pra não repetir assunto.
- **Baixo:** rajada irregular, render pesado no processo web (timeout), repetição de pauta.
- **Checar:** o scheduler (horários, frequência), onde o vídeo renderiza, blindagem de duplicata.

## 7. Pesquisa / Conteúdo
Divisão de trabalho 2026: **IA coleta/rascunha/detecta tendência; humano decide o sensível.**
- **Alto:** coleta multi-fonte, **dedup** por similaridade, detecção de **urgência/tendência**,
  **threshold de confiança** (não publica automático abaixo dele), **revisão humana** p/ temas
  sensíveis, enriquecimento (buscar foto/mais info em outras fontes).
- **Baixo:** fonte única, sem dedup (repete), publica qualquer coisa sem filtro.
- **Checar:** fontes, lógica de dedup, fila de revisão, filtro de sensível, enriquecimento.

## 8. Regionalidade / Voz
Hiperlocal é o diferencial — **prioriza as 4 cidades** (Jaraguá do Sul, Schroeder, Guaramirim,
Joinville) e fala como vizinho, não como agência.
- **Alto:** prioriza/realça cidade na escolha e na arte; voz local calorosa e consistente;
  geotag e menção da cidade.
- **Baixo:** trata tudo como "SC" genérico; voz robótica/variável.
- **Checar:** priorização por cidade no código, pills/labels de cidade, tom dos textos da IA.

## 9. Segurança / Risco editorial
- **Alto:** filtro editorial (regex de morte/crime/menor/sexual → segura p/ revisão), redação
  anti-processo (atribuição em pauta política, cuidado com valores R$), **zero foto falsa**
  apresentada como real, **nenhum segredo/token vazado** no código/repo.
- **Baixo:** posta tema sensível direto; afirma fato sem atribuição; fake visual; .env commitado.
- **Checar:** o filtro de temas, o revisor, e se há credencial em texto puro (FLAGAR, não imprimir).

## 10. Métrica / Kaizen
**Sem medir, kaizen é chute.** O motor tem que reportar o básico pra guiar a melhoria.
- **Alto:** health check com posts/dia, % com foto, % por cidade, erros no log, categoria que
  bomba; backlog vivo (KAIZEN.md) com 1–2 itens fechados por sessão.
- **Baixo:** nenhuma métrica; decisões no achismo.
- **Checar:** existe relatório/contador? Existe KAIZEN.md sendo usado?

---

## Constraints técnicas do projeto (respeitar nas recomendações)
- **Railway, deploy via push na main**, gunicorn 1 worker, timeout ~120s. Render de vídeo no
  worker web tem que ser modesto.
- **ZERO SDK novo** — IA é toda via HTTP `requests` (Groq/Gemini/Claude). Não recomendar instalar
  dependência pesada sem necessidade real.
- **Trava de segurança:** só posta de verdade com `SOCIAL_AUTOPOST=1` + tokens Meta presentes.
- **Gemini 2.5 é "thinking"** → mandar `thinkingConfig.thinkingBudget=0` p/ texto.
- Preferir fixes **grátis** e **sem dependência** (a régua do projeto).

## Lições já aprendidas (FLAGAR se violado, NÃO relitigar)
- **VOLUME é a estratégia validada desta conta (decisão do dono, jul/2026):** ~10 posts/dia
  levaram de 600 seguidores a 842 mil views/30d. Para conta de NOTÍCIA LOCAL (plantão/utilidade),
  "mais é mais" — a regra genérica "3 Reels bons > 7 medíocres" NÃO se aplica aqui. Não recomendar
  reduzir cadência nem teto editorial; o POSTS_MAX_DIA=30 existente é só fusível anti-bug
  (job em loop), nunca freio de pauta.
- **IA de imagem (Nano Banana) está OFF para notícia dura** — o dono testou ao vivo e não gostou
  (ilustrações genéricas "storybook" que não casam com a notícia). Módulo fica pronto, só
  desligado. Serviria só p/ conteúdo leve/aspiracional. **Não recomendar religar p/ hard news.**
- **CTA já virou engajamento in-feed** (salvar/marcar/comentar) em vez de "vá ao site" — manter.
- **Foto real é a estratégia** (cascata og:image → fotobusca com crédito → stock regional → card).
- **Matching de foto tem que ser ESTRITO** (já deu falso-positivo com matching frouxo).

## Fontes (pesquisa jun/2026)
- [Later — Instagram algorithm 2026](https://later.com/blog/how-instagram-algorithm-works/)
- [TrueFuture Media — Reach 2026: Reels, Carousels, Caption SEO](https://www.truefuturemedia.com/articles/instagram-reach-2026-algorithm-reels-carousels-caption-seo)
- [Marketing Agent — Carousel strategy 2026](https://marketingagent.blog/2026/01/03/mastering-instagram-carousel-strategy-in-2026-the-algorithm-demands-swipes-not-just-scrolls/)
- [CreatorFlow — Carousel best practices](https://creatorflow.so/blog/instagram-carousel-posts-guide/)
- [Later — Instagram SEO 2026](https://later.com/blog/instagram-seo/)
- [SocialRealtr — Keywords replace hashtags 2026](https://socialrealtr.com/the-2026-instagram-update-that-changes-everything-keywords-replace-hashtags/)
- [Reuters Institute — Journalism/tech trends 2026](https://reutersinstitute.politics.ox.ac.uk/journalism-media-and-technology-trends-and-predictions-2026)
- [CallSphere — Agentic AI in journalism (human-in-the-loop, confidence thresholds)](https://callsphere.ai/blog/agentic-ai-automated-journalism-news-generation)
- [Anthropic — Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
