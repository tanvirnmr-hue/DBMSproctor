PRAGMA foreign_keys = ON;
CREATE TABLE teachers(id INTEGER PRIMARY KEY, teacher_id TEXT UNIQUE NOT NULL, name TEXT NOT NULL, password_hash TEXT NOT NULL);
CREATE TABLE students(id INTEGER PRIMARY KEY, roll_no TEXT UNIQUE NOT NULL, name TEXT NOT NULL, password_hash TEXT NOT NULL);
CREATE TABLE subjects(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE questions(
  id INTEGER PRIMARY KEY,
  teacher_id INTEGER NOT NULL REFERENCES teachers(id),
  subject_id INTEGER NOT NULL REFERENCES subjects(id),
  text TEXT NOT NULL,
  qtype TEXT NOT NULL DEFAULT 'mcq' CHECK (qtype IN ('mcq','short')),
  model_answer TEXT,
  difficulty TEXT NOT NULL CHECK (difficulty IN ('easy','medium','hard')),
  marks REAL NOT NULL DEFAULT 1);
CREATE TABLE options(id INTEGER PRIMARY KEY, question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE, text TEXT NOT NULL, is_correct INTEGER NOT NULL DEFAULT 0);
CREATE TABLE tags(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE question_tags(question_id INTEGER REFERENCES questions(id) ON DELETE CASCADE, tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE, PRIMARY KEY(question_id, tag_id));
CREATE TABLE exams(
  id INTEGER PRIMARY KEY,
  teacher_id INTEGER NOT NULL REFERENCES teachers(id),
  title TEXT NOT NULL, subject_id INTEGER NOT NULL REFERENCES subjects(id), instructions TEXT,
  duration_min INTEGER NOT NULL,
  n_easy INTEGER NOT NULL DEFAULT 0, n_medium INTEGER NOT NULL DEFAULT 0, n_hard INTEGER NOT NULL DEFAULT 0, n_short INTEGER NOT NULL DEFAULT 0,
  opens_at TEXT, closes_at TEXT,
  published INTEGER NOT NULL DEFAULT 0, results_released INTEGER NOT NULL DEFAULT 0,
  negative_marks REAL NOT NULL DEFAULT 0, pass_percent INTEGER NOT NULL DEFAULT 40, max_violations INTEGER NOT NULL DEFAULT 3);
CREATE TABLE attempts(
  id INTEGER PRIMARY KEY,
  exam_id INTEGER NOT NULL REFERENCES exams(id), student_id INTEGER NOT NULL REFERENCES students(id),
  started_at TEXT NOT NULL, submitted_at TEXT, score REAL, total REAL, auto_submitted INTEGER NOT NULL DEFAULT 0,
  UNIQUE(exam_id, student_id));
-- one random set per attempt; the composite PK guarantees no duplicate question
CREATE TABLE attempt_questions(attempt_id INTEGER REFERENCES attempts(id) ON DELETE CASCADE, question_id INTEGER REFERENCES questions(id), position INTEGER NOT NULL, PRIMARY KEY(attempt_id, question_id));
-- append-only, time-stamped submission log (latest row per question is graded)
CREATE TABLE answers(
  id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id INTEGER NOT NULL, question_id INTEGER NOT NULL,
  option_id INTEGER REFERENCES options(id), answer_text TEXT, submitted_at TEXT NOT NULL,
  FOREIGN KEY(attempt_id, question_id) REFERENCES attempt_questions(attempt_id, question_id) ON DELETE CASCADE);
-- teacher corrections / manual marks override
CREATE TABLE corrections(
  attempt_id INTEGER NOT NULL, question_id INTEGER NOT NULL, marks REAL NOT NULL, feedback TEXT, corrected_at TEXT NOT NULL,
  PRIMARY KEY(attempt_id, question_id),
  FOREIGN KEY(attempt_id, question_id) REFERENCES attempt_questions(attempt_id, question_id) ON DELETE CASCADE);
CREATE TABLE proctor_events(id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id INTEGER NOT NULL REFERENCES attempts(id) ON DELETE CASCADE, event_type TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX idx_q_pool ON questions(teacher_id, subject_id, qtype, difficulty);
CREATE INDEX idx_ans_latest ON answers(attempt_id, question_id, id);
