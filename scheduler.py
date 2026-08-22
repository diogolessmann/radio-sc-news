"""
scheduler.py — Agendador de coleta automática de notícias
Rádio SC News
"""
import logging
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler = None


def _autopost_on():
    """Trava de seguranca: so publica sozinho quando SOCIAL_AUTOPOST=1 (e tokens Meta existem)."""
    return os.environ.get('SOCIAL_AUTOPOST', '0') == '1'


def bom_dia_job():
    """Gera o 'Bom dia, Vale' toda manha. Posta IG+FB se autopost ligado."""
    try:
        import bom_dia
        bom_dia.run(post=_autopost_on())
        logger.info("☀️ Bom dia Vale %s.", "gerado e POSTADO" if _autopost_on() else "gerado (preview)")
    except Exception as e:
        logger.error(f"❌ Bom dia Vale falhou: {e}")


def social_news_job():
    """Distribui a proxima noticia nas redes. Só age se autopost ligado."""
    if not _autopost_on():
        logger.info("📭 Autopost OFF — distribuicao de noticia pulada (modo seguro).")
        return
    try:
        import distribuidor
        # 📈 MAIS É MAIS (dono, 5/ago): posts por slot via env — NOTICIAS_POR_SLOT=4 com a
        # grade cheia de 15 slots ≈ 60 + urgente/clima/reels ≈ 80/dia. Default 1 = como era.
        _por_slot = int(os.environ.get("NOTICIAS_POR_SLOT", "1") or 1)
        r = distribuidor.run_once(post=True, limit=_por_slot)
        logger.info(f"📣 Distribuidor: {r['postadas']} postada(s). Erros: {r['erros']}")
    except Exception as e:
        logger.error(f"❌ Distribuidor falhou: {e}")


def reels_job():
    """Gera e posta 1 Reels (vídeo vertical narrado) por dia. Só age se autopost ligado."""
    if not _autopost_on():
        logger.info("📭 Autopost OFF — Reels pulado (modo seguro).")
        return
    try:
        import reels
        r = reels.run_reel(post=True, limit=1)
        logger.info(f"🎬 Reels: {r['postadas']} postado(s). Erros: {r['erros']} Seguradas: {r.get('seguradas')}")
    except Exception as e:
        logger.error(f"❌ Reels falhou: {e}")


def resumo_job():
    """🎙️ 'O Vale em 60 segundos' — Reels diário de resumo (3 notícias). DORMENTE até RESUMO_ON=1.
    Com RESUMO_ON=1 GERA todo dia pra revisão em /admin/resumo; só POSTA se RESUMO_POST=1 (+autopost).
    Assim o dono aprova os primeiros antes de ir ao ar. Render roda no worker — 1x/dia, horário calmo."""
    if os.environ.get('RESUMO_ON', '0').strip() != '1':
        return
    try:
        import resumo_dia
        quer_postar = _autopost_on() and os.environ.get('RESUMO_POST', '0').strip() == '1'
        r = resumo_dia.run(post=quer_postar)
        if r.get('ok'):
            logger.info("🎙️ Resumo do dia %s — %s",
                        "POSTADO" if r.get('postado') else "gerado (preview p/ revisão)", r.get('titulos'))
        else:
            logger.info("💤 Resumo do dia pulado — %s", r.get('motivo'))
    except Exception as e:
        logger.error(f"❌ Resumo do dia falhou: {e}")


def urgent_news_job():
    """Plantão: posta NA HORA notícia urgente recém-coletada. Só age se autopost ligado."""
    if not _autopost_on():
        return
    try:
        import distribuidor
        r = distribuidor.run_urgent(post=True, limit=1)
        if r['postadas'] or r['seguradas']:
            logger.info(f"⚡ URGENTE: {r['postadas']} postada(s) · seguradas: {r['seguradas']}")
    except Exception as e:
        logger.error(f"❌ Urgente falhou: {e}")


def tempo_pauta_job():
    """🌦️ Pauta diária de previsão own (30/jul): forecast real -> manchete-impacto pela IA
    ('PREPARE O CASACO' fez 36 mil; o genérico fazia 300). O passa-tudo de clima posta."""
    try:
        import tempo_pauta
        r = tempo_pauta.run()
        logger.info(f"🌦️ Pauta do tempo: {r}")
    except Exception as e:
        logger.error(f"❌ Pauta do tempo falhou: {e}")


def empresas_job():
    """🏭 Empresas do Vale (pedido do dono 27/jul): 1x/semana, matéria celebrando empresa da
    região (só Jaraguá/Guaramirim/Schroeder/Corupá). NUNCA auto-posta — vai pra fila /revisar
    e avisa o dono no zap. Também é funil de venda (a empresa vira lead do pacote)."""
    try:
        import empresas
        r = empresas.run()
        logger.info(f"🏭 Empresas do Vale: {r}")
    except Exception as e:
        logger.error(f"❌ Empresas do Vale falhou: {e}")


