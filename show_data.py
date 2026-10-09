import sqlite3, os, sys
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Database', 'exam.db')
if not os.path.exists(DB): raise SystemExit('exam.db not found - run app.py once first.')
c = sqlite3.connect(DB)
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
only = sys.argv[1] if len(sys.argv) > 1 else None
limit = int(sys.argv[2]) if len(sys.argv) > 2 else (None if only else 10)
if only and only not in tables: raise SystemExit('Tables: ' + ', '.join(tables))
for t in ([only] if only else tables):
    cols = [r[1] for r in c.execute(f'PRAGMA table_info({t})') if r[1] != 'password_hash']
    total = c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
    data = c.execute(f'SELECT {",".join(cols)} FROM {t}' + (f' LIMIT {limit}' if limit else '')).fetchall()
    cell = lambda v: ('' if v is None else str(v)).replace('\n', ' ')[:38]
    w = [max([len(h)] + [len(cell(r[i])) for r in data]) for i, h in enumerate(cols)]
    print(f'\n== {t} ({total} rows)')
    print('  ' + ' | '.join(h.ljust(w[i]) for i, h in enumerate(cols))); print('  ' + '-+-'.join('-' * x for x in w))
    for r in data: print('  ' + ' | '.join(cell(v).ljust(w[i]) for i, v in enumerate(r)))