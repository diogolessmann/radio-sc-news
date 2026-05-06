"""
scheduler.py — Agendador de coleta automática de notícias
Rádio SC News — coleta a cada 1 hora
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler = None


def collect_job():
    """Job de coleta executado pelo scheduler."""
    try:
        from scraper import collect_all
        logger.info("⏰ Iniciando coleta automática de notícias...")
        total = collect_all()
        logger.info(f"✅ Coleta automática concluída: {total} novas notícias.")
    except Exception as e:
        logger.error(f"❌ Erro na coleta automática: {e}")


def start_scheduler(interval_minutes=60):
    """Inicia o agendador de coleta automática."""
    global _scheduler
    
    if _scheduler and _scheduler.running:
        logger.info("Scheduler já está rodando.")
        return _scheduler
    
    _scheduler = BackgroundScheduler(timezone='America/Sao_Paulo')
    _scheduler.add_job(
        func=collect_job,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id='collect_news',
        name='Coleta automática de notícias',
        replace_existing=True
    )
    _scheduler.start()
    logger.info(f"✅ Scheduler iniciado — coleta a cada {interval_minutes} minutos.")
    return _scheduler


def stop_scheduler():
    """Para o agendador."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler parado.")


def get_scheduler_status():
    """Retorna status do scheduler."""
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