def promo_grupo_job():
    """📣 Propaganda fixa do Grupo DL (pedido do dono 4/ago): card + legenda apontando pra
    dldespachante.com.br toda SEXTA, DOMINGO e SEGUNDA 12h15. Arte pré-gerada em
    static/promo/ (trocar arte = trocar JPG). PROMO_GRUPO_ON=0 desliga."""
    try:
        import promo_grupo
        r = promo_grupo.run()
        logger.info(f"📣 Promo do grupo: {r}")
    except Exception as e:
        logger.error(f"❌ Promo do grupo falhou: {e}")


def versiculo_job():
    """🙏 Mensagem do dia (pedido do dono 27/jul): card devocional às 6h40 — versículo ARC
    universal + reflexão, série com identidade própria. Custo zero/dia. VERSICULO_ON=0 desliga."""
    try:
        import versiculo
        r = versiculo.run(post=True)
        logger.info(f"🙏 Versículo: {r}")
    except Exception as e:
        logger.error(f"❌ Versículo falhou: {e}")


def inspetor_job():
    """🔍 O INSPETOR (a 'Thais-bot'): revisa os posts do dia (imagem real + legenda via Graph)
    com o checklist do revisor de jornal e manda os SUSPEITOS no zap do dono (Evolution do
    Vigia). Não depende de autopost — revisa o que FOI ao ar. Fail-safe total."""
    try:
        import inspetor
        r = inspetor.run(enviar=True)
        logger.info(f"🔍 Inspetor: {r['auditados']} revisados, {r['suspeitos']} suspeito(s).")
    except Exception as e:
        logger.error(f"❌ Inspetor falhou: {e}")


def clima_news_job():
    """🌧️ Clima passa-tudo: posta todo evento de clima/chuva/alagamento recente (deduped + safety).
    Só age se autopost ligado."""
    if not _autopost_on():
        return
    try:
        import distribuidor
        r = distribuidor.run_clima(post=True)
        if r['postadas'] or r['seguradas']:
            logger.info(f"🌧️ CLIMA passa-tudo: {r['postadas']} postada(s) · seguradas: {r['seguradas']}")
    except Exception as e:
        logger.error(f"❌ Clima falhou: {e}")


def marca_job(brand_key):
    """Posta 1 carrossel (IG) + foto (FB) + Story da MARCA por dia.
    Só age se autopost ligado E se os tokens Meta daquela marca existirem.
    Se faltar token (ex: IG ainda não criado), PULA sem erro — assim DL/4kitem
    ativam sozinhos quando os tokens forem adicionados, sem mexer no código."""
    if not _autopost_on():
        logger.info("📭 Autopost OFF — marca '%s' pulada (modo seguro).", brand_key)
        return
    try:
        import marcas
        t = marcas.BRANDS.get(brand_key)
        if not t:
            logger.error("❌ Marca '%s' não existe em BRANDS.", brand_key)
            return
        token, ig_id, page_id = marcas._brand_tokens(t)
        # Marcas ig_only (DL/4kitem) não usam page_id — basta token + ig_id.
        falta = (not (token and ig_id)) if t.get("ig_only") else (not (token and ig_id and page_id))
        if falta:
            logger.info("⏭️ Marca '%s' sem tokens Meta ainda — pulada "
                        "(crie o IG + tokens p/ ativar automaticamente).", brand_key)
            return
        marcas.run(brand_key, post=True)
        logger.info("🏷️ Marca '%s' POSTADA (IG carrossel + FB + Story).", brand_key)
    except Exception as e:
        logger.error(f"❌ Marca '{brand_key}' falhou: {e}")


def insights_job():
    """Loop de Insights: puxa alcance/saves/seguidor real dos posts recentes (1x/dia).
    Não depende de autopost — lê métricas, não publica. Precisa dos tokens Meta."""
    try:
        import insights
        n = insights.atualizar_recentes()
        conta = insights.snapshot_conta()   # GRAVA seguidores/alcance do dia em conta_dia (serie temporal)
        logger.info(f"📈 Insights: {n} post(s) atualizado(s). Conta gravada: {conta}")
    except Exception as e:
        logger.error(f"❌ Insights falhou: {e}")


def vigia_job():
    """O VIGIA (dead-man switch): confere se a fábrica postou hoje; se não, manda ZAP pro
    dono via Evolution. Dormente até configurar EVOLUTION_URL/APIKEY/INSTANCE + VIGIA_ZAP."""
    try:
        import vigia
        if not vigia.ligado():
            return
        r = vigia.checar_dia()
        logger.info(f"👁️ Vigia: {r}")
    except Exception as e:
        logger.error(f"❌ Vigia falhou: {e}")


def vigia_semana_job():
    """Resumo semanal + BACKUP do banco no zap do dono (único backup fora do Railway)."""
    try:
        import vigia
        if not vigia.ligado():
            return
        r = vigia.resumo_semana()
        logger.info(f"👁️ Vigia semana: {r}")
    except Exception as e:
        logger.error(f"❌ Vigia semanal falhou: {e}")


