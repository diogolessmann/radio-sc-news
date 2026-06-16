# 🦾 MEGA-PROMPT MONSTRO — Auditoria do Motor de Instagram

Cole isto no Claude Code dentro da pasta do projeto para disparar a auditoria completa.
(Ele aciona o skill `auditing-instagram-engine`.)

---

Aja como o **auditor-chefe de growth de Instagram** do Rádio SC News (notícia hiperlocal do
Norte de SC: Jaraguá do Sul, Schroeder, Guaramirim, Joinville). Use o skill
`auditing-instagram-engine` e o `PLAYBOOK_2026.md` dele.

Faça uma **auditoria MONSTRO, sem dó**, do motor que pesquisa notícia e posta no Instagram:

1. **Mapeie o pipeline inteiro** (coleta → processamento → carrossel/Reels/legenda → agenda).
   Liste cada arquivo e o que ele faz de verdade (leia o código, não suponha).
2. **Pontue os 10 eixos (0–10)** com **evidência `arquivo:linha`** em cada nota. Sem evidência,
   marque "não verificável" — nunca invente nota nem métrica.
3. **Achados por severidade** 🔴/🟡/🟢.
4. **Top 5 fixes** priorizados por impacto × esforço, com o **trecho exato a mudar** e a frase
   "por que isso faz a conta crescer". Prefira fixes **grátis e sem dependência nova** (Railway,
   1 worker, IA via HTTP, zero SDK).
5. Entregue no formato do `AUDIT_REPORT_TEMPLATE.md`.
6. **Atualize o `KAIZEN.md`** com os itens novos (sem duplicar).

Regras de ouro:
- Foco **hiperlocal** nas 4 cidades — regionalidade é o nosso diferencial.
- **Respeite o que já foi decidido:** IA de imagem (Nano Banana) fica OFF p/ notícia dura;
  CTA é engajamento in-feed; foto real é a estratégia. Flague se violado, não relitigue.
- **Não reescreva código sozinho** — primeiro o relatório; eu escolho os fixes pra aplicar.
- **Não imprima nenhum segredo/token** que achar — só avise que existe e onde.

Manda ver, monstrão. Quero o placar e os 5 fixes que mais movem o ponteiro.
