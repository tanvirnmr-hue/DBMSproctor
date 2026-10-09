import sqlite3, random, os, csv, io, threading, webbrowser
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import Flask, g, jsonify, request, session, Response
from werkzeug.security import generate_password_hash as gph, check_password_hash as cph

BASE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(BASE)
DB = os.path.join(ROOT, 'Database', 'exam.db')
app = Flask(__name__, static_folder=os.path.join(ROOT, 'Frontend'), static_url_path='')
app.secret_key = 'proctorhall-capstone-secret'
TEACHER_CODE = 'TEACH2026'   # needed to register as a teacher
utc = lambda: datetime.now(timezone.utc)
now = lambda: utc().isoformat(timespec='seconds')
def parse(t): return datetime.fromisoformat(t.replace('Z', '+00:00')) if t else None
iso = lambda t: parse(t).isoformat(timespec='seconds') if t else None

def db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB); g.db.row_factory = sqlite3.Row; g.db.execute('PRAGMA foreign_keys=ON')
    return g.db
@app.teardown_appcontext
def close(_):
    c = g.pop('db', None)
    if c: c.close()
def rows(sql, a=()): return [dict(r) for r in db().execute(sql, a)]
def one(sql, a=()):
    r = db().execute(sql, a).fetchone(); return dict(r) if r else None
def need(role):
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            u = session.get('user')
            if not u or u['role'] != role: return jsonify(error='Please log in again'), 401
            return f(*a, **k)
        return w
    return deco
uid = lambda: session['user']['pk']

SEED = [  # (difficulty, text, options [correct first], tags)
 ('easy','Which SQL command removes all rows without logging each deletion?',['TRUNCATE','DELETE','DROP','REMOVE'],'sql,ddl'),
 ('easy',"In ACID, what does the 'I' stand for?",['Isolation','Integrity','Indexing','Inheritance'],'transactions'),
 ('easy','A column set that uniquely identifies every row is a…',['Primary key','Foreign key','Composite view','Trigger'],'keys'),
 ('easy','Which clause filters groups after aggregation?',['HAVING','WHERE','GROUP BY','ORDER BY'],'sql'),
 ('medium','Which normal form removes partial dependencies?',['2NF','1NF','3NF','BCNF'],'normalization'),
 ('medium','Which join keeps unmatched rows from the left table?',['LEFT JOIN','INNER JOIN','CROSS JOIN','SELF JOIN'],'sql,joins'),
 ('medium','Which isolation level stops dirty reads but allows non-repeatable reads?',['Read Committed','Read Uncommitted','Repeatable Read','Serializable'],'transactions'),
 ('medium','An index on (a, b) most helps queries filtering on…',['Column a (leftmost prefix)','Only column b','Neither column','Any column equally'],'indexing'),
 ('hard','In two-phase locking, when may a transaction release locks?',['Only after it has acquired all its locks','At any time','Before acquiring any lock','Only at restart'],'transactions,concurrency'),
 ('hard','BCNF removes which redundancy that 3NF may retain?',['From non-superkey determinants','Lost updates','Phantom reads','Deadlocks'],'normalization'),
 ('hard','Which protocol guarantees conflict-serializable schedules?',['Two-phase locking','Read uncommitted','Write-ahead logging','Checkpointing'],'concurrency')]
SHORT = [('medium','In one or two sentences, what is a foreign key and why is it used?','A column that references the primary key of another table to enforce referential integrity.','keys'),
 ('hard','Explain why normalization can slow down read-heavy workloads.','More tables mean more joins per query; denormalization trades redundancy for read speed.','normalization,performance')]