def comunidade_job():
    """Franquia de COMUNIDADE ('Diz Aí, Vale' — pergunta da semana). Puxa comentário.
    Só posta se autopost ligado; senão gera só o preview."""
    try:
        import comunidade
        r = comunidade.run(post=_autopost_on())
        logger.info("🗣️ Comunidade '%s' %s — %s",
                    r['franquia'], "POSTADA" if r['postado'] else "preview", r['pergunta'])
    except Exception as e:
        logger.error(f"❌ Comunidade falhou: {e}")


def publipost_job():
    """Publipost do parceiro da semana (produto pago). Só posta se autopost ligado E houver
    parceiro ativo; senão gera preview / pula sem erro."""
    try:
        import sponsors
        r = sponsors.run_publipost(post=_autopost_on())
        if r.get("ok"):
            logger.info("💙 Publipost '%s' %s.", r["sponsor"],
                        "POSTADO" if r["postado"] else "preview")
        else:
            logger.info("💤 Publipost pulado — %s.", r.get("motivo"))
    except Exception as e:
        logger.error(f"❌ Publipost falhou: {e}")


def segue_job():
    """Post recorrente 'SEGUE a Rádio' (conversão view->seguidor). 2x/semana."""
    try:
        import segue
        r = segue.run(post=_autopost_on())
        logger.info("➕ SEGUE %s — %s", "POSTADO" if r.get("postado") else "preview/pulado",
                    r.get("motivo", "ok"))
    except Exception as e:
        logger.error(f"❌ SEGUE falhou: {e}")


def enquete_job():
    """Enquete do Vale (Story) — gera pergunta + opções + imagem 1x/dia. NÃO posta (o sticker de
    enquete é colado na mão no app; a Meta não deixa via API). Fica pronta em /admin/enquete."""
    try:
        import enquete
        r = enquete.run()
        logger.info("🗳️ Enquete do dia gerada: %s (%s / %s)", r.get("pergunta"), r.get("a"), r.get("b"))
    except Exception as e:
        logger.error(f"❌ Enquete falhou: {e}")


def curiosidade_job():
    """Curiosidade do Vale ('Você Sabia?' das cidades) — gera carrossel próprio 2x/semana pros dias
    fracos de notícia. NÃO auto-posta (conteúdo novo); fica pronto em /admin/curiosidade."""
    try:
        import curiosidades
        r = curiosidades.run()
        logger.info("🏛️ Curiosidade gerada: %s — %s", r.get("cidade"), r.get("gancho"))
    except Exception as e:
        logger.error(f"❌ Curiosidade falhou: {e}")


def retro_job():
    """🐇 'O Vale na Semana' — retrospectiva de DADOS (carrossel) todo domingo. Conteúdo 100% nosso
    do próprio banco. NÃO auto-posta (padrão Curiosidade): fica pronto em /admin/retro pro dono postar."""
    try:
        import retro_semana
        r = retro_semana.run()
        if r.get("ok"):
            logger.info("🐇 Retrospectiva da semana gerada: %s notícias · %s",
                        r["numeros"]["total"], r["numeros"]["cidade"])
        else:
            logger.info("💤 Retrospectiva pulada — %s", r.get("motivo"))
    except Exception as e:
        logger.error(f"❌ Retrospectiva falhou: {e}")


def agenda_job():
    """AGENDA DO VALE — carrossel dos eventos da semana. Pula se não há eventos."""
    try:
        import agenda
        r = agenda.run(post=_autopost_on())
        if r.get("ok"):
            logger.info("📅 Agenda %s — %s evento(s).",
                        "POSTADA" if r["postado"] else "preview", r["n_eventos"])
        else:
            logger.info("💤 Agenda pulada — %s.", r.get("motivo"))
    except Exception as e:
        logger.error(f"❌ Agenda falhou: {e}")


def palpite_job():
    """Palpite do Vale (Copa). DESLIGADO por decisão editorial (03/jul/2026): os dados provaram
    que é poluição — posts de interação fazendo 0-107 views contra 400-1.700 das notícias.
    Religa com PALPITE_ON=1 se um dia fizer sentido (ex: final de Copa com aposta da cidade)."""
    if os.environ.get('PALPITE_ON', '0') != '1':
        return
    try:
        import palpite
        r = palpite.run_auto(post=_autopost_on())
        if r.get("vota") or r.get("revela"):
            logger.info("⚽ Palpite: vota=%s · revela=%s", r.get("vota"), r.get("revela"))
    except Exception as e:
        logger.error(f"❌ Palpite falhou: {e}")


def collect_job():
    """Coleta notícias de todos os feeds RSS."""
    try:
        from scraper import collect_all
        logger.info("⏰ Iniciando coleta automática de notícias...")
        total = collect_all()
        logger.info(f"✅ Coleta concluída: {total} novas notícias.")
    except Exception as e:
        logger.error(f"❌ Erro na coleta automática: {e}")


