# 📻 MEGACONTEXTO + ULTRAPLAN — Rádio SC News
> Documento para revisão externa (ex.: outra IA / Fable). **Autocontido:** quem lê isto não tem outro contexto. Gerado em 12/jul/2026 a partir de um mapeamento do código-fonte (6 agentes leram o motor inteiro) + dados reais do painel + histórico do projeto.

---

## 0. TL;DR (pra decidir em 30 segundos)
- **Rádio SC News** = portal de notícias hiperlocal do **Norte de Santa Catarina** (Flask + SQLite) + um **motor que gera e posta sozinho** no Instagram/Facebook (carrossel, story, reels). No ar, no Railway.
- **A distribuição FUNCIONA:** ~**1,4 milhão de views/mês** no Instagram, ~7,7k seguidores, 61% do alcance vem de NÃO-seguidores (viral).
- **O gargalo NÃO é produção nem alcance — é CONVERSÃO/RECEITA.** A infra de monetização está construída (planos, página /anuncie, selo de patrocinador), mas **R$0 de receita recorrente fechada.**
- **O motor já aprende** (LEARN_ON=1 há 1 mês) e o dado diz claramente: **clima é o tema nº1, Jaraguá a cidade nº1, Reels rende 2x o carrossel, esporte nacional é buraco negro.**
- **Nesta sessão** construímos 3 melhorias (ainda não deployadas): clima "passa-tudo", regional com janela maior, e uma **camada de VISÃO IA anti-processo** (uma IA barata que OLHA a foto antes de publicar).

---

## 1. O QUE É — produto, números, o negócio

**Produto:** notícia hiperlocal do Norte de SC (Schroeder, Jaraguá do Sul, Guaramirim, Corupá, Joinville) reescrita no tom "TikTok" (gancho forte, sem sensacionalismo) e distribuída de forma automática. Marca: navio/rádio vermelho + dourado.

**Números (reais, do painel):**
- ~1,4 mi views/mês · ~7,7k seguidores · 61% viral (não-seguidores)
- ~26 posts/dia de conteúdo (183 em 7 dias)
- Alcance médio por post: 300–2.500 dependendo do tema

**A tese de negócio (dono, fundador solo):** *"quem é visto é lembrado"* — distribuição é a alavanca. O Insta é o único canal que abre portas (site quase ninguém acessa; SaaS/serviços não vendem sozinhos). **Modelo "chinês 2.0":** copiar o provado e melhorar, não reinventar. **"Menos é mais":** feito pro leigo, 1 ação óbvia por tela.

**A verdade dura:** 1,4M de views com ~0 conversão. Multiplicar view sem resolver conversão = multiplicar zero. **O trabalho nº1 não é mais alcance — é transformar alcance em (a) seguidor e (b) receita.**

---

## 2. ARQUITETURA DO MOTOR — os 6 subsistemas

Fluxo macro: **Coleta (RSS) → Escrita por IA → Banco (SQLite) → Distribuição/Agendador → Imagem (cascata) → Postagem (Meta Graph) → Insights → Aprendizado**. Roda tudo dentro de 1 gunicorn (1 worker + 8 threads) com um APScheduler in-process. Só publica com `SOCIAL_AUTOPOST=1`.

### 2.1 Coleta & Fontes (`scraper.py`, `geo.py`)
- Lê **~28 feeds RSS fixos** (G1 SC/Norte, ND Mais por cidade, OCP, Rádio 105/Nossa FM/RBN, Diário da Jaraguá, JDV, SchPost + /segurança, Notícias Corupá, Prefeitura de Schroeder, Câmara de Jaraguá, Joinville Notícias, GE/Gazeta/Lance de esporte).
- **A cada 60 min** (30 min em produção real via wsgi). Coleta de emergência se o banco tem <10 notícias.
- **Cidade** = campo do feed OU `detect_city()` por palavra-chave (default "Santa Catarina"). **Categoria** = `detect_category()` por palavra inteira (default "geral"). **Ambas são REGRA, não IA.**
- **Dedup na coleta:** por link (UNIQUE) + por conteúdo (overlap de stems ≥0.6, janela 3 dias).
- **Enriquecimento:** puxa foto (og:image) e corpo da matéria quando o RSS vem raso.
- **Fontes com FOTO bloqueada** (litigiosas): OCP e Portal de Schroeder → usa só o TEXTO (fato é livre), descarta a foto. Config: `IMG_BLOCK_DOMAINS`.
- **O filtro "Norte de SC" NÃO roda na coleta — roda na POSTAGEM** (`pick_next`). O scraper ingere tudo de SC.

