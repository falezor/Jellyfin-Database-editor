import http.client
import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKEN_RE = re.compile(r"TOKEN='([a-f0-9]+)'")


def free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]
    finally:
        s.close()


def create_test_db(path, count=25):
    con = sqlite3.connect(path)
    try:
        con.executescript("""
        CREATE TABLE BaseItems (
            Id TEXT PRIMARY KEY,
            Name TEXT,
            SortName TEXT,
            Type TEXT,
            Path TEXT,
            ParentId TEXT,
            TopParentId TEXT,
            SeriesId TEXT,
            SeasonId TEXT,
            SeriesName TEXT,
            IndexNumber INTEGER,
            ParentIndexNumber INTEGER,
            ProductionYear INTEGER,
            Size INTEGER,
            PrimaryVersionId TEXT,
            Data TEXT
        );
        CREATE TABLE BaseItemImageInfos (
            Id TEXT PRIMARY KEY,
            ItemId TEXT,
            ImageType INTEGER,
            Path TEXT
        );
        """)
        rows = []
        for i in range(count):
            iid = f'item-{i:03d}'
            name = f'Item {i:03d}'
            rows.append((iid, name, name, 'MediaBrowser.Controller.Entities.Movies.Movie',
                         f'/media/item-{i:03d}.mkv', '', '', '', '', '', None, None, 2020, 100, None, None))
        con.executemany('INSERT INTO BaseItems VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', rows)
        con.execute('INSERT INTO BaseItemImageInfos VALUES (?,?,?,?)',
                    ('img-0', 'item-000', 0, '/media/item-000.jpg'))
        con.execute('INSERT INTO BaseItemImageInfos VALUES (?,?,?,?)',
                    ('img-orphan', 'missing-item', 0, '/media/orphan.jpg'))
        con.commit()
    finally:
        con.close()


