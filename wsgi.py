"""Ponto de entrada para produção (gunicorn)."""
import threading
from app import app, init_db, get_db, logger

init_db()

def _startup():
    import time
    time.sleep(2)
    try:
        from scheduler import start_scheduler
        # CHIP Stage 2 (03/jul): coleta a cada 30min (era 60) — o plantão urgente roda a cada
        # 20min mas só posta o que a COLETA já viu; coleta 2x mais rápida = a gente publica o
        # fato antes da concorrência postar no Instagram. "Mais é mais" (decisão do dono).
        start_scheduler(interval_minutes=30)
    except Exception as e:
        logger.warning(f"Scheduler não iniciado: {e}")
    try:
        conn = get_db()
        count = conn.execute('SELECT COUNT(*) FROM news').fetchone()[0]
        conn.close()
        if count == 0:
            logger.info("Banco vazio — coleta inicial em background...")
            from scraper import collect_all
            collect_all()
    except Exception as e:
        logger.warning(f"Coleta inicial falhou: {e}")

threading.Thread(target=_startup, daemon=True).start()