### 2.2 Escrita por IA & Voz (`cerebro.py`, `scraper._reescreve`, `tts_engine.py`)
- **`cerebro.py` = roteador de 3 IAs** (HTTP puro): **Gemini** (padrão, `gemini-2.5-flash`) → **Groq** (volume, grátis) → **fallback local** que nunca quebra.
- **A reescrita acontece na COLETA:** ao salvar, `scraper._reescreve()` gera `title_own`/`resumo_own` (e `materia_own` pra SEO) no tom da Rádio. O site e o Insta sempre preferem o texto NOSSO.
- **Tom da marca vive num único prompt** ("editor da Rádio SC News, estilo TikTok, gancho forte, proibido inventar número/data").
- **Voz (TTS):** Reels narram com **Gemini TTS grátis** (voz Charon); o player do site usa **ElevenLabs pago**.
- ⚠️ **Fail-open:** se a IA cair, o texto cai no ORIGINAL da fonte — o que **remove a proteção anti-strike (texto próprio) sem avisar.**

### 2.3 Distribuição, Cadência, Dedup, Aprendizado (`distribuidor.py`, `scheduler.py`, `placar.py`, `insights.py`)
- **Baseline diário (autopost ON): 7 posts** → Bom dia Vale 7h + Notícia 12h e 18h + Reels 9h/13h/16h/19h.
- **Event-driven:** Plantão urgente a cada 20 min (1/rodada) + **[NOVO] Clima passa-tudo a cada 20 min** (até 5/rodada).
- **Cadência da notícia principal é APERTADA: só 2/dia (12h/18h).** Por isso a maioria das matérias do site nunca vai pro Insta.
- **Dedup semântico** (`_mesmo_fato`): vetos (cidade/rodovia diferentes) + overlap ≥0.45 + fingerprint evento:cidade:dia. `mark_cluster` segura TODAS as irmãs do mesmo fato após postar (nasceu da dor de postar 2x).
- **Fusível:** `POSTS_MAX_DIA=30` em janela rolante de 24h (Meta limita ~100/24h).
- **Aprendizado (`LEARN_ON=1`, ligado há 1 mês):** `_ranqueia_aprendido` reordena o `pick_next` pelo Placar (categoria + 0,5·cidade), com trava 80/20 (20% explora). **Score do Placar = (saves·3 + shares·4 + coment·2) / alcance · 1000.**
- **Medição:** `insights.py` grava alcance/saves/seguidores por post (`post_insights`) e a série diária (`conta_dia`).

### 2.4 Imagem — a cascata de capa (`gen_instagram.slide_cover`)
**Ordem real da cascata** (o motor é **CEGO** — casa nome de arquivo/slug com palavra do título, nunca vê o pixel):
0. **Decisão anti-strike** (`ANTI_STRIKE=1` default): por padrão NÃO usa foto de terceiro. Se `_foto_sensivel` → força modo neutro SEMPRE.
1. **Foto da fonte** (só se categoria segura + não-sensível)
2. **[NOVO] VISÃO IA** (`visao_imagem.py`, Gemini Flash) — **a ÚNICA camada que OLHA o pixel**; derruba rosto/corpo/sangue/criança.
3. **Street View** (só quando o título cita um lugar: prefeitura/hospital/BR-280)
4. **Arsenal próprio** (`static/bg/`, **152 arquivos, ~49 slugs**) → carimba "Foto ilustrativa"
5. **fotobusca** [⚠️ OFF por default na cascata]
6. **Stock regional** [⚠️ pasta `static/stock` VAZIA = camada morta]
7. **Pexels** (só esporte/clima)
8. **Nano Banana / IA gera imagem** [⚠️ `NANOBANANA_ON=0` — EXISTE mas está DESLIGADO; exige billing]
9. **Card de marca** (fundo gradiente nosso — melhor que foto errada)

### 2.5 Segurança Editorial — a rede "anti-Chapecó" (6 camadas)
Nasceu de 2 incidentes reais: **(06/jul)** o motor postou a foto do ROSTO de uma vítima numa matéria de crime + texto afirmando culpa → **notificação jurídica** (calúnia + uso de imagem); **(07/jul)** mesma notícia postada 2x.
1. **Trava de foto por texto** (`_foto_sensivel`, regex em título+corpo): matéria sensível NUNCA usa foto de terceiro.
2. **Allowlist de categoria** (esporte/clima/economia/geral/turismo liberam foto real).
3. **[NOVO] VISÃO IA no pixel** — o buraco que o texto não pegava.
4. **Filtro jurídico** (`neutralizar_juridico`): troca afirmação de culpa por suspeita (determinístico, não-IA).
5. **Fila de revisão humana** (morte/sexual/suicídio/menor → `social_hold`, não auto-posta).
6. **Dedup anti-repost.**
- **2 testes-rede permanentes:** `test_seguranca.py` + `test_dedup.py` (exit 1 = brecha reaberta).
- ⚠️ **Assimetria documentada:** a trava de FOTO é larga (inclui roubo/tráfico/acidente), mas a FILA DE REVISÃO é estreita (só morte/sexual/menor). **Roubo/tráfico/acidente sem morte AUTO-POSTA** (com imagem neutra + texto suavizado).

