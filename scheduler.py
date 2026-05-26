"""
scheduler.py — Agendador de coleta automática de notícias
Rádio SC News
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler = None


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

        conn = sqlite3.connect(db_path)
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

    _scheduler = BackgroundScheduler(timezone='America/Sao_Paulo')

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

    _scheduler.start()
    logger.info(f"✅ Scheduler iniciado — notícias a cada {interval_minutes} min · ao vivo a cada 10 min · limpeza às 3h.")
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
