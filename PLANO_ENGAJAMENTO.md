# 🎮 MOTOR DE BRINCADEIRA — v2.0 (Rádio SC News)

> Transformar quem ASSISTE em quem JOGA junto. Brincar = comentário + marcação + retorno =
> o que o algoritmo premia. Conserta o vazamento de engajamento E traz alcance.
> **v2.0 = o pulo de "enquete" pra "JOGO que a cidade não larga":** placar + amarrar na
> notícia + grade de programação + jogos copyright-safe.

---

## 🧠 A tese refinada (o que faltava no v1)
Enquete prende pela pergunta; **JOGO prende pelo PLACAR** (a chase). 4 peças que faltavam:
1. **PLACAR/score** — quem acerta vira "Mestre do Palpite do Vale", tem sequência, sobe no ranking. *Sem placar = enquete. Com placar = vício.*
2. **AMARRAR NA NOTÍCIA** — palpite sobre a obra/evento real = jornalismo, não enfeite (e fonte infinita).
3. **LOOP DE VOLTA** — vota → volta pra ver se ganhou (Stories "saiu o resultado", resposta auto "acertou!").
4. **GRADE DE PROGRAMAÇÃO** — dia fixo que a cidade decora (igual grade de TV).

## 🧱 2 trilhas
| Trilha | Automatiza? |
|--------|-------------|
| **FEED** (Palpite, Diz Aí A/B, Onde é Isso, "vota A ou B nos comentários") | ✅ 100% pelo motor |
| **STORIES** (figurinha enquete/quiz nativa — ímã do algoritmo) | ⚠️ motor gera o card, dono põe a figurinha (30s) |

---

## 📅 A GRADE DE PROGRAMAÇÃO (os jogos com nome + dia)
A cidade aprende o ritmo. Sugestão:
- **Seg/dia de jogo — 🏆 PALPITE DO VALE** (esporte ou evento): vota → conta votos reais → revela → placar.
- **Quarta — 🗳️ DIZ AÍ, VALE (modo A/B)**: opinião/rixa boa, fácil de votar.
- **Quinta — 🧠 QUIZ DA QUINTA** (Stories): "você sabia?" de conhecimento local (orgulho + ensina).
- **Sexta — 📍 ONDE É ISSO NO VALE?**: foto de um cantinho → "que lugar é esse? 1º acerta ganha shoutout".
- **Domingo — 🏅 CAMPEÃO DA SEMANA**: reconhece quem mais jogou/acertou (alimenta o placar).

---

## 🆕 OS JOGOS (detalhe)

### 🏆 Palpite do Vale (completo: vota → revela → placar)
- Tabela `palpites(id, evento, opcao_a, opcao_b, data_evento, resultado, posted_vota, posted_revela)`.
- Card VOTA (✅ existe) → **conta os comentários A vs B pela API** → Card REVELA com **% real**
  ("65% cravaram Portugal — e DEU PORTUGAL! campeões 👇").
- `/admin/palpite`: cria + confirma o **resultado em 1 clique** (FATO nunca pela IA).
- **Amarra na notícia:** todo fato incerto vira palpite (obra no prazo? recorde de público?).

### 📍 Onde é Isso no Vale? (a jogada de OURO — 3 problemas resolvidos)
- Foto de um lugar do Vale (cortada/zoom) → "que lugar é esse?".
- ✅ **engajamento** (corrida pra acertar) · ✅ **UGC** (galera manda fotos = conteúdo grátis) ·
  ✅ **copyright ZERO** (foto sua/da comunidade — mata o medo de strike) · ✅ **orgulho local**.
- Banco de fotos-mistério (reusa static/stock + envios) + card "QUE LUGAR É ESSE?" + revela depois.

### 🅰️🅱️ Diz Aí, Vale — modo A/B
- Turbinar comunidade.py: além da pergunta aberta, **opção binária** (mais fácil votar = mais joga).

### 🧠 Quiz da Quinta (Stories) + ❓ caixinha
- Motor gera a pergunta+card; dono põe a figurinha de quiz/enquete. Banco curado.

### 🏅 Campeão da Semana
- Post recorrente que celebra os campeões → vira o **placar/hall da fama** que a galera persegue.

---

## 🎖️ CAMADA DE GAMIFICAÇÃO (o vício)
- **Placar/título:** "Mestre do Palpite do Vale", sequência (streak), ranking.
- **v1 viável:** auto-contagem de votos (API) + reconhecimento manual dos campeões.
- **v2 (evoluir):** rastrear quem acerta (parse de comentário) → ranking real. Só quando valer o esforço.
- **Loop de volta:** resposta automática ao votante ("acertou! 👏") + Stories "saiu o resultado".

## 💰 MONETIZAÇÃO
- **Palpite Premiado por patrocinador** (liga no sponsors.py): comércio dá brinde pro campeão da
  semana = engaja + valor pro patrocinador + leva gente na loja. "Palpite apresentado por X".
- **Jogo patrocinado:** "Onde é Isso apresentado por [loja]" / prêmio cortesia.
- ⚖️ Se virar sorteio formal com prêmio → estruturar dentro da lei (regra de promoção/sorteio).

## 📈 MEDIR E APRENDER (fecha com o Insights)
- Insights marca os posts de jogo → "qual JOGO e qual CIDADE mais engaja" no /admin/saude.
- Auto-contagem de votos por opção (dado real). Dobra no que o Vale ama; mata o tosco.

---

## 🛡️ GUARDRAILS (cravados)
- **Régua** em TODA enquete ("dois amigos brigariam?") · sem política partidária, sem crime.
- **FATO sempre conferido** — IA dá o tom, NUNCA inventa placar/data (lição Portugal x Congo 😅).
- **Preferir jogos copyright-safe** (Onde é Isso, Quiz, Palpite com texto) — conteúdo 100% original.
- **Nunca enquadrar como aposta** (palpite é grátis, diversão).
- Reusa o motor todo (publish_single/images, comunidade, sponsors, Insights) — zero dependência nova.
- **Validar nas 4 cidades** (Jaraguá/Schroeder/Guaramirim/Joinville): medir engajamento por cidade =
  a prova antes de replicar.

## 🧭 ORDEM DE EXECUÇÃO (v2.0)
1. **📍 Onde é Isso no Vale?** — a jogada de ouro (engajamento + UGC + zero copyright). Começo seguro e forte.
2. **🏆 Palpite completo** (vota → conta votos → revela → /admin) — fecha o loop, estreia com jogo real.
3. **🅰️🅱️ Diz Aí A/B** + **🧠 Quiz da Quinta** + **🏅 Campeão da Semana** (a grade).
4. **🎖️ Placar/gamificação** + **💰 Palpite premiado** + **📈 medir**.
