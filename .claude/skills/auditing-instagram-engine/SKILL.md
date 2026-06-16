---
name: auditing-instagram-engine
description: Audits and improves an automated Instagram content engine (RSS/news to carousel/Reels, captions, scheduling). Scores 10 growth dimensions against the 2026 algorithm with file:line evidence and concrete fixes. Use when reviewing, auditing, or improving the Instagram/social automation of a local-news or content project (e.g. Rádio SC News, marcas, Hype), or when the user asks to analyze posting quality, reach, hooks, captions, photos, or growth.
---

# Auditing an automated Instagram engine

Audit a code-driven Instagram pipeline (news/RSS → carousel + Reels + caption → post)
against the 2026 algorithm and return a scored report with **evidence (file:line)** and
**concrete, prioritized fixes** — not vague advice.

This skill encodes the 2026 Instagram playbook and the owner's hard-won lessons so the
audit is opinionated and regional-first. It is built for hyperlocal Brazilian news
(focus: Jaraguá do Sul · Schroeder · Guaramirim · Joinville) but works for any
content-automation account.

## When to use
- "Analisa/audita o motor do Instagram", "como melhorar o alcance/engajamento", "revisa os posts".
- Reviewing caption/hook/photo/scheduling code.
- Planning the next Kaizen improvements for the social engine.

## Boundaries
- **Audit and recommend — do not silently rewrite code.** Produce the report first; only
  edit when the user picks fixes to apply.
- **Never invent metrics.** If real numbers (reach, saves, follower delta) aren't available,
  say so and recommend instrumenting them — don't fabricate.
- **Respect the owner's settled decisions** (e.g. AI-generated images are OFF for hard news —
  see [PLAYBOOK_2026.md](PLAYBOOK_2026.md) §Lessons). Flag, don't relitigate.
- **Security:** never print secrets/tokens found in code or .env; flag the leak instead.

## The 10 dimensions (score each 0–10)
Full criteria + the 2026 sources are in [PLAYBOOK_2026.md](PLAYBOOK_2026.md). Summary:

1. **Gancho / Hook** — first slide & first 3s of Reels carry ~80% of the weight. Is there a real hook?
2. **Formato** — Reels for *reach*, carousels for *retention* (highest engagement format, 8–10 slides). Right mix?
3. **Engajamento / CTA** — saves + shares + comments beat likes. Does the CTA earn them (não "vá ao site")?
4. **SEO / Descoberta** — keywords in caption (> hashtags now), alt text, location tag, 3–5 hyperlocal hashtags.
5. **Foto / Qualidade visual** — real photo > AI for hard news; fallback cascade; legibility, brand, credit.
6. **Cadência / Consistência** — frequency, timing, quality-over-volume; render not blocking the web worker.
7. **Pesquisa / Conteúdo** — collection, dedup, trend/urgency detection, confidence threshold, human review for sensitive.
8. **Regionalidade / Voz** — hyperlocal focus (the 4 cities), consistent brand voice, location signals.
9. **Segurança / Risco editorial** — sensitive-topic filter, anti-process wording, no fake visuals, no leaked secrets.
10. **Métrica / Kaizen** — does it measure to steer? (posts/day, % with photo, % per city, what hits). No metrics = guessing.

## Audit workflow
Copy this checklist into your response and check off as you go:

```
Auditoria do Motor IG:
- [ ] 1. Mapear o pipeline (entrada→processamento→saída): quais arquivos fazem o quê
- [ ] 2. Ler os arquivos-chave do post (caption, slides, hook, scheduler, AI, foto)
- [ ] 3. Pontuar os 10 eixos (0–10) com EVIDÊNCIA file:line
- [ ] 4. Listar achados por severidade (🔴 crítico / 🟡 médio / 🟢 polish)
- [ ] 5. Top 5 fixes priorizados (impacto × esforço), com o trecho exato a mudar
- [ ] 6. Montar o relatório no formato do template
- [ ] 7. Atualizar KAIZEN.md com os itens novos (não duplicar)
```

**Step 1 — Map the pipeline.** Identify the entry (RSS/scraper), the processor (dedup, AI
summary/caption, filters), and the outputs (carousel image gen, Reels, caption, scheduler).
For Rádio SC News these are typically: `scraper.py`, `distribuidor.py`, `gen_instagram.py`,
`reels.py`, `marcas.py`, `bom_dia.py`, `scheduler.py`, `cerebro.py`, `fotobusca.py`,
`stockfoto.py`. Adapt to whatever exists.

**Step 2 — Read the key files.** Read the actual code that builds the caption, the first
slide/hook, the scheduler cadence, the AI routing, and the photo cascade. Quote real lines.

**Step 3 — Score each dimension** using the criteria in [PLAYBOOK_2026.md](PLAYBOOK_2026.md).
Every score MUST cite at least one `file:line` as evidence (good or bad). No evidence = don't score it; mark "não verificável".

**Step 4 — Findings by severity.** 🔴 hurts reach/engagement or is a legal/security risk ·
🟡 leaves growth on the table · 🟢 polish.

**Step 5 — Top 5 fixes.** Rank by impact × (1/effort). For each: the dimension, the exact
file:line, what to change, and the one-line "why it grows the account". Prefer free/zero-dependency
fixes (the engine runs on Railway with no SDKs — see PLAYBOOK §Constraints).

**Step 6 — Report.** Use [AUDIT_REPORT_TEMPLATE.md](AUDIT_REPORT_TEMPLATE.md).

**Step 7 — Feed Kaizen.** Add new actionable items to `KAIZEN.md` (the project's living
backlog), without duplicating what's already there. The philosophy is 1% better per session.

## Scoring guide
- **0–3** absent/counterproductive · **4–6** present but weak · **7–8** solid · **9–10** best-in-class for 2026.
- Be honest and specific. "CTA pede salvar+marcar no slide final (distribuidor.py:212) → 8/10"
  beats "engajamento ok". A low score with a concrete fix is more useful than a generous one.
