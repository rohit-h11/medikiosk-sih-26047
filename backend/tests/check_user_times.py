import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/medikiosk.db')
c = conn.cursor()
c.execute("SELECT turn_number, role, created_at FROM dialogue_messages WHERE session_id = 'sess_97e5d42d8d' ORDER BY turn_number ASC")
rows = c.fetchall()

print('=== REAL TIME GAPS IN USER CONVERSATION ===')
for i in range(len(rows)-1):
    r1, r2 = rows[i], rows[i+1]
    t1 = datetime.fromisoformat(r1[2])
    t2 = datetime.fromisoformat(r2[2])
    diff = (t2 - t1).total_seconds()
    if r1[1] == 'patient' and r2[1] == 'assistant':
        print(f"Turn {r1[0]} (Patient) -> Turn {r2[0]} (Assistant): {round(diff, 2)}s")