### 2.6 Produtos & Monetização
- **7+ formatos autorais:** Bom dia Vale (hábito), Reels (alcance), O Vale em 60s (dormente), O Vale na Semana (autoridade), Enquete, Palpite (desligado — dava 0-107 views), Marcas (cross-sell: Despachante LIVE; DL Mobilidade e 4kitem dormentes até criar IG).
- **Monetização (infra pronta, receita ZERO):** Selo Patrocinador (diário no Bom dia) + Publipost "Parceiro do Vale" (sexta 19h) + página **/anuncie** com 3 planos: **Reportagem R$480 · Parceiro R$780/mês · Master R$1.290/mês**. Diferencial: alcance orgânico + impulsionamento pago na cidade do cliente.

---

## 3. O QUE O MOTOR APRENDEU (Placar, dado real, 245 posts)
| Dimensão | Vencedor | Perdedor |
|---|---|---|
| **Tema** | 🌧️ **CLIMA (nota 16)** · Saúde 10 · Geral 10 | Esporte **1.3** (com 53 posts!) · Economia 0 |
| **Cidade** | **Jaraguá (17.7)** · Guaramirim 7 · Schroeder 6 | Brasil/nacional **0.5** · Joinville 2.3 |
| **Formato** | 🎬 **Reels (12.2)** | Carrossel 5.8 *(mas 5x mais carrossel que reels)* |
| **Horário** | 🕛 **00h (32)** · 22h (18) | manhã/tarde fracos |

**Traduções diretas:**
1. **Clima domina** → validou a decisão de "clima passa-tudo".
2. **Local ganha, nacional afunda** → validou "regional libera mais fácil".
3. **Reels rende 2x mas é subusado** → deveria inverter a proporção.
4. **Esporte é buraco negro** → 34% do que o motor COLETA é esporte, e é a pior nota. Desperdício.
5. **Só ~13% do que o motor coleta é Norte de SC** → o funil de ENTRADA está torto (50% SC genérico, 30% Brasil).

---

## 4. O QUE CONSTRUÍMOS NESTA SESSÃO (testado, ainda LOCAL/não deployado)
1. 🌧️ **Clima passa-tudo** (`run_clima` + job de 20 min): todo evento de clima/chuva/alagamento recente vai pro ar, fora do funil de 2/dia — mantendo dedup + trava de sensível.
2. 📍 **Regional libera mais fácil** (`MAX_NEWS_AGE_DIAS_REGIONAL=6`): notícia do Norte de SC fica elegível 6 dias (vs 3), pra não envelhecer na fila.
3. 👁️ **Visão IA anti-Chapecó** (`visao_imagem.py`): Gemini Flash OLHA a foto da fonte antes de publicar; rosto/corpo/sangue → usa imagem nossa. Fail-open (não trava o post se a IA cair). Custo: centavos.
- Smoke test: py_compile OK, classificador/encoding/fail-open OK.

---

## 5. GAPS & RISCOS (o que o mapeamento achou de torto)
**🔴 Alto:**
- **Nano Banana (IA gera imagem) existe mas está DESLIGADO** (`NANOBANANA_ON=0`). É a peça que mataria a "Foto ilustrativa" — falta ligar + billing + guarda-corpos.
- **`static/stock` VAZIA** = uma camada inteira da cascata (stock regional) está morta. Perde-se um fallback bonito e 100% legal.
- **Produção HOJE não tem a camada de pixel anti-Chapecó** (a visão IA é desta sessão, não deployada).
- **Loop de dados / Insights:** o mapa sinalizou risco de `instagram_manage_insights` faltando (Placar=0 → LEARN_ON cego + sem prova pro patrocinador). **⚠️ MAS o Placar live tem 245 posts com dado** → parece OK; **confirmar a permissão em produção.**
- **Reels NÃO passam pelo fusível** `POSTS_MAX_DIA` — um loop no reels_job não seria contido.

**🟡 Médio:**
- **Material de venda inconsistente:** números (308k vs 1M vs 1,4M) e preços (KIT vs /anuncie) divergem. Precisa reconciliar antes de prospectar.
- **Placeholders em produção:** `WA_COMMUNITY` e `ANUNCIE_WHATSAPP` viram número fake se as env vars não estiverem setadas.
- **@handle inconsistente:** `@radiosc.news` (palpite) vs `@radioscnews` (resto).
- **`city=None` → default "Santa Catarina"** (fora de NORTE_SC) → matéria local sem a cidade no texto perde o rótulo de região.
- **Clima passa-tudo (5/20min) num temporal grande** pode gerar pico de volume — contido só pelo fusível de 30/24h.