def check_live_job():
    """Verifica canais monitorados e atualiza transmissões ao vivo automaticamente."""
    try:
        import os
        from stream_checker import update_live_status
        db_path = os.environ.get('DB_PATH', 'radio_sc.db')
        logger.info("📡 Verificando canais ao vivo...")
        update_live_status(db_path)
        logger.info("✅ Verificação de ao vivo concluída.")
    except Exception as e:
        logger.error(f"❌ Erro na verificação de ao vivo: {e}")


def cleanup_job():
    """Remove notícias com mais de 7 dias, garantindo mínimo de 60 artigos."""
    try:
        import sqlite3, os
        db_path = os.environ.get('DB_PATH', 'radio_sc.db')
        audio_dir = os.environ.get('AUDIO_DIR', 'audio')

        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row

        # Segurança: só limpa se tiver notícias suficientes recentes (últimas 24h)
        recentes = conn.execute("""
            SELECT COUNT(*) FROM news
            WHERE created_at > datetime('now', '-24 hours') AND active = 1
        """).fetchone()[0]

        total = conn.execute("SELECT COUNT(*) FROM news WHERE active = 1").fetchone()[0]

        if recentes < 10:
            logger.warning(f"🛑 Limpeza cancelada — apenas {recentes} notícias nas últimas 24h. Executando coleta emergencial...")
            conn.close()
            try:
                from scraper import collect_all
                collect_all()
            except Exception as ex:
                logger.error(f"❌ Coleta emergencial falhou: {ex}")
            return

        if total < 60:
            logger.warning(f"🛑 Limpeza cancelada — apenas {total} notícias no banco. Limite mínimo: 60.")
            conn.close()
            return

        # Busca notícias antigas para deletar os áudios antes (7 dias)
        old_news = conn.execute("""
            SELECT id, audio_file FROM news
            WHERE created_at < datetime('now', '-7 days')
            AND active = 1
        """).fetchall()

        for row in old_news:
            if row['audio_file']:
                audio_path = os.path.join(audio_dir, row['audio_file'])
                if os.path.exists(audio_path):
                    try:
                        os.remove(audio_path)
                    except Exception:
                        pass

        # MEMÓRIA DO MOTOR: notícia POSTADA nunca é apagada — o Placar/LEARN cruza post_insights
        # com news (JOIN); apagar limitaria o aprendizado a 7 dias de histórico PARA SEMPRE.
        # Só limpa o áudio dela (arquivo já foi removido acima) e apaga as NÃO postadas.
        try:
            conn.execute("""
                UPDATE news SET audio_file = NULL
                WHERE created_at < datetime('now', '-7 days')
                AND social_posted_at IS NOT NULL AND social_posted_at != ''
            """)
            result = conn.execute("""
                DELETE FROM news
                WHERE created_at < datetime('now', '-7 days')
                AND (social_posted_at IS NULL OR social_posted_at = '')
            """)
        except Exception:
            # banco antigo sem a coluna social_posted_at -> comportamento original
            result = conn.execute("""
                DELETE FROM news
                WHERE created_at < datetime('now', '-7 days')
            """)
        deleted = result.rowcount
        conn.commit()
        conn.close()

        logger.info(f"🧹 Limpeza: {deleted} notícias antigas (>7 dias) removidas (postadas preservadas p/ o Placar). Restam: {total - deleted}.")
    except Exception as e:
        logger.error(f"❌ Erro na limpeza: {e}")


