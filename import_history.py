import sqlite3
from datetime import date
from decimal import Decimal

data = """
09-09|-4.40
09-10|5.60
09-11|17.40,1.60
09-12|-20.00,11.30
09-13|10.60
09-14|1.90,30.80
09-16|-40.00
09-19|53.20
09-20|-11.20
09-21|-40.00
09-22|-10.00,32.90
09-23|34.40
09-24|-1.00
09-25|-50.00,-12.50
09-26|7.10
09-28|-36.00
09-30|-18.20
10-01|30.00
10-02|-20.00
10-03|-10.00
10-04|30.00
10-05|-20.00,36.10
10-06|26.30,-20.00,-25.00
10-07|7.00
10-08|31.00
10-09|-20.00
10-11|-20.00
10-14|-22.80
10-15|28.30
10-19|1.40
10-20|23.00
10-22|5.70,7.90
10-23|-1.00,-9.00
10-24|30.00,16.10
"""

stake_entries = {
    ("10-01", 0),
    ("10-02", 0),
    ("10-04", 0),
    ("10-06", 1),
}

records = []

for line in data.strip().splitlines():
    day, amounts = line.split("|")
    for index, amount in enumerate(amounts.split(",")):
        cents = int(Decimal(amount) * 100)
        game_type = (
            "Stake" if (day, index) in stake_entries
            else "Home Game"
        )
        notes = "Imported from original poker history"
        if day == "10-02":
            notes += "; original note: stake never again"

        records.append((
            1,
            date.fromisoformat("2026-" + day).isoformat(),
            game_type,
            max(-cents, 0),
            max(cents, 0),
            notes,
            "net",
        ))

assert len(records) == 45
assert sum(r[4] - r[3] for r in records) == 6850

conn = sqlite3.connect("instance/poker.db")

try:
    conn.execute("BEGIN IMMEDIATE")

    user = conn.execute(
        "SELECT username FROM users WHERE id = 1"
    ).fetchone()

    if user != ("eyoung",):
        raise RuntimeError("Expected eyoung account not found")

    existing = conn.execute(
        "SELECT COUNT(*) FROM poker_sessions WHERE user_id = 1"
    ).fetchone()[0]

    if existing:
        raise RuntimeError(
            f"Import stopped: account already has {existing} sessions"
        )

    conn.executemany("""
        INSERT INTO poker_sessions
        (user_id, date, game_type, buy_in_cents,
         cash_out_cents, notes, entry_mode)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, records)

    conn.commit()

    print("Import successful!")
    print("Sessions imported:", len(records))
    print("Total profit: +$68.50")
    print("Stake sessions:", sum(r[2] == "Stake" for r in records))

except Exception:
    conn.rollback()
    raise
finally:
    conn.close()