def init():
    if os.path.exists(DB): return
    c = sqlite3.connect(DB); c.executescript(open(os.path.join(ROOT, 'Database', 'schema.sql')).read())
    c.execute("INSERT INTO teachers(teacher_id,name,password_hash) VALUES('T001','Dr. Meera Krishnan',?)", (gph('teach123'),))
    for r, n in (('101','Asha Nair'), ('102','Ravi Kumar'), ('103','Meena Iyer')):
        c.execute('INSERT INTO students(roll_no,name,password_hash) VALUES(?,?,?)', (r, n, gph('student123')))
    c.execute("INSERT INTO subjects(name) VALUES('Database Management Systems')")
    def addq(diff, text, tags, ty, model=None, marks=1, opts=()):
        qid = c.execute('INSERT INTO questions(teacher_id,subject_id,text,qtype,model_answer,difficulty,marks) VALUES(1,1,?,?,?,?,?)', (text, ty, model, diff, marks)).lastrowid
        for i, o in enumerate(opts): c.execute('INSERT INTO options(question_id,text,is_correct) VALUES(?,?,?)', (qid, o, int(i == 0)))
        for t in tags.split(','):
            c.execute('INSERT OR IGNORE INTO tags(name) VALUES(?)', (t,)); c.execute('INSERT INTO question_tags SELECT ?, id FROM tags WHERE name=?', (qid, t))
    for d, t, o, g_ in SEED: addq(d, t, g_, 'mcq', opts=o)
    for d, t, m, g_ in SHORT: addq(d, t, g_, 'short', model=m, marks=3)
    c.execute("""INSERT INTO exams(teacher_id,title,subject_id,instructions,duration_min,n_easy,n_medium,n_hard,n_short,opens_at,closes_at,published,negative_marks)
      VALUES(1,'DBMS Mid-Term',1,'Answer all questions. Wrong MCQ answers carry a 0.25 penalty.',30,2,2,1,1,?,?,1,0.25)""",
      ((utc() - timedelta(days=1)).isoformat(timespec='seconds'), (utc() + timedelta(days=365)).isoformat(timespec='seconds')))
    c.commit(); c.close()

# ---------- auth ----------
@app.get('/')
def index(): return app.send_static_file('index.html')
@app.get('/api/me')
def whoami(): return jsonify(user=session.get('user'))

@app.post('/api/login')
def login():
    d = request.json; t = {'teacher': ('teachers', 'teacher_id'), 'student': ('students', 'roll_no')}.get(d.get('role'))
    if not t: return jsonify(error='Choose teacher or student'), 400
    u = one(f'SELECT * FROM {t[0]} WHERE {t[1]}=?', (d.get('ident', '').strip(),))
    if not u or not cph(u['password_hash'], d.get('password', '')): return jsonify(error='Invalid ID or password'), 401
    session['user'] = dict(role=d['role'], pk=u['id'], ident=u[t[1]], name=u['name'])
    return jsonify(user=session['user'])

@app.post('/api/register')
def register():
    d = request.json; role = d.get('role'); ident = d.get('ident', '').strip(); name = d.get('name', '').strip()
    if not ident or not name or len(d.get('password', '')) < 4: return jsonify(error='Fill all fields (password: min 4 characters)'), 400
    try:
        if role == 'teacher':
            if d.get('code') != TEACHER_CODE: return jsonify(error='Invalid teacher access code'), 403
            db().execute('INSERT INTO teachers(teacher_id,name,password_hash) VALUES(?,?,?)', (ident, name, gph(d['password'])))
        elif role == 'student':
            db().execute('INSERT INTO students(roll_no,name,password_hash) VALUES(?,?,?)', (ident, name, gph(d['password'])))
        else: return jsonify(error='Choose teacher or student'), 400
        db().commit()
    except sqlite3.IntegrityError: return jsonify(error='This ID is already registered'), 409
    return login()

@app.post('/api/logout')
def logout(): session.clear(); return jsonify(ok=True)

# ---------- grading helpers ----------
PEND = """(SELECT COUNT(*) FROM attempt_questions aq JOIN questions q ON q.id=aq.question_id WHERE aq.attempt_id=a.id AND q.qtype='short'
  AND NOT EXISTS (SELECT 1 FROM corrections c WHERE c.attempt_id=a.id AND c.question_id=aq.question_id)
  AND EXISTS (SELECT 1 FROM answers n WHERE n.attempt_id=a.id AND n.question_id=aq.question_id AND TRIM(COALESCE(n.answer_text,''))<>''))"""

def latest(aid, qid): return one('SELECT option_id,answer_text,submitted_at FROM answers WHERE attempt_id=? AND question_id=? ORDER BY id DESC LIMIT 1', (aid, qid))

def detail(aid, neg):
    out = []
    for q in rows('SELECT q.id,q.text,q.qtype,q.marks,q.difficulty,q.model_answer FROM attempt_questions aq JOIN questions q ON q.id=aq.question_id WHERE aq.attempt_id=? ORDER BY aq.position', (aid,)):
        a = latest(aid, q['id']); q['answered_at'] = a['submitted_at'] if a else None
        if q['qtype'] == 'mcq':
            q['options'] = rows('SELECT id,text,is_correct FROM options WHERE question_id=?', (q['id'],))
            sel = a['option_id'] if a else None; q['selected'] = sel
            q['auto'] = 0 if sel is None else (q['marks'] if any(o['id'] == sel and o['is_correct'] for o in q['options']) else -neg)
        else:
            q['text_answer'] = (a['answer_text'] or '') if a else ''
            q['auto'] = None if q['text_answer'].strip() else 0
        c = one('SELECT marks,feedback FROM corrections WHERE attempt_id=? AND question_id=?', (aid, q['id'])); q['correction'] = c
        q['final'] = c['marks'] if c else (q['auto'] or 0)
        q['pending'] = q['auto'] is None and not c
        out.append(q)
    return out

def recompute(aid, neg):
    d = detail(aid, neg); total = sum(q['marks'] for q in d); score = max(0, sum(q['final'] for q in d))
    db().execute('UPDATE attempts SET score=?,total=? WHERE id=?', (score, total, aid)); db().commit(); return d, score, total

def finalize(aid, ex, auto=False):
    if not one('SELECT submitted_at FROM attempts WHERE id=?', (aid,))['submitted_at']:
        db().execute('UPDATE attempts SET submitted_at=?,auto_submitted=? WHERE id=?', (now(), int(auto), aid))
    return recompute(aid, ex['negative_marks'])

def state(e):
    n = utc(); o = parse(e['opens_at']); c = parse(e['closes_at'])
    return 'upcoming' if o and n < o else 'closed' if c and n > c else 'open'

def remaining(ex, at):
    r = ex['duration_min'] * 60 - (utc() - parse(at['started_at'])).total_seconds()
    if ex['closes_at']: r = min(r, (parse(ex['closes_at']) - utc()).total_seconds())
    return max(0, int(r))

def pool(tid, sid, qtype, diff=None):
    sql = 'SELECT id FROM questions WHERE teacher_id=? AND subject_id=? AND qtype=?'; a = [tid, sid, qtype]
    if diff: sql += ' AND difficulty=?'; a.append(diff)
    return [r['id'] for r in rows(sql, a)]

# ---------- teacher: bank ----------
@app.get('/api/meta')
def meta(): return jsonify(subjects=rows('SELECT * FROM subjects ORDER BY name'), tags=rows('SELECT * FROM tags ORDER BY name'))

@app.post('/api/subjects')
@need('teacher')
def add_subject():
    n = request.json.get('name', '').strip()
    if not n: return jsonify(error='Subject name required'), 400
    db().execute('INSERT OR IGNORE INTO subjects(name) VALUES(?)', (n,)); db().commit(); return jsonify(ok=True), 201

@app.get('/api/questions')
@need('teacher')
def list_q():
    sql = """SELECT q.id,q.text,q.qtype,q.difficulty,q.marks,s.name subject,
      (SELECT GROUP_CONCAT(t.name) FROM question_tags qt JOIN tags t ON t.id=qt.tag_id WHERE qt.question_id=q.id) tags
      FROM questions q JOIN subjects s ON s.id=q.subject_id WHERE q.teacher_id=?"""; a = [uid()]
    for k, col in (('difficulty', 'q.difficulty'), ('qtype', 'q.qtype')):
        if request.args.get(k): sql += f' AND {col}=?'; a.append(request.args[k])
    if request.args.get('tag'):
        sql += ' AND q.id IN (SELECT question_id FROM question_tags qt JOIN tags t ON t.id=qt.tag_id WHERE t.name=?)'; a.append(request.args['tag'])
    return jsonify(rows(sql + ' ORDER BY q.id DESC', a))