def start_scheduler(interval_minutes=60):
    """Inicia o agendador com coleta horária e limpeza diária."""
    global _scheduler

    if _scheduler and _scheduler.running:
        logger.info("Scheduler já está rodando.")
        return _scheduler

    # job_defaults: sem isso o APScheduler usa misfire_grace_time=1s — se o Railway reiniciar
    # (deploy) exatamente na hora de um post (7h/12h/18h/19h), o job some sem rodar. Com 30min
    # de tolerância + coalesce, o post atrasado AINDA dispara quando o processo volta (1x só).
    _scheduler = BackgroundScheduler(
        timezone='America/Sao_Paulo',
        job_defaults={
            'misfire_grace_time': 1800,   # tolera até 30min de atraso (deploy/restart)
            'coalesce': True,             # juntou execuções perdidas → roda 1 vez, não enfileira
            'max_instances': 1,           # nunca 2 do mesmo job ao mesmo tempo
        },
    )

    # Coleta a cada hora
    _scheduler.add_job(
        func=collect_job,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id='collect_news',
        name='Coleta automática de notícias',
        replace_existing=True
    )

    # Limpeza diária às 3h da manhã
    _scheduler.add_job(
        func=cleanup_job,
        trigger=CronTrigger(hour=3, minute=0, timezone='America/Sao_Paulo'),
        id='cleanup_news',
        name='Limpeza de notícias antigas (48h)',
        replace_existing=True
    )

    # Verificação de canais ao vivo a cada 10 minutos
    _scheduler.add_job(
        func=check_live_job,
        trigger=IntervalTrigger(minutes=10),
        id='check_live',
        name='Verificação automática de transmissões ao vivo',
        replace_existing=True
    )

    # ☀️ "Bom dia, Vale" — produto-bandeira, todo dia às 7h
    _scheduler.add_job(
        func=bom_dia_job,
        trigger=CronTrigger(hour=7, minute=0, timezone='America/Sao_Paulo'),
        id='bom_dia_vale',
        name='Bom dia Vale (carrossel + WhatsApp)',
        replace_existing=True
    )

    # 📣 Distribuição de notícia — "MAIS É MAIS" (decisão do dono, 12/jul): notícia é jogo de
    # volume (61% do alcance é de não-seguidores = posts não canibalizam; público consome e
    # volta com fome). Slot vazio é SEGURO: sem matéria boa/fresca na fila, o job simplesmente
    # PULA (dedup + trava + fila) — volume escala com a notícia real, igual redação de verdade.
    # Horários via env NOTICIA_HORAS (default 8h-22h a cada 2h). O Placar mede o alcance/post
    # em 2 semanas: segurou = escala mais; despencou = tira slot. Dado decide.
    _not_horas = [int(h) for h in os.environ.get('NOTICIA_HORAS', '8,10,12,14,16,18,20,22').split(',')
                  if h.strip().isdigit()] or [12, 18]
    for _h in _not_horas:
        _scheduler.add_job(
            func=social_news_job,
            trigger=CronTrigger(hour=_h, minute=0, timezone='America/Sao_Paulo'),
            id=f'social_news_{_h}',
            name=f'Distribuidor de notícias {_h}h (IG+FB)',
            replace_existing=True
        )

    # 🎬 Reels (vídeo vertical narrado) — motor de ALCANCE (o formato que mais cresce). Configurável
    # via env REELS_HORAS (horas separadas por vírgula). Default 4x/dia (9,13,16,19), bem espaçado.
    # ⚠️ o render roda no worker web; pra escalar MUITO (6x+), mover o render p/ fora (risco aberto).
    _reels_horas = [int(h) for h in os.environ.get('REELS_HORAS', '9,13,16,19').split(',')
                    if h.strip().isdigit()] or [13, 19]
    for _h in _reels_horas:
        _scheduler.add_job(
            func=reels_job,
            trigger=CronTrigger(hour=_h, minute=0, timezone='America/Sao_Paulo'),
            id=f'reels_news_{_h}',
            name=f'Reels {_h}h (vídeo narrado IG+FB)',
            replace_existing=True
        )

    # 🎙️ O VALE EM 60 SEGUNDOS — Reels diário de resumo (3 notícias do dia), 20h30. DORMENTE até
    # RESUMO_ON=1; posta só com RESUMO_POST=1 (senão gera p/ revisão em /admin/resumo).
    _scheduler.add_job(
        func=resumo_job,
        trigger=CronTrigger(hour=20, minute=30, timezone='America/Sao_Paulo'),
        id='resumo_dia',
        name='O Vale em 60 segundos (Reels diário de resumo, 20h30)',
        replace_existing=True
    )

    # ⚽ PALPITE DO VALE (Copa) — checa a cada 2h: posta o vota do jogo + a revela quando acaba.
    _scheduler.add_job(
        func=palpite_job,
        trigger=IntervalTrigger(hours=2),
        id='palpite_copa',
        name='Palpite do Vale (Copa: vota + revela automático)',
        replace_existing=True
    )

    # 📣 Bloco de marca 12h15 — sex/dom/seg = Grupo DL · ter/qui/sáb = institucional da
    # Rádio ("somos daqui": as 5 cidades) · quarta = folga (nunca o mesmo card 2 dias seguidos)
    _scheduler.add_job(
        func=promo_grupo_job,
        trigger=CronTrigger(day_of_week='mon,tue,thu,fri,sat,sun', hour=12, minute=15,
                            timezone='America/Sao_Paulo'),
        id='promo_grupo_dl',
        name='Bloco de marca 12h15 (DL sex/dom/seg · Rádio ter/qui/sáb)',
        replace_existing=True
    )

    # ⚡ Plantão: notícia urgente em tempo real — checa a cada 20 min
    _scheduler.add_job(
        func=urgent_news_job,
        trigger=IntervalTrigger(minutes=20),
        id='urgent_news',
        name='Plantão de notícia urgente (tempo real)',
        replace_existing=True
    )

    # 🌧️ Clima passa-tudo: chuva/alagamento/temporal vão pro ar sem o funil — checa a cada 20 min
    _scheduler.add_job(
        func=clima_news_job,
        trigger=IntervalTrigger(minutes=20),
        id='clima_news',
        name='Clima passa-tudo (chuva/alagamento em tempo real)',
        replace_existing=True
    )

    # 🌦️ Pauta do tempo: todo dia 16h20 (previsão de AMANHÃ com manchete-impacto; o
    # passa-tudo de clima posta no tick seguinte ~16h38, hora nobre)
    _scheduler.add_job(
        func=tempo_pauta_job,
        trigger=CronTrigger(hour=16, minute=20, timezone='America/Sao_Paulo'),
        id='tempo_pauta',
        name='Pauta diária de previsão (manchete-impacto)',
        misfire_grace_time=3600,
        replace_existing=True
    )

    # 🏭 Empresas do Vale: quinta 17h30 (pedido do dono) — gera, avisa no zap e SEGURA na
    # fila; ele revisa/aprova na hora e o post sai no horário-rei (~17h30-18h)
    _scheduler.add_job(
        func=empresas_job,
        trigger=CronTrigger(day_of_week='thu', hour=17, minute=30, timezone='America/Sao_Paulo'),
        id='empresas_vale',
        name='Empresas do Vale (matéria semanal -> fila)',
        replace_existing=True
    )

    # 🙏 Mensagem do dia — REMOVIDA 30/jul (decisão do dono: 81 views na estreia = o pior
    # post do feed; "não deu ibope, não faz sentido manter"). O módulo versiculo.py fica no
    # repo (dormente) e a rota /admin/versiculo segue existindo pra teste manual se um dia
    # quiser reviver. Nenhum job agendado.

    # 🔍 O Inspetor: revisão noturna dos posts do dia (imagem×tema, neutralidade, crime×lugar,
    # cidade, português) → suspeitos no zap do dono. Roda depois do último slot de notícia (22h).
    _scheduler.add_job(
        func=inspetor_job,
        trigger=CronTrigger(hour=22, minute=45, timezone='America/Sao_Paulo'),
        id='inspetor',
        name='Inspetor (revisor noturno do feed)',
        replace_existing=True
    )

    # 📈 Loop de Insights — puxa o resultado real dos posts 1x/dia às 23h30 (métrica amadurece).
    _scheduler.add_job(
        func=insights_job,
        trigger=CronTrigger(hour=23, minute=30, timezone='America/Sao_Paulo'),
        id='insights_loop',
        name='Loop de Insights (alcance/saves/seguidor por post)',
        replace_existing=True
    )

    # 👁️ O VIGIA — dead-man switch diário 21h30 (fábrica parou? zap na hora) +
    # resumo semanal com BACKUP do banco domingo 21h. Dormente sem as env vars.
    _scheduler.add_job(
        func=vigia_job,
        trigger=CronTrigger(hour=21, minute=30, timezone='America/Sao_Paulo'),
        id='vigia_diario',
        name='Vigia (dead-man switch: avisa no zap se a fábrica parar)',
        replace_existing=True
    )
    _scheduler.add_job(
        func=vigia_semana_job,
        trigger=CronTrigger(day_of_week='sun', hour=21, minute=0, timezone='America/Sao_Paulo'),
        id='vigia_semana',
        name='Vigia semanal (resumo + backup do banco no zap)',
        replace_existing=True
    )

    # 👂 OUVIDOR — leitor apontou erro nos comentários -> zap em minutos (22/ago, caso Antídio).
    def _ouvidor_job():
        try:
            import ouvidor
            r = ouvidor.run(enviar=True)
            if r.get("alertas"):
                logger.info(f"👂 Ouvidor: {r}")
        except Exception as e:
            logger.error(f"👂 Ouvidor falhou: {e}")

    _scheduler.add_job(func=_ouvidor_job,
        trigger=IntervalTrigger(hours=2),
        id='ouvidor_comentarios', name='Ouvidor: correções nos comentários (2/2h)',
        replace_existing=True)

    # 📚 AULA AUTOMÁTICA — segunda 07h15, o motor reescreve a própria lição de manchete
    # com o desempenho real (fecha o ciclo publica->mede->aprende, 22/ago).
    def _aula_job():
        try:
            import aula
            aula.gerar()
        except Exception as e:
            logger.error(f"📚 Aula falhou: {e}")

    _scheduler.add_job(func=_aula_job,
        trigger=CronTrigger(day_of_week='mon', hour=7, minute=15, timezone='America/Sao_Paulo'),
        id='aula_semana', name='Aula da semana (seg 07h15)', replace_existing=True)

    # 🩹 IMUNIZAÇÃO — segunda 07h20: as pegas da semana viram regras permanentes (cicatrizes)
    # no prompt do redator. Trava anti-censura: regra só corrige ESCRITA, nunca proíbe assunto.
    def _cicatriz_job():
        try:
            import cicatriz
            cicatriz.aprender_do_log()
        except Exception as e:
            logger.error(f"🩹 Imunização falhou: {e}")

    _scheduler.add_job(func=_cicatriz_job,
        trigger=CronTrigger(day_of_week='mon', hour=7, minute=20, timezone='America/Sao_Paulo'),
        id='cicatriz_semana', name='Imunização: cicatrizes da semana (seg 07h20)',
        replace_existing=True)

    # 🗳️ ALARME PÓS-ELEIÇÃO (22/ago): a lista de fatos verificados do redator (prefeitos,
    # Antídio candidato ao Senado) VENCE na eleição de outubro — o motor avisa o dono no zap
    # pra atualizar (1º turno 04/out; lembra de novo pós-2º turno). Só agenda se ainda futuro.
    def _alarme_eleicao(msg):
        try:
            import vigia
            vigia.send_zap(msg)
        except Exception as e:
            logger.error(f"🗳️ alarme eleição falhou: {e}")

    from datetime import datetime as _dt
    from apscheduler.triggers.date import DateTrigger
    for _quando, _msg, _jid in (
        ("2026-10-05 08:30", "🗳️ *ELEIÇÃO PASSOU (1º turno)* — a lista de FATOS VERIFICADOS "
         "do redator (prefeitos, Antídio candidato ao Senado) pode ter vencido. Pede pro "
         "Legião atualizar os fatos no cerebro.py com o resultado.", "fatos_eleicao_t1"),
        ("2026-10-26 08:30", "🗳️ *2º TURNO PASSOU* — conferir de novo os fatos verificados "
         "do redator (governador/senado definidos). Pede pro Legião atualizar.", "fatos_eleicao_t2"),
    ):
        try:
            if _dt.strptime(_quando, "%Y-%m-%d %H:%M") > _dt.now():
                _scheduler.add_job(func=_alarme_eleicao, args=[_msg],
                    trigger=DateTrigger(run_date=_quando, timezone='America/Sao_Paulo'),
                    id=_jid, name=f'Alarme fatos pós-eleição ({_quando[:10]})',
                    replace_existing=True)
        except Exception as e:
            logger.error(f"🗳️ agendamento eleição falhou: {e}")

    # 🏆 PLACAR — o motor mede as views sozinho (20/ago, "dos números é pra você aprender").
    def _placar_job():
        try:
            import placar
            r = placar.run(enviar=True)
            logger.info(f"🏆 Placar: {r}")
        except Exception as e:
            logger.error(f"🏆 Placar falhou: {e}")

    _scheduler.add_job(func=_placar_job,
        trigger=CronTrigger(day_of_week='mon', hour=7, minute=45, timezone='America/Sao_Paulo'),
        id='placar_semana', name='Placar da semana (seg 07h45)', replace_existing=True)

    # 📦 COMPILADOS — matéria NOSSA da colheita dos radares (20/ago, diretiva do dono:
    # "pesquisas na internet e material nosso"). Vagas seg 08h30 · Agenda qui 16h30.
    def _vagas_semana_job():
        try:
            import compilados
            compilados.vagas_da_semana()
        except Exception as e:
            logger.error(f"📦 vagas da semana falhou: {e}")

    def _agenda_fds_job():
        try:
            import compilados
            compilados.agenda_fim_de_semana()
        except Exception as e:
            logger.error(f"📦 agenda do fds falhou: {e}")

    _scheduler.add_job(func=_vagas_semana_job,
        trigger=CronTrigger(day_of_week='mon', hour=8, minute=30, timezone='America/Sao_Paulo'),
        id='compilado_vagas', name='Compilado: Vagas da semana (seg 08h30)', replace_existing=True)
    _scheduler.add_job(func=_agenda_fds_job,
        trigger=CronTrigger(day_of_week='thu', hour=16, minute=30, timezone='America/Sao_Paulo'),
        id='compilado_agenda', name='Compilado: Agenda do fim de semana (qui 16h30)', replace_existing=True)

    # 🗣️ COMUNIDADE "Diz Aí, Vale" — ☠️ DESLIGADA (12/ago, ordem do dono: "interação que não
    # funciona, precisa sumir"). Pergunta genérica em card preto fez 146 views e ZERO resposta —
    # engajamento não se pede, se conquista com pauta (clima/serviço/nostalgia). O módulo
    # comunidade.py fica no repo caso um dia volte com formato melhor (ex.: enquete de STORY,
    # que tem botão nativo). Pra religar: descomentar o add_job.
    # _scheduler.add_job(
    #     func=comunidade_job,
    #     trigger=CronTrigger(day_of_week='wed', hour=18, minute=0, timezone='America/Sao_Paulo'),
    #     id='comunidade_diz_ai',
    #     name='Comunidade: Diz Aí, Vale (pergunta semanal, quarta 18h)',
    #     replace_existing=True
    # )

    # 💙 PUBLIPOST — parceiro da semana (produto pago) toda sexta 19h. Pula sozinho se não há parceiro.
    _scheduler.add_job(
        func=publipost_job,
        trigger=CronTrigger(day_of_week='fri', hour=19, minute=0, timezone='America/Sao_Paulo'),
        id='publipost_parceiro',
        name='Publipost do parceiro da semana (sexta 19h)',
        replace_existing=True
    )

    # 🐇 O VALE NA SEMANA — retrospectiva de DADOS (carrossel) todo domingo 18h. Não auto-posta:
    # fica pronto em /admin/retro pro dono postar (conteúdo próprio do banco, salvável).
    _scheduler.add_job(
        func=retro_job,
        trigger=CronTrigger(day_of_week='sun', hour=18, minute=0, timezone='America/Sao_Paulo'),
        id='retro_semana',
        name='O Vale na Semana (retrospectiva de dados, domingo 18h)',
        replace_existing=True
    )

    # 📅 AGENDA DO VALE — eventos da semana, toda quinta 12h (a galera planeja o fim de semana).
    _scheduler.add_job(
        func=agenda_job,
        trigger=CronTrigger(day_of_week='thu', hour=12, minute=0, timezone='America/Sao_Paulo'),
        id='agenda_vale',
        name='Agenda do Vale (eventos da semana, quinta 12h)',
        replace_existing=True
    )

    # ➕ SEGUE a Rádio — conversão view->seguidor, 2x/semana (segunda e quinta 20h).
    _scheduler.add_job(
        func=segue_job,
        trigger=CronTrigger(day_of_week='mon,thu', hour=20, minute=0, timezone='America/Sao_Paulo'),
        id='segue_radio',
        name='SEGUE a Rádio (conversão, seg/qui 20h)',
        replace_existing=True
    )

    # 🗳️ ENQUETE DO VALE — Story diário de engajamento, pronto às 8h (dono posta + cola o sticker).
    _scheduler.add_job(
        func=enquete_job,
        trigger=CronTrigger(hour=8, minute=0, timezone='America/Sao_Paulo'),
        id='enquete_vale',
        name='Enquete do Vale (Story diário, 8h)',
        replace_existing=True
    )

    # 🏛️ CURIOSIDADE DO VALE — carrossel "Você Sabia?" das cidades, 2x/semana (terça e sábado 9h),
    # pros dias fracos de notícia. Conteúdo 100% nosso. Não auto-posta: pronto em /admin/curiosidade.
    _scheduler.add_job(
        func=curiosidade_job,
        trigger=CronTrigger(day_of_week='tue,sat', hour=9, minute=0, timezone='America/Sao_Paulo'),
        id='curiosidade_vale',
        name='Curiosidade do Vale (Você Sabia?, ter/sáb 9h)',
        replace_existing=True
    )

    # 🏷️ MARCAS (motores próprios) — 1 carrossel+story por dia cada, horários diferentes.
    # Despachante já tem tokens (LIVE) → posta hoje. DL Mobilidade e 4kitem PULAM sozinhos
    # até criar o IG + tokens; aí ativam automaticamente sem mexer no código.
    _scheduler.add_job(
        func=marca_job, args=['despachante'],
        trigger=CronTrigger(hour=10, minute=0, timezone='America/Sao_Paulo'),
        id='marca_despachante',
        name='Despachante Lessmann (carrossel diário 10h)',
        replace_existing=True
    )
    _scheduler.add_job(
        func=marca_job, args=['4kitem'],
        trigger=CronTrigger(hour=14, minute=0, timezone='America/Sao_Paulo'),
        id='marca_4kitem',
        name='4kitem (carrossel diário 14h)',
        replace_existing=True
    )
    # DL Mobilidade agora posta NO PERFIL DO DESPACHANTE (decisão 27/jul: sem IG separado) —
    # oferta com FOTO REAL do galpão NXT, 3x/semana pra não saturar o feed de dicas diário.
    _scheduler.add_job(
        func=marca_job, args=['dl_mobilidade'],
        trigger=CronTrigger(day_of_week='tue,thu,sat', hour=16, minute=0, timezone='America/Sao_Paulo'),
        id='marca_dl_mobilidade',
        name='DL Mobilidade → perfil do despachante (oferta foto real, ter/qui/sáb 16h)',
        replace_existing=True
    )

    _scheduler.start()
    _ap = "LIGADO" if _autopost_on() else "modo seguro (preview)"
    logger.info(f"✅ Scheduler iniciado — notícias a cada {interval_minutes} min · ao vivo a cada 10 min · "
                f"limpeza às 3h · Bom dia às 7h · distribuição 12h/18h · Reels {len(_reels_horas)}x/dia {_reels_horas} · "
                f"marcas: Despachante 10h / 4kitem 14h / DL 16h · autopost {_ap}.")
    return _scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler parado.")


def get_scheduler_status():
    global _scheduler
    if not _scheduler:
        return {'running': False, 'jobs': []}

    jobs = []
    for job in _scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            'id': job.id,
            'name': job.name,
            'next_run': next_run.isoformat() if next_run else None,
        })

    return {
        'running': _scheduler.running,
        'jobs': jobs
    }