**🟢 Higiene:**
- Código morto: `scraper.NORTE_SC_CITIES` (nunca usado); `radio_sc/scheduler.py` (cópia stale sem o clima). Slug `acidente_aviao` sem arquivo.
- Render de Reels (moviepy) roda no worker web — risco de travar quando escalar vídeo.

---

## 6. 🎯 O ULTRAPLAN (roadmap priorizado)

### FASE 0 — DEPLOY (hoje) ⚡
Subir as 3 mudanças testadas (clima + regional + **visão IA**). **Crítico: a produção não tem a camada de pixel anti-Chapecó.** No Railway confirmar `GEMINI_API_KEY` (✓ já tem) e `LEARN_ON=1` (✓ já tem).

### FASE 1 — QUALIDADE VISUAL (mata a "Foto ilustrativa") 🖼️
1. **Ligar a IA que gera imagem** (Nano Banana — já existe na cascata, `NANOBANANA_ON=1` + billing), como fallback **só** pra notícia SEM foto E SEM acervo. **3 guarda-corpos:** (a) só tema SEGURO (clima/economia/cultura/geral leve; crime/morte nunca gera); (b) rótulo "Arte IA"; (c) imagem TEMÁTICA/atmosférica, não a cena literal. Custo estimado ~R$50-65/mês, com teto (`NANOBANANA_LIMITE_DIA`).
2. **Popular `static/stock`** (camada morta) + adicionar imagem pro slug `acidente_aviao` + expandir o arsenal regional.

### FASE 2 — ALAVANCAR O QUE O DADO JÁ DIZ (grátis) 📈
1. **Mais Reels** (rendem 2x; hoje subusados) — aumentar `REELS_HORAS`.
2. **Menos esporte nacional** (34% da coleta, pior nota) — despriorizar/cortar feeds GE/Gazeta/Lance.
3. **Consertar o funil de entrada** (só 13% Norte de SC): mais fontes regionais + tratar `city=None`.

### FASE 3 — MONETIZAÇÃO (o gargalo REAL: 1,4M views, R$0) 💰
1. **Reconciliar o material de venda** (número + preço numa fonte única) + consertar placeholders.
2. **Provar 1-2 patrocinadores pagos** — bater na porta de comércios locais com o kit + a PROVA de alcance (o publipost já grava o `ig_media_id` pra mandar "teu post alcançou X mil").
3. **Garantir o loop de dados** (`instagram_manage_insights`) — é o que prova resultado e gera renovação.
4. **Fechar o buraco view→seguidor** (comerciante olha nº de seguidor, não view) — CTA de seguir mais forte, aproveitar o 61% viral.

### FASE 4 — EXPANSÃO (só depois de provar monetização) 🗺️
- **Clonar região** (Vale/Blumenau): mesmo motor, muda RSS + cidade. "1 motor, N marcas". NÃO nicho (esports/moda) — região mantém o moat local.

### PARALELO — Higiene técnica
Matar código morto · Reels no fusível · @handle único · render de vídeo fora do worker quando escalar.

---

## 7. ❓ PERGUNTAS PRO FABLE (o que eu quero de retorno)
1. **A ordem do ULTRAPLAN está certa?** Deploy → visual → alavancar dado → monetização → expansão. Ou a monetização deveria vir ANTES do visual (já que é o gargalo real)?
2. **A IA gera imagem por post** (~R$60/mês) — vale a pena AGORA, ou é polir o produto enquanto a receita é zero? (dilema clássico: qualidade vs distribuição/venda).
3. **Esporte:** cortar de vez os feeds nacionais (pior nota) ou manter "pra não esvaziar" o feed? O dado diz que dilui o hiperlocal.
4. **Cadência:** a notícia principal é só 2/dia. Aumentar (mais slots) ou a escassez é boa (curadoria > spam)?
5. **A camada de segurança** (6 travas + visão IA) está robusta o suficiente pra rodar 100% autônoma, dado o histórico de notificação jurídica? Onde você reforçaria?
6. **O maior risco cego** que você vê neste motor que a gente não listou?

---
*Fim do documento. Stack: Flask + SQLite + APScheduler no Railway; Gemini/Groq (texto+visão), ElevenLabs/Gemini TTS (voz), Meta Graph API (postagem). Fundador solo. Foco declarado: distribuição está resolvida, o próximo salto é CONVERSÃO/RECEITA.*