@app.post('/api/questions')
@need('teacher')
def add_q():
    d = request.json; ty = d.get('qtype', 'mcq'); text = d.get('text', '').strip(); opts = d.get('options', []); c = d.get('correct', 0)
    try: marks = float(d.get('marks') or 1)
    except ValueError: marks = 0
    if not text or ty not in ('mcq', 'short') or d.get('difficulty') not in ('easy', 'medium', 'hard') or marks <= 0: return jsonify(error='Please complete the question form'), 400
    if ty == 'mcq' and (sum(1 for o in opts if o.strip()) < 2 or c >= len(opts) or not opts[c].strip()): return jsonify(error='Give at least 2 options and mark a valid correct one'), 400
    cn = db(); qid = cn.execute('INSERT INTO questions(teacher_id,subject_id,text,qtype,model_answer,difficulty,marks) VALUES(?,?,?,?,?,?,?)',
        (uid(), d['subject_id'], text, ty, d.get('model_answer'), d['difficulty'], marks)).lastrowid
    if ty == 'mcq':
        for i, o in enumerate(opts):
            if o.strip(): cn.execute('INSERT INTO options(question_id,text,is_correct) VALUES(?,?,?)', (qid, o.strip(), int(i == c)))
    for t in {t.strip().lower() for t in d.get('tags', '').split(',') if t.strip()}:
        cn.execute('INSERT OR IGNORE INTO tags(name) VALUES(?)', (t,)); cn.execute('INSERT INTO question_tags SELECT ?, id FROM tags WHERE name=?', (qid, t))
    cn.commit(); return jsonify(id=qid), 201

@app.delete('/api/questions/<int:qid>')
@need('teacher')
def del_q(qid):
    try: db().execute('DELETE FROM questions WHERE id=? AND teacher_id=?', (qid, uid())); db().commit()
    except sqlite3.IntegrityError: return jsonify(error='Already used in a student attempt, cannot delete'), 409
    return jsonify(ok=True)

# ---------- teacher: exams ----------
own_exam = lambda eid: one('SELECT * FROM exams WHERE id=? AND teacher_id=?', (eid, uid()))

@app.get('/api/exams')
@need('teacher')
def t_exams():
    ex = rows("""SELECT e.*,s.name subject,(SELECT COUNT(*) FROM attempts WHERE exam_id=e.id) attempts,
      (SELECT COUNT(*) FROM attempts WHERE exam_id=e.id AND submitted_at IS NOT NULL) submitted
      FROM exams e JOIN subjects s ON s.id=e.subject_id WHERE e.teacher_id=? ORDER BY e.id DESC""", (uid(),))
    for e in ex: e['pending'] = one('SELECT COALESCE(SUM(p),0) n FROM (SELECT ' + PEND + ' p FROM attempts a WHERE a.exam_id=? AND a.submitted_at IS NOT NULL)', (e['id'],))['n']
    return jsonify(ex)

