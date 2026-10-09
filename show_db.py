import sqlite3, os
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Database', 'exam.db')
if not os.path.exists(DB): raise SystemExit('exam.db not found - run app.py once first.')
c = sqlite3.connect(DB)
for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall():
    print(f'\n== {t}  ({c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]} rows)')
    fks = {r[3]: f'{r[2]}.{r[4]}' for r in c.execute(f'PRAGMA foreign_key_list({t})')}
    for _, name, typ, notnull, _d, pk in c.execute(f'PRAGMA table_info({t})'):
        print(f'  {name:<16}{typ:<8}{"PK " if pk else ""}{"NOT NULL " if notnull else ""}{"-> " + fks[name] if name in fks else ""}')
