import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, root):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        for folder in ('uploads','snapshots'):
            (root/folder).mkdir(exist_ok=True)
        self.db = root/'debriswatch.sqlite3'
        with self.connect() as con:
            con.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS uploads(id TEXT PRIMARY KEY, path TEXT NOT NULL, metadata TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, job_id TEXT NOT NULL, created_at TEXT NOT NULL, media_seconds REAL NOT NULL, rule TEXT NOT NULL, count INTEGER NOT NULL, track_ids TEXT NOT NULL, message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', acknowledged_at TEXT, resolved_at TEXT, snapshot TEXT);
            CREATE INDEX IF NOT EXISTS events_job ON events(job_id,created_at);
            UPDATE jobs SET status='interrupted' WHERE status IN ('running','queued','stopping');
            ''')

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.db, timeout=15)
        con.row_factory = sqlite3.Row
        try:
            with con:
                yield con
        finally:
            con.close()

    def add_upload(self, uid, path, metadata):
        with self.connect() as con:
            con.execute('INSERT INTO uploads VALUES (?,?,?)',(uid,str(path),json.dumps(metadata)))

    def upload(self, uid):
        with self.connect() as con:
            row = con.execute('SELECT * FROM uploads WHERE id=?',(uid,)).fetchone()
        return dict(row) if row else None

    def save_job(self, job):
        with self.connect() as con:
            con.execute('INSERT INTO jobs VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,payload=excluded.payload', (job['id'],job['created_at'],job['status'],json.dumps(job)))

    def job(self, jid):
        with self.connect() as con:
            row = con.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
        if row:
            result = json.loads(row['payload']); result['status'] = row['status']
            return result

    def jobs(self):
        with self.connect() as con:
            rows = con.execute('SELECT * FROM jobs ORDER BY created_at DESC LIMIT 100').fetchall()
        return [dict(json.loads(r['payload']),status=r['status']) for r in rows]

    def add_event(self, jid, seconds, event, snapshot):
        eid = uuid4().hex
        with self.connect() as con:
            con.execute('INSERT INTO events(id,job_id,created_at,media_seconds,rule,count,track_ids,message,snapshot) VALUES (?,?,?,?,?,?,?,?,?)', (eid,jid,now(),seconds,event['rule'],event['count'],json.dumps(event['track_ids']),event['message'],snapshot))
        return eid

    @staticmethod
    def decode(row):
        item = dict(row); item['track_ids'] = json.loads(item['track_ids'])
        return item

    def events(self, jid=None, limit=200, offset=0):
        with self.connect() as con:
            rows = con.execute('SELECT * FROM events WHERE (? IS NULL OR job_id=?) ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?', (jid,jid,limit,offset)).fetchall()
        return [self.decode(r) for r in rows]

    def event(self, eid):
        with self.connect() as con:
            row = con.execute('SELECT * FROM events WHERE id=?',(eid,)).fetchone()
        return self.decode(row) if row else None

    def event_summary(self, jid=None):
        with self.connect() as con:
            row = con.execute("SELECT COUNT(*) AS total, COALESCE(SUM(status!='resolved'),0) AS unresolved FROM events WHERE (? IS NULL OR job_id=?)", (jid,jid)).fetchone()
        return dict(row)

    def transition(self, eid, action):
        with self.connect() as con:
            if action == 'acknowledge':
                con.execute("UPDATE events SET status='acknowledged',acknowledged_at=? WHERE id=? AND status='open'",(now(),eid))
            else:
                con.execute("UPDATE events SET status='resolved',resolved_at=? WHERE id=? AND status!='resolved'",(now(),eid))
        return self.event(eid)