@app.post('/api/exams')
@need('teacher')
def add_exam():
    d = request.json
    try:
        n = {k: int(d.get(k) or 0) for k in ('easy', 'medium', 'hard', 'short')}; dur = int(d['duration_min']); neg = float(d.get('negative') or 0)
        pp = int(d.get('pass_percent') or 40); mv = int(d.get('max_violations') or 3); o, c = iso(d.get('opens_at')), iso(d.get('closes_at'))
    except (ValueError, KeyError): return jsonify(error='Check the numbers you entered'), 400
    if not d.get('title', '').strip() or dur < 1 or sum(n.values()) < 1 or min(n.values()) < 0: return jsonify(error='Need a title, time limit and at least 1 question'), 400
    if o and c and parse(c) <= parse(o): return jsonify(error='Closing time must be after opening time'), 400
    sid = d['subject_id']
    for diff in ('easy', 'medium', 'hard'):
        if len(pool(uid(), sid, 'mcq', diff)) < n[diff]: return jsonify(error=f'Your bank has fewer than {n[diff]} {diff} MCQs for this subject'), 400
    if len(pool(uid(), sid, 'short')) < n['short']: return jsonify(error=f"Your bank has fewer than {n['short']} short-answer questions"), 400
    db().execute("""INSERT INTO exams(teacher_id,title,subject_id,instructions,duration_min,n_easy,n_medium,n_hard,n_short,opens_at,closes_at,negative_marks,pass_percent,max_violations)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (uid(), d['title'].strip(), sid, d.get('instructions'), dur, n['easy'], n['medium'], n['hard'], n['short'], o, c, neg, pp, mv))
    db().commit(); return jsonify(ok=True), 201

@app.post('/api/exams/<int:eid>/settings')
@need('teacher')
def settings(eid):
    if not own_exam(eid): return jsonify(error='Not found'), 404
    for k in ('published', 'results_released'):
        if k in request.json: db().execute(f'UPDATE exams SET {k}=? WHERE id=?', (int(bool(request.json[k])), eid))
    db().commit(); return jsonify(ok=True)

@app.delete('/api/exams/<int:eid>')
@need('teacher')
def del_exam(eid):
    if not own_exam(eid): return jsonify(error='Not found'), 404
    if one('SELECT 1 x FROM attempts WHERE exam_id=?', (eid,)): return jsonify(error='Students have attempted this exam; unpublish it instead'), 409
    db().execute('DELETE FROM exams WHERE id=?', (eid,)); db().commit(); return jsonify(ok=True)

@app.get('/api/exams/<int:eid>/results')
@need('teacher')
def results(eid):
    ex = own_exam(eid)
    if not ex: return jsonify(error='Not found'), 404
    ats = rows("""SELECT a.id,s.roll_no,s.name,a.started_at,a.submitted_at,a.score,a.total,a.auto_submitted,
      (SELECT COUNT(*) FROM answers WHERE attempt_id=a.id) submissions,
      (SELECT COUNT(*) FROM proctor_events WHERE attempt_id=a.id) flags, """ + PEND + """ pending
      FROM attempts a JOIN students s ON s.id=a.student_id WHERE a.exam_id=? ORDER BY a.id""", (eid,))
    done = [a for a in ats if a['submitted_at']]; acc = {}
    for a in done:
        for q in detail(a['id'], ex['negative_marks']):
            r = acc.setdefault(q['id'], dict(text=q['text'], difficulty=q['difficulty'], n=0, ok=0)); r['n'] += 1; r['ok'] += q['final'] > 0
    pct = [100 * a['score'] / a['total'] for a in done if a['total']]
    stats = dict(started=len(ats), submitted=len(done), avg=round(sum(pct) / len(pct), 1) if pct else 0,
        high=round(max(pct), 1) if pct else 0, low=round(min(pct), 1) if pct else 0, passed=sum(p >= ex['pass_percent'] for p in pct))
    return jsonify(exam=ex, attempts=ats, stats=stats, questions=list(acc.values()))

@app.get('/api/exams/<int:eid>/export')
@need('teacher')
def export(eid):
    ex = own_exam(eid)
    if not ex: return jsonify(error='Not found'), 404
    buf = io.StringIO(); w = csv.writer(buf); w.writerow(['Roll no', 'Name', 'Score', 'Total', 'Percent', 'Result', 'Submitted at (UTC)', 'Proctor flags'])
    for a in rows('SELECT a.*,s.roll_no,s.name,(SELECT COUNT(*) FROM proctor_events WHERE attempt_id=a.id) f FROM attempts a JOIN students s ON s.id=a.student_id WHERE a.exam_id=? AND a.submitted_at IS NOT NULL', (eid,)):
        p = round(100 * a['score'] / a['total'], 1) if a['total'] else 0
        w.writerow([a['roll_no'], a['name'], a['score'], a['total'], p, 'PASS' if p >= ex['pass_percent'] else 'FAIL', a['submitted_at'], a['f']])
    return Response(buf.getvalue(), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename=exam_{eid}_results.csv'})

def t_attempt(aid):
    at = one('SELECT a.* FROM attempts a JOIN exams e ON e.id=a.exam_id WHERE a.id=? AND e.teacher_id=?', (aid, uid()))
    return (at, one('SELECT * FROM exams WHERE id=?', (at['exam_id'],))) if at else (None, None)

@app.get('/api/attempts/<int:aid>/review')
@need('teacher')
def review(aid):
    at, ex = t_attempt(aid)
    if not at: return jsonify(error='Not found'), 404
    d, s, t = recompute(aid, ex['negative_marks'])
    return jsonify(student=one('SELECT name,roll_no FROM students WHERE id=?', (at['student_id'],)), score=s, total=t, questions=d,
        events=rows('SELECT event_type,created_at FROM proctor_events WHERE attempt_id=? ORDER BY id', (aid,)))

@app.post('/api/attempts/<int:aid>/correct')
@need('teacher')
def correct(aid):
    at, ex = t_attempt(aid); d = request.json
    if not at: return jsonify(error='Not found'), 404
    q = one('SELECT q.marks FROM attempt_questions aq JOIN questions q ON q.id=aq.question_id WHERE aq.attempt_id=? AND aq.question_id=?', (aid, d.get('question_id')))
    try: m = float(d['marks'])
    except (ValueError, KeyError, TypeError): return jsonify(error='Enter marks'), 400
    if not q or m < 0 or m > q['marks']: return jsonify(error=f"Marks must be between 0 and {q['marks'] if q else '?'}"), 400
    db().execute('REPLACE INTO corrections(attempt_id,question_id,marks,feedback,corrected_at) VALUES(?,?,?,?,?)', (aid, d['question_id'], m, d.get('feedback', ''), now()))
    _, s, t = recompute(aid, ex['negative_marks']); return jsonify(score=s, total=t)

# ---------- student ----------
def mine(aid):
    at = one('SELECT * FROM attempts WHERE id=? AND student_id=?', (aid, uid()))
    return (at, one('SELECT * FROM exams WHERE id=?', (at['exam_id'],))) if at else (None, None)

@app.get('/api/student/exams')
@need('student')
def s_exams():
    out = []
    for e in rows('SELECT e.*,t.name teacher,s.name subject FROM exams e JOIN teachers t ON t.id=e.teacher_id JOIN subjects s ON s.id=e.subject_id WHERE e.published=1 ORDER BY e.id DESC'):
        at = one('SELECT id,submitted_at,score,total FROM attempts WHERE exam_id=? AND student_id=?', (e['id'], uid()))
        if at and not e['results_released']: at['score'] = at['total'] = None
        e.update(state=state(e), attempt=at, n_questions=e['n_easy'] + e['n_medium'] + e['n_hard'] + e['n_short']); out.append(e)
    return jsonify(out)

def payload(aid):
    at, ex = mine(aid)
    if not at['submitted_at'] and remaining(ex, at) <= 0: finalize(aid, ex, True); at = one('SELECT * FROM attempts WHERE id=?', (aid,))
    qs = rows('SELECT q.id,q.text,q.qtype,q.difficulty,q.marks FROM attempt_questions aq JOIN questions q ON q.id=aq.question_id WHERE aq.attempt_id=? ORDER BY aq.position', (aid,))
    for q in qs:
        if q['qtype'] == 'mcq': o = rows('SELECT id,text FROM options WHERE question_id=?', (q['id'],)); random.shuffle(o); q['options'] = o
        a = latest(aid, q['id']); q['selected'] = a['option_id'] if a else None; q['text_answer'] = (a['answer_text'] if a else '') or ''
    v = one("SELECT COUNT(*) n FROM proctor_events WHERE attempt_id=? AND event_type IN ('tab_switch','fullscreen_exit')", (aid,))['n']
    at.update(title=ex['title'], instructions=ex['instructions'], max_violations=ex['max_violations']); at.pop('score'); at.pop('total')
    return dict(attempt=at, questions=qs, remaining=remaining(ex, at), violations=v)

@app.post('/api/attempts')
@need('student')
def start():
    ex = one('SELECT * FROM exams WHERE id=? AND published=1', (request.json.get('exam_id'),))
    if not ex: return jsonify(error='This exam is not available'), 404
    at = one('SELECT id FROM attempts WHERE exam_id=? AND student_id=?', (ex['id'], uid()))
    if not at:
        st = state(ex)
        if st != 'open': return jsonify(error=f'This exam is {st}'), 403
        chosen = []
        for diff in ('easy', 'medium', 'hard'):
            p = pool(ex['teacher_id'], ex['subject_id'], 'mcq', diff)
            if len(p) < ex['n_' + diff]: return jsonify(error=f'Not enough {diff} questions in the bank'), 400
            chosen += random.sample(p, ex['n_' + diff])
        p = pool(ex['teacher_id'], ex['subject_id'], 'short')
        if len(p) < ex['n_short']: return jsonify(error='Not enough short-answer questions'), 400
        chosen += random.sample(p, ex['n_short']); random.shuffle(chosen)
        aid = db().execute('INSERT INTO attempts(exam_id,student_id,started_at) VALUES(?,?,?)', (ex['id'], uid(), now())).lastrowid
        for i, q in enumerate(chosen): db().execute('INSERT INTO attempt_questions VALUES(?,?,?)', (aid, q, i + 1))
        db().commit()
    else: aid = at['id']
    return jsonify(payload(aid))

@app.post('/api/attempts/<int:aid>/answer')
@need('student')
def answer(aid):
    at, ex = mine(aid); d = request.json
    if not at: return jsonify(error='Not found'), 404
    if at['submitted_at']: return jsonify(error='Attempt already submitted'), 409
    if remaining(ex, at) <= 0: finalize(aid, ex, True); return jsonify(error='Time is over'), 409
    q = one('SELECT q.qtype FROM attempt_questions aq JOIN questions q ON q.id=aq.question_id WHERE aq.attempt_id=? AND aq.question_id=?', (aid, d.get('question_id')))
    if not q: return jsonify(error='Question not in your paper'), 400
    if q['qtype'] == 'mcq':
        if not one('SELECT 1 x FROM options WHERE id=? AND question_id=?', (d.get('option_id'), d['question_id'])): return jsonify(error='Invalid option'), 400
        db().execute('INSERT INTO answers(attempt_id,question_id,option_id,submitted_at) VALUES(?,?,?,?)', (aid, d['question_id'], d['option_id'], now()))
    else: db().execute('INSERT INTO answers(attempt_id,question_id,answer_text,submitted_at) VALUES(?,?,?,?)', (aid, d['question_id'], str(d.get('text', ''))[:5000], now()))
    db().commit(); return jsonify(saved_at=now())

@app.post('/api/attempts/<int:aid>/event')
@need('student')
def event(aid):
    at, ex = mine(aid); t = str(request.json.get('type', ''))[:30]
    if not at or at['submitted_at']: return jsonify(violations=0, max=0)
    db().execute('INSERT INTO proctor_events(attempt_id,event_type,created_at) VALUES(?,?,?)', (aid, t, now())); db().commit()
    n = one("SELECT COUNT(*) n FROM proctor_events WHERE attempt_id=? AND event_type IN ('tab_switch','fullscreen_exit')", (aid,))['n']
    auto = t in ('tab_switch', 'fullscreen_exit') and n >= ex['max_violations']
    if auto: finalize(aid, ex, True)
    return jsonify(violations=n, max=ex['max_violations'], counted=t in ('tab_switch', 'fullscreen_exit'), auto_submitted=auto)

@app.post('/api/attempts/<int:aid>/submit')
@need('student')
def submit(aid):
    at, ex = mine(aid)
    if not at: return jsonify(error='Not found'), 404
    finalize(aid, ex, False); return jsonify(ok=True)

@app.get('/api/attempts/<int:aid>/result')
@need('student')
def result(aid):
    at, ex = mine(aid)
    if not at or not at['submitted_at']: return jsonify(error='Not submitted yet'), 404
    out = dict(title=ex['title'], submitted_at=at['submitted_at'], auto_submitted=bool(at['auto_submitted']), released=bool(ex['results_released']), pass_percent=ex['pass_percent'])
    if ex['results_released']:
        d, s, t = recompute(aid, ex['negative_marks']); out.update(score=s, total=t, questions=d, pending=sum(q['pending'] for q in d))
    return jsonify(out)

if __name__ == '__main__':
    init()
    threading.Timer(1.2, lambda: webbrowser.open('http://127.0.0.1:5000')).start()   # site opens on Run
    app.run(debug=True, use_reloader=False, port=5000)
