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
        r = distribuidor.run_once(post=True, limit=1)
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
        conta = insights.coletar_conta()
        logger.info(f"📈 Insights: {n} post(s) atualizado(s). Conta: {conta}")
    except Exception as e:
        logger.error(f"❌ Insights falhou: {e}")


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
    """Palpite do Vale (Copa): posta o VOTA do jogo do dia e a REVELA quando o jogo acaba.
    Roda a cada 2h. Pula sozinho se não há jogo / sem chave da API. Só posta se autopost ligado."""
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

        result = conn.execute("""
            DELETE FROM news
            WHERE created_at < datetime('now', '-7 days')
        """)
        deleted = result.rowcount
        conn.commit()
        conn.close()

        logger.info(f"🧹 Limpeza: {deleted} notícias antigas (>7 dias) removidas. Restam: {total - deleted}.")
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

    # 📣 Distribuição de notícia nas redes — 12h e 18h (2 posts/dia)
    _scheduler.add_job(
        func=social_news_job,
        trigger=CronTrigger(hour='12,18', minute=0, timezone='America/Sao_Paulo'),
        id='social_news',
        name='Distribuidor de notícias (IG+FB)',
        replace_existing=True
    )

    # 🎬 Reels (vídeo vertical narrado) — 2x/dia (13h e 19h). Reels = motor de ALCANCE.
    # ⚠️ o render roda no worker web; manter modesto (2/dia) até mover o render p/ fora.
    for _h in (13, 19):
        _scheduler.add_job(
            func=reels_job,
            trigger=CronTrigger(hour=_h, minute=0, timezone='America/Sao_Paulo'),
            id=f'reels_news_{_h}',
            name=f'Reels {_h}h (vídeo narrado IG+FB)',
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

    # ⚡ Plantão: notícia urgente em tempo real — checa a cada 20 min
    _scheduler.add_job(
        func=urgent_news_job,
        trigger=IntervalTrigger(minutes=20),
        id='urgent_news',
        name='Plantão de notícia urgente (tempo real)',
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

    # 🗣️ COMUNIDADE — franquia "Diz Aí, Vale" (pergunta da semana) toda quarta 18h. Puxa comentário.
    _scheduler.add_job(
        func=comunidade_job,
        trigger=CronTrigger(day_of_week='wed', hour=18, minute=0, timezone='America/Sao_Paulo'),
        id='comunidade_diz_ai',
        name='Comunidade: Diz Aí, Vale (pergunta semanal, quarta 18h)',
        replace_existing=True
    )

    # 💙 PUBLIPOST — parceiro da semana (produto pago) toda sexta 19h. Pula sozinho se não há parceiro.
    _scheduler.add_job(
        func=publipost_job,
        trigger=CronTrigger(day_of_week='fri', hour=19, minute=0, timezone='America/Sao_Paulo'),
        id='publipost_parceiro',
        name='Publipost do parceiro da semana (sexta 19h)',
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
    _scheduler.add_job(
        func=marca_job, args=['dl_mobilidade'],
        trigger=CronTrigger(hour=16, minute=0, timezone='America/Sao_Paulo'),
        id='marca_dl_mobilidade',
        name='DL Mobilidade (carrossel diário 16h)',
        replace_existing=True
    )

    _scheduler.start()
    _ap = "LIGADO" if _autopost_on() else "modo seguro (preview)"
    logger.info(f"✅ Scheduler iniciado — notícias a cada {interval_minutes} min · ao vivo a cada 10 min · "
                f"limpeza às 3h · Bom dia às 7h · distribuição 12h/18h · Reels às 19h · "
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
