import sqlite3, time, sys
sys.path.insert(0, ".")
from tts_engine import generate_audio

conn = sqlite3.connect("radio_sc.db")
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT id, title, summary, source, city FROM news WHERE audio_file IS NULL AND active=1 ORDER BY priority DESC, published_at DESC").fetchall()
print(f"Total para gerar: {len(rows)}")
generated = 0
for row in rows:
    try:
        f = generate_audio(title=row["title"], summary=row["summary"] or "", source=row["source"], city=row["city"], news_id=row["id"])
        if f:
            conn.execute("UPDATE news SET audio_file=? WHERE id=?", (f, row["id"]))
            conn.commit()
            generated += 1
            if generated % 5 == 0:
                print(f"[{generated}/{len(rows)}] gerados...")
        time.sleep(0.3)
    except Exception as e:
        print(f"ERRO {row['id']}: {e}")
        time.sleep(2)
conn.close()
print(f"Concluido: {generated} audios com voz neural")