class Server:
    def __init__(self, db_path):
        self.tmp = tempfile.mkdtemp(prefix='jfapi_')
        self.data_dir = os.path.join(self.tmp, 'data')
        os.makedirs(self.data_dir)
        self.config = os.path.join(self.tmp, 'settings.json')
        with open(self.config, 'w', encoding='utf-8') as f:
            json.dump({'data_dir': self.data_dir}, f)
        self.port = free_port()
        self.base = f'http://127.0.0.1:{self.port}'
        self.log_path = os.path.join(self.tmp, 'server.log')
        self.log = open(self.log_path, 'w', encoding='utf-8')
        env = os.environ.copy()
        env['JF_BROWSER_CONFIG'] = self.config
        env['PYTHONIOENCODING'] = 'utf-8'
        self.proc = subprocess.Popen(
            [sys.executable, str(ROOT / 'jf_browser.py'), '--db', str(db_path),
             '--port', str(self.port), '--no-browser', '--no-service-check'],
            cwd=str(ROOT), env=env, stdout=self.log, stderr=subprocess.STDOUT,
        )
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.page = None
        try:
            self._wait()
        except Exception:
            self.close()
            raise

    def _wait(self):
        deadline = time.time() + 15
        last = None
        while time.time() < deadline:
            if self.proc.poll() is not None:
                break
            try:
                r = self.opener.open(self.base + '/', timeout=0.4)
                self.page = r.read().decode('utf-8')
                m = TOKEN_RE.search(self.page)
                if not m:
                    raise RuntimeError('token missing from page')
                self.token = m.group(1)
                return
            except Exception as e:
                last = e
                time.sleep(0.2)
        self.log.flush()
        log = Path(self.log_path).read_text(encoding='utf-8', errors='replace')
        raise RuntimeError(f'server did not start: {last}\n{log}')

    def get(self, path, auth=True):
        opener = self.opener if auth else urllib.request.build_opener()
        req = urllib.request.Request(self.base + path, headers={'X-Lang': 'en'})
        try:
            with opener.open(req, timeout=10) as r:
                raw = r.read()
                try:
                    return r.status, json.loads(raw.decode('utf-8'))
                except ValueError:
                    return r.status, raw
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw.decode('utf-8'))
            except ValueError:
                return e.code, raw

    def get_headers(self, path):
        req = urllib.request.Request(self.base + path, headers={'X-Lang': 'en'})
        with self.opener.open(req, timeout=10) as r:
            return r.status, dict(r.headers)

    def post(self, path, body):
        data = json.dumps(body or {}).encode('utf-8')
        req = urllib.request.Request(
            self.base + path, data=data, method='POST',
            headers={'Content-Type': 'application/json', 'X-Token': self.token, 'X-Lang': 'en'},
        )
        try:
            with self.opener.open(req, timeout=30) as r:
                return r.status, json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode('utf-8'))

    def host_status(self, host):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        try:
            conn.putrequest('GET', '/api/info', skip_host=True)
            conn.putheader('Host', host)
            conn.putheader('X-Token', self.token)
            conn.putheader('X-Lang', 'en')
            conn.endheaders()
            r = conn.getresponse()
            r.read()
            return r.status
        finally:
            conn.close()

    def close(self):
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        try:
            self.log.close()
        except Exception:
            pass
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='jfdb_test_')
        cls.db = os.path.join(cls.tmp, 'jellyfin.db')
        create_test_db(cls.db)
        cls.server = Server(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.server.close()
        import shutil
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_auth_and_security_headers(self):
        status, headers = self.server.get_headers('/')
        self.assertEqual(status, 200)
        self.assertIn('jfb_token=', headers.get('Set-Cookie', ''))
        self.assertEqual(headers.get('X-Frame-Options'), 'DENY')
        self.assertIn("frame-ancestors 'none'", headers.get('Content-Security-Policy', ''))

        status, _ = self.server.get('/api/info', auth=False)
        self.assertEqual(status, 403)
        status, info = self.server.get('/api/info')
        self.assertEqual(status, 200)
        self.assertFalse(info['nodb'])

        req = urllib.request.Request(self.server.base + '/api/info',
                                     headers={'X-Token': self.server.token, 'X-Lang': 'en'})
        with urllib.request.urlopen(req, timeout=10) as r:
            self.assertEqual(r.status, 200)

        status, _ = self.server.get('/img?id=nope', auth=False)
        self.assertEqual(status, 403)
        status, _ = self.server.get('/img?id=nope')
        self.assertEqual(status, 404)

        self.assertEqual(self.server.host_status('evil.example'), 403)
        self.assertEqual(self.server.host_status(f'192.168.1.50:{self.server.port}'), 403)
        self.assertEqual(self.server.host_status(f'127.0.0.1:{self.server.port}'), 200)

    def test_data_flow(self):
        status, rows = self.server.get('/api/list?limit=5&offset=20')
        self.assertEqual(status, 200)
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]['Name'], 'Item 020')

        status, only = self.server.get('/api/list?sort=only&limit=5&offset=0')
        self.assertEqual(status, 200)
        self.assertEqual(len(only), 5)

        status, problems = self.server.get('/api/problems')
        self.assertEqual(status, 200)
        self.assertEqual(problems['total'], 25)
        self.assertEqual(problems['limit'], 5000)
        self.assertEqual(len(problems['items']), 25)

        status, types = self.server.get('/api/types')
        self.assertEqual(status, 200)
        self.assertEqual(types['mode'], 'type')

        status, orphans = self.server.get('/api/orphans')
        self.assertEqual(status, 200)
        self.assertEqual(orphans['total'], 1)

        status, deleted = self.server.post('/api/delete', {'ids': ['item-000']})
        self.assertEqual(status, 200)
        self.assertEqual(deleted['deleted'], 1)

        status, orphans = self.server.get('/api/orphans')
        self.assertEqual(status, 200)
        self.assertEqual(orphans['total'], 2)

        status, cleaned = self.server.post('/api/orphans', {'clean': True})
        self.assertEqual(status, 200)
        self.assertEqual(cleaned['removed_total'], 2)
        self.assertEqual(cleaned['total'], 0)

        status, info = self.server.get('/api/info')
        self.assertEqual(status, 200)
        self.assertEqual(info['dirty'], 3)

        status, uploaded = self.server.post('/api/upload', {'backup': True, 'ver': 'test'})
        self.assertEqual(status, 200)
        backup = uploaded.get('backup')
        self.assertTrue(backup and os.path.isfile(backup))
        con = sqlite3.connect(backup)
        try:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM BaseItems').fetchone()[0], 25)
            self.assertEqual(con.execute('PRAGMA quick_check').fetchone()[0], 'ok')
        finally:
            con.close()
        con = sqlite3.connect(self.db)
        try:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM BaseItems').fetchone()[0], 24)
        finally:
            con.close()

        status, info = self.server.get('/api/info')
        self.assertEqual(status, 200)
        self.assertEqual(info['dirty'], 0)
        status, history = self.server.get('/api/history')
        self.assertEqual(status, 200)
        self.assertEqual(len(history['records']), 1)
        status, orphans = self.server.get('/api/orphans')
        self.assertEqual(status, 200)
        self.assertEqual(orphans['total'], 0)


if __name__ == '__main__':
    unittest.main()
