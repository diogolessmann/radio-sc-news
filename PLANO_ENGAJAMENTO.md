# 🎮 PLANO MOTOR DE BRINCADEIRA — Enquetes & Jogos (Rádio SC News)

> Transformar AUDIÊNCIA (que assiste) em COMUNIDADE (que joga junto). Brincar = comentário +
> marcação + retorno = exatamente o que o algoritmo premia → conserta o vazamento de engajamento
> E traz mais alcance. Página que a cidade BRINCA junto vira "A página do Vale".

---

## 🧱 A REALIDADE TÉCNICA (2 trilhas)
A API do Instagram **NÃO** posta figurinha interativa (enquete/quiz/caixinha) no Stories.
Então o motor trabalha em 2 trilhas:

| Trilha | O que | Automatiza? |
|--------|-------|-------------|
| **A — FEED (comentário)** | Palpite do Vale, Diz Aí Vale A/B, enquete "vota A ou B nos comentários" | ✅ 100% pelo motor |
| **B — STORIES (figurinha nativa)** | enquete/quiz/caixinha — o ímã do algoritmo | ⚠️ o motor GERA o card+pergunta, o dono põe a figurinha (30s) |

**Regra de ouro de toda enquete** (já validada): *"dois amigos brigariam por isso? alguém marcaria outro pra provar que tá certo?"* Se não → não posta. Sem política partidária, sem crime.

---

## 🗺️ AS PEÇAS (o que já temos × o que falta)
- ✅ `palpite.py` — card "QUEM LEVA?" (vota) FEITO.
- ✅ `comunidade.py` — "Diz Aí, Vale" (pergunta semanal) FEITO.
- ✅ `sponsors.py` — base pro "Palpite Premiado por patrocinador".
- ✅ Loop de Insights — pra medir qual brincadeira bomba.
- ⏳ FALTA: revelação/resultado, banco de enquetes, modo A/B, Hall da Fama, Stories de apoio, dados.

---

## 🔥 FASE 1 — BANCO DE ENQUETES (a munição)
`enquetes.py`: banco curado de dezenas de enquetes nos 6 tipos que bombam, cada uma passando na
régua, dividido em **Story (manual)** e **Feed (auto)**, com rotação (não repete).
- 6 tipos: rixa boa · opinião sobre notícia real · decisão da comunidade · orgulho/identidade ·
  palpite · quiz de conhecimento local.
- Por cidade quando fizer sentido ("o que SÓ quem é de Schroeder entende?").
- Função `proxima(tipo, surface)` → devolve a próxima enquete não-usada.
- **Feito quando:** dá pra puxar uma enquete boa de qualquer tipo, sem repetir.

## 🏆 FASE 2 — PALPITE DO VALE COMPLETO (vota → revela → Hall da Fama)
O loop do "EU FALEI". Extensão do `palpite.py`:
- Tabela `palpites(id, evento, opcao_a, opcao_b, data_evento, resultado, posted_vota, posted_revela)`.
- **Card VOTA** (já existe) + **Card REVELA** ("DEU PORTUGAL 🇵🇹 — quem votou A, ACERTOU! Joga o
  print, campeões do Vale 👇").
- `/admin/palpite`: cria o palpite + depois do evento informa o **RESULTADO** (fato verificado — IA
  NUNCA chuta placar; entra na mão ou de feed esportivo confiável).
- Scheduler: posta o VOTA na véspera/manhã; quando o resultado é setado, posta a REVELA.
- **Feito quando:** crio um palpite, posta o vota, informo o resultado, posta a revela sozinho.

## 🅰️🅱️ FASE 3 — "DIZ AÍ, VALE" MODO A/B
Turbinar `comunidade.py`: além da pergunta aberta, **opção binária A/B** ("vota A ou B nos
comentários") — mais fácil de votar = mais gente joga. Reusa o card de pergunta + 2 opções.
- **Feito quando:** o Diz Aí Vale sai como enquete A/B do banco (Fase 1).

## 📲 FASE 4 — STORIES DE ENQUETE (apoio ao manual)
O motor gera o **card de fundo + a pergunta pronta** (do banco) pra o dono só colar a figurinha
nativa no app. Um lembrete diário/semanal com a enquete do dia já montada.
- **Feito quando:** todo dia tem 1 enquete de Story pronta pra postar em 30s.

## 🎖️ FASE 5 — GAMIFICAÇÃO + MONETIZAÇÃO
- **Hall da Fama:** post recorrente que celebra os que acertaram ("os campeões do palpite da
  semana"). v1 social (a galera joga o print); evoluir pra ranking depois.
- **💰 PALPITE PREMIADO POR PATROCINADOR:** comércio dá um brinde (café/pizza) pro vencedor da
  semana → engaja + valor pro patrocinador + leva gente na loja. Liga no `sponsors.py`
  ("Palpite do Vale apresentado por X · prêmio cortesia da Padaria Y").
- **Streaks/ranking** (futuro): exige rastrear quem votou certo (parse de comentário) — fica pra
  quando valer o esforço.
- **Feito quando:** 1 Hall da Fama postado + 1 palpite com prêmio de patrocinador.

## 📈 FASE 6 — MEDIR E APRENDER (fecha com o Insights)
- O Loop de Insights marca os posts de brincadeira → relatório "qual TIPO de enquete mais engaja"
  e "qual cidade mais joga" no `/admin/saude`.
- Dobra a aposta no que o Vale ama jogar. Mata o que é tosco.
- **Feito quando:** o /admin/saude mostra o ranking de engajamento por tipo de brincadeira.

---

## 🧭 ORDEM DE EXECUÇÃO
1. **FASE 2 (Palpite completo)** — já tem o card vota + o jogo Portugal x Congo estreando; fechar o
   loop (revela + admin + tabela) é o maior impacto imediato.
2. **FASE 1 (Banco de Enquetes)** — a munição que abastece tudo.
3. **FASE 3 (Diz Aí A/B)** — turbina o que já roda.
4. **FASE 4 (Stories)** + **FASE 5 (gamificação/monetização)** + **FASE 6 (medir)**.

## 🛡️ GUARDRAILS
- Régua em TODA enquete (briga de amigo? sim/não). Sem política partidária, sem crime.
- FATO (placar/data) é SEMPRE conferido — IA dá o tom, nunca inventa (lição do Portugal x Congo).
- Reusa o motor (publish_single / publish_images / comunidade / sponsors / Insights). Zero dep nova.
- Validar nas 4 cidades (Jaraguá/Schroeder/Guaramirim/Joinville): medir engajamento por cidade →
  prova do modelo antes de replicar.
