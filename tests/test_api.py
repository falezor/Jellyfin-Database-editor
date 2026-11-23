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

import jf_browser as j

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
        CREATE TABLE AncestorIds (
            ItemId TEXT REFERENCES BaseItems(Id),
            AncestorId TEXT REFERENCES BaseItems(Id)
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
        con.execute('INSERT INTO BaseItemImageInfos VALUES (?,?,?,?)',
                    ('img-empty', '', 0, ''))
        con.execute('INSERT INTO AncestorIds VALUES (?,?)',
                    ('missing-item', 'missing-ancestor'))
        con.execute('INSERT INTO AncestorIds VALUES (?,?)', ('', ''))
        con.execute('INSERT INTO AncestorIds VALUES (?,?)',
                    ('00000000-0000-0000-0000-000000000000',
                     '00000000-0000-0000-0000-000000000000'))
        con.commit()
    finally:
        con.close()


def create_advanced_db(path):
    """Rich hierarchy used by the advanced-editor tests."""
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
            Data TEXT,
            ForcedSortName TEXT,
            OriginalTitle TEXT
        );
        CREATE TABLE BaseItemImageInfos (
            Id TEXT PRIMARY KEY,
            ItemId TEXT,
            ImageType INTEGER,
            Path TEXT
        );
        """)

        def row(iid, name, typ, path='', parent='', top='', series='', season='',
                idx=None, pidx=None, year=None, data=None, forced=None,
                original=None, version=None):
            return (iid, name, name, typ, path, parent, top, series, season, '',
                    idx, pidx, year, 0, version, data, forced, original)

        tv_series = 'MediaBrowser.Controller.Entities.TV.Series'
        tv_season = 'MediaBrowser.Controller.Entities.TV.Season'
        tv_episode = 'MediaBrowser.Controller.Entities.TV.Episode'
        movie = 'MediaBrowser.Controller.Entities.Movies.Movie'
        rows = [
            row('series-1', 'Series One', tv_series, '/media/tv/one'),
            row('series-2', 'Series Two', tv_series, '/media/tv/two'),
            row('season-1', 'Season 1', tv_season, parent='series-1', top='series-1',
                series='series-1', idx=1, pidx=1),
            row('season-2', 'Season 2', tv_season, parent='series-2', top='series-2',
                series='series-2', idx=2, pidx=2),
            row('ep-1', 'Episode One', tv_episode, '/media/tv/one/s01e01.mkv',
                parent='season-1', top='series-1', series='series-1', season='season-1',
                idx=1, pidx=1),
            row('ep-2', 'Episode Two', tv_episode, '/media/tv/one/s01e02.mkv',
                parent='season-1', top='series-1', series='series-1', season='season-1',
                idx=2, pidx=1),
            row('ep-3', 'Episode Three', tv_episode, '/media/tv/two/s02e01.mkv',
                parent='season-2', top='series-2', series='series-2', season='season-2',
                idx=1, pidx=2),
            row('movie-1', 'Movie One', movie, '/media/movies/one.mkv', year=2001,
                data='{"Overview":"Old overview","Tags":["a","b"]}',
                forced='One, The', original='The One'),
            row('movie-2', 'Movie Two', movie, '/media/movies/two.mkv'),
            row('movie-3', 'Movie Three', movie, '/media/movies/three.mkv'),
            row('movie-4', 'Movie Four', movie, '/media/movies/four.mkv'),
            row('movie-5', 'Movie Five', movie, '/media/movies/five.mkv'),
            row('basic-1', 'Basic One', movie, '/media/movies/basic.mkv'),
            row('basic-2', 'Basic Two', movie, '/media/movies/basic2.mkv'),
            row('flag-1', 'Flag One', movie, '/media/movies/flag.mkv'),
            row('target-long', 'Target Long', movie, '/media/movies/target.mkv'),
            row('cyc-a', 'Cycle A', movie, '/media/movies/cyc-a.mkv'),
            row('cyc-b', 'Cycle B', movie, '/media/movies/cyc-b.mkv'),
            row('cyc-c', 'Cycle C', movie, '/media/movies/cyc-c.mkv'),
            row('movie-uni', 'Zażółć gęślą jaźń 🎬', movie,
                'D:\\Media\\Filmy\\Остров.mkv',
                data='{"Title":"Остров","Quote":"\\"x\\""}'),
            row('movie-legacy', 'Legacy Data', movie, '/media/movies/legacy.mkv',
                data='not json'),
        ]
        for i in range(111):
            parent = f'chain-{i + 1:03d}' if i < 110 else 'target-long'
            rows.append(row(f'chain-{i:03d}', f'Chain {i}', movie,
                            f'/media/movies/chain-{i:03d}.mkv', parent=parent))
        con.executemany('INSERT INTO BaseItems VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', rows)
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
            json.dump({'data_dir': self.data_dir, 'jf_version': '10.10.7'}, f)
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
                if self.page is None:
                    r = self.opener.open(self.base + '/', timeout=0.4)
                    self.page = r.read().decode('utf-8')
                    m = TOKEN_RE.search(self.page)
                    if not m:
                        raise RuntimeError('token missing from page')
                    self.token = m.group(1)
                req = urllib.request.Request(
                    self.base + '/api/info',
                    headers={'X-Token': self.token, 'X-Lang': 'en'},
                )
                with self.opener.open(req, timeout=0.4) as r:
                    info = json.loads(r.read().decode('utf-8'))
                if not info.get('nodb'):
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
        self.assertIn(f'<span id="version">{j.APP_VERSION}</span>', self.server.page)
        self.assertNotIn('__VERSION__', self.server.page)
        self.assertLess(self.server.page.index('id="topmode"'), self.server.page.index('id="langnow"'))
        self.assertLess(self.server.page.index('id="langnow"'), self.server.page.index('id="version"'))
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

    def test_service_auto_setting(self):
        status, info = self.server.get('/api/info')
        self.assertEqual(status, 200)
        self.assertFalse(info.get('service_auto'))

        status, saved = self.server.post('/api/settings', {'service_auto': True})
        self.assertEqual(status, 200)
        self.assertTrue(saved['service_auto'])
        self.assertTrue(saved['persisted'])
        with open(self.server.config, encoding='utf-8') as f:
            self.assertTrue(json.load(f)['service_auto'])

        status, info = self.server.get('/api/info')
        self.assertEqual(status, 200)
        self.assertTrue(info['service_auto'])

        status, saved = self.server.post('/api/settings', {'service_auto': False})
        self.assertEqual(status, 200)
        self.assertFalse(saved['service_auto'])

    def test_data_flow(self):
        status, rows = self.server.get('/api/list?limit=5&offset=20')
        self.assertEqual(status, 200)
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]['Name'], 'Item 020')

        status, only = self.server.get('/api/list?sort=only&limit=5&offset=0')
        self.assertEqual(status, 200)
        self.assertEqual(len(only), 5)

        status, item = self.server.get('/api/item?id=item-010')
        self.assertEqual(status, 200)
        self.assertEqual(item['Name'], 'Item 010')
        status, edited = self.server.post('/api/edit', {
            'id': 'item-010',
            'fields': {'name': 'Renamed 010', 'productionyear': 2021, 'seriesname': ''},
        })
        self.assertEqual(status, 200)
        self.assertEqual(edited['dirty'], 1)
        self.assertEqual(edited['edited'], 1)
        status, item = self.server.get('/api/item?id=item-010')
        self.assertEqual(status, 200)
        self.assertEqual(item['Name'], 'Renamed 010')
        self.assertEqual(item['ProductionYear'], 2021)
        self.assertIsNone(item['SeriesName'])
        status, _ = self.server.post('/api/edit', {'id': 'item-010', 'fields': {'name': ''}})
        self.assertEqual(status, 400)
        status, _ = self.server.post('/api/edit', {'id': 'missing', 'fields': {'name': 'x'}})
        self.assertEqual(status, 400)
        status, advanced = self.server.post('/api/edit', {
            'id': 'item-010', 'advanced': True,
            'fields': {
                'path': '/media/renamed.mkv',
                'data': '{"Overview": "Edited overview"}',
                'parentid': 'item-000',
            },
        })
        self.assertEqual(status, 200)
        self.assertEqual(advanced['dirty'], 1)
        status, item = self.server.get('/api/item?id=item-010')
        self.assertEqual(status, 200)
        self.assertEqual(item['Path'], '/media/renamed.mkv')
        self.assertEqual(item['ParentId'], 'item-000')
        self.assertEqual(json.loads(item['Data']), {'Overview': 'Edited overview'})
        status, _ = self.server.post('/api/edit', {
            'id': 'item-010', 'advanced': True, 'fields': {'data': '{bad'}})
        self.assertEqual(status, 400)
        status, _ = self.server.post('/api/edit', {
            'id': 'item-010', 'advanced': True, 'fields': {'parentid': 'missing'}})
        self.assertEqual(status, 400)
        status, _ = self.server.post('/api/edit', {
            'id': 'item-010', 'advanced': True, 'fields': {'parentid': 'item-010'}})
        self.assertEqual(status, 400)

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
        self.assertEqual(orphans['total'], 2)
        ancestor = next(x for x in orphans['tables'] if x['table'] == 'AncestorIds')
        self.assertEqual(ancestor['columns'], ['AncestorId', 'ItemId'])
        self.assertEqual(ancestor['rows'], 1)
        self.assertEqual(ancestor['samples'][0]['ItemId'], 'missing-item')
        self.assertEqual(ancestor['samples'][0]['AncestorId'], 'missing-ancestor')
        img = next(x for x in orphans['tables'] if x['table'] == 'BaseItemImageInfos')
        self.assertEqual(img['samples'][0]['ItemId'], 'missing-item')

        status, deleted = self.server.post('/api/delete', {'ids': ['item-000']})
        self.assertEqual(status, 200)
        self.assertEqual(deleted['deleted'], 1)

        status, orphans = self.server.get('/api/orphans')
        self.assertEqual(status, 200)
        self.assertEqual(orphans['total'], 3)

        status, cleaned = self.server.post('/api/orphans', {'clean': True})
        self.assertEqual(status, 200)
        self.assertEqual(cleaned['removed_total'], 3)
        self.assertEqual(cleaned['total'], 0)

        status, info = self.server.get('/api/info')
        self.assertEqual(status, 200)
        self.assertEqual(info['dirty'], 5)

        status, uploaded = self.server.post('/api/upload', {'backup': True})
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
            self.assertEqual(con.execute(
                "SELECT COUNT(*) FROM AncestorIds WHERE ItemId IN ('', '00000000-0000-0000-0000-000000000000')"
            ).fetchone()[0], 2)
            self.assertEqual(con.execute(
                "SELECT COUNT(*) FROM BaseItemImageInfos WHERE ItemId = ''").fetchone()[0], 1)
        finally:
            con.close()

        status, info = self.server.get('/api/info')
        self.assertEqual(status, 200)
        self.assertEqual(info['dirty'], 0)
        status, history = self.server.get('/api/history')
        self.assertEqual(status, 200)
        self.assertEqual(len(history['records']), 2)
        self.assertEqual(history['bak_keep'], 10)
        anchors = [r for r in history['records'] if r.get('protected')]
        self.assertEqual(len(anchors), 1)
        self.assertEqual(anchors[0]['role'], 'anchor')
        self.assertEqual(anchors[0]['ver'], '10.10.7')
        self.assertTrue(all(r['ver'] == '10.10.7' for r in history['records']))
        self.assertTrue(os.path.isfile(os.path.join(self.server.data_dir, 'history',
                                                     anchors[0]['file'])))
        edited_recs = [r for r in history['records'] if r.get('edited')]
        self.assertEqual(len(edited_recs), 1)
        self.assertEqual(edited_recs[0]['edited'], 1)
        self.assertTrue(any(x['Id'] == 'item-010' for x in edited_recs[0]['items_edited']))

        def baks():
            return [n for n in os.listdir(os.path.dirname(self.db))
                    if n.startswith('jellyfin.db-') and n.endswith('.bak')]

        self.assertEqual(len(baks()), 1)

        status, _ = self.server.post('/api/delete', {'ids': ['item-001']})
        self.assertEqual(status, 200)
        status, uploaded2 = self.server.post('/api/upload', {'backup': True})
        self.assertEqual(status, 200)
        self.assertIsNone(uploaded2.get('backup'))
        self.assertEqual(len(baks()), 1)
        status, history = self.server.get('/api/history')
        self.assertEqual(status, 200)
        self.assertEqual(len(history['records']), 3)

        status, cleared = self.server.post('/api/history', {'action': 'clear'})
        self.assertEqual(status, 200)
        self.assertEqual(cleared['cleared'], 2)
        self.assertEqual(cleared['kept'], 1)
        status, history = self.server.get('/api/history')
        self.assertEqual(status, 200)
        self.assertEqual(len(history['records']), 1)
        self.assertTrue(history['records'][0]['protected'])

        status, orphans = self.server.get('/api/orphans')
        self.assertEqual(status, 200)
        self.assertEqual(orphans['total'], 0)

        status, _ = self.server.post('/api/delete', {'ids': ['item-003']})
        self.assertEqual(status, 200)
        status, backup = self.server.post('/api/backup', {})
        self.assertEqual(status, 200)
        self.assertEqual(backup['source'], 'original')
        backup_path = os.path.join(self.server.data_dir, 'backups', backup['file'])
        self.assertTrue(os.path.isfile(backup_path))
        con = sqlite3.connect(backup_path)
        try:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM BaseItems').fetchone()[0], 23)
            self.assertEqual(
                con.execute("SELECT COUNT(*) FROM BaseItems WHERE Id='item-003'").fetchone()[0], 1)
        finally:
            con.close()

        status, working_backup = self.server.post('/api/backup', {'working': True})
        self.assertEqual(status, 200)
        self.assertEqual(working_backup['source'], 'working')
        working_path = os.path.join(
            self.server.data_dir, 'backups', 'working-copy', working_backup['file'])
        self.assertTrue(os.path.isfile(working_path))
        con = sqlite3.connect(working_path)
        try:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM BaseItems').fetchone()[0], 22)
        finally:
            con.close()

        status, _ = self.server.post('/api/delete', {'ids': ['item-002']})
        self.assertEqual(status, 200)
        status, reverted = self.server.post(
            '/api/backups', {'action': 'revert', 'id': backup['id'], 'backup': False})
        self.assertEqual(status, 200)
        self.assertEqual(reverted['id'], backup['id'])
        con = sqlite3.connect(self.db)
        try:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM BaseItems').fetchone()[0], 23)
        finally:
            con.close()
        status, info = self.server.get('/api/info')
        self.assertEqual(status, 200)
        self.assertEqual(info['dirty'], 0)
        status, backups = self.server.get('/api/backups')
        self.assertEqual(status, 200)
        self.assertEqual(len(backups['records']), 1)

        old_data = self.server.data_dir
        new_data = os.path.join(self.server.tmp, 'data2')
        status, moved = self.server.post('/api/settings', {'data_dir': new_data, 'force': True})
        self.assertEqual(status, 200)
        self.assertEqual(moved['data_dir'], os.path.abspath(new_data))
        self.assertTrue(moved['reloaded'])
        self.assertGreaterEqual(moved['moved']['history'], 1)
        self.assertGreaterEqual(moved['moved']['backups'], 1)
        self.server.data_dir = new_data
        self.assertFalse(os.path.exists(os.path.join(old_data, 'history')))
        self.assertFalse(os.path.exists(os.path.join(old_data, 'backups')))
        self.assertTrue(os.path.isfile(os.path.join(new_data, 'history', 'index.json')))
        self.assertTrue(os.path.isfile(os.path.join(new_data, 'backups', backup['file'])))
        self.assertTrue(os.path.isfile(os.path.join(
            new_data, 'backups', 'working-copy', working_backup['file'])))

        status, history = self.server.get('/api/history')
        self.assertEqual(status, 200)
        self.assertEqual(len(history['records']), 1)
        self.assertTrue(os.path.isfile(os.path.join(
            new_data, 'history', history['records'][0]['file'])))
        status, backups = self.server.get('/api/backups')
        self.assertEqual(status, 200)
        self.assertEqual(len(backups['records']), 1)
        status, info = self.server.get('/api/info')
        self.assertEqual(status, 200)
        self.assertFalse(info['nodb'])
        self.assertEqual(info['dirty'], 0)


class AdvancedEditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='jfadv_')
        cls.db = os.path.join(cls.tmp, 'jellyfin.db')
        create_advanced_db(cls.db)
        cls.server = Server(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.server.close()
        import shutil
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def item(self, rid):
        status, item = self.server.get('/api/item?id=' + rid)
        self.assertEqual(status, 200, item)
        return item

    def dirty(self):
        status, info = self.server.get('/api/info')
        self.assertEqual(status, 200, info)
        return info['dirty']

    def edit(self, rid, fields, advanced=True):
        return self.server.post('/api/edit', {
            'id': rid, 'fields': fields, 'advanced': advanced})

    def ok(self, rid, fields, advanced=True):
        status, body = self.edit(rid, fields, advanced)
        self.assertEqual(status, 200, body)
        return body

    def rejected(self, rid, fields, advanced=True):
        before = self.item(rid)
        status, body = self.edit(rid, fields, advanced)
        self.assertEqual(status, 400, body)
        self.assertEqual(self.item(rid), before)
        return body

    def original_row(self, rid):
        con = sqlite3.connect(self.db)
        try:
            return con.execute(
                'SELECT Name, Path, Data, ParentId FROM BaseItems WHERE Id=?',
                (rid,)).fetchone()
        finally:
            con.close()

    def test_01_round_trip_all_advanced_fields(self):
        before = self.dirty()
        data_text = (' { "Overview" : "Line 1\\nLine 2", "Tags" : ["a", "b"], '
                     '"Nested" : {"n": 1, "ok": true} } ')
        expected_data = {
            'Overview': 'Line 1\nLine 2',
            'Tags': ['a', 'b'],
            'Nested': {'n': 1, 'ok': True},
        }
        fields = {
            'path': '  /media/tv/one/s01e01 - remux.mkv  ',
            'data': data_text,
            'parentid': '  season-2  ',
            'topparentid': 'series-2',
            'seriesid': 'series-2',
            'seasonid': 'season-2',
            'primaryversionid': 'ep-3',
            'forcedsortname': '  Episode One  ',
            'originaltitle': '  Original One  ',
        }
        res = self.ok('ep-1', fields)
        self.assertEqual(res['dirty'], before + 1)
        item = self.item('ep-1')
        self.assertEqual(item['Path'], '/media/tv/one/s01e01 - remux.mkv')
        self.assertEqual(item['ParentId'], 'season-2')
        self.assertEqual(item['TopParentId'], 'series-2')
        self.assertEqual(item['SeriesId'], 'series-2')
        self.assertEqual(item['SeasonId'], 'season-2')
        self.assertEqual(item['PrimaryVersionId'], 'ep-3')
        self.assertEqual(item['ForcedSortName'], 'Episode One')
        self.assertEqual(item['OriginalTitle'], 'Original One')
        self.assertEqual(item['Name'], 'Episode One')
        self.assertEqual(item['Data'], json.dumps(
            expected_data, ensure_ascii=False, separators=(',', ':')))

        res2 = self.ok('ep-1', {'path': '/media/tv/one/changed.mkv'})
        self.assertEqual(res2['dirty'], before + 1)
        self.assertEqual(res2['edited'], res['edited'])
        item2 = self.item('ep-1')
        self.assertEqual(item2['Path'], '/media/tv/one/changed.mkv')
        self.assertEqual(item2['Data'], item['Data'])
        self.assertEqual(item2['ParentId'], 'season-2')
        self.assertEqual(item2['ForcedSortName'], 'Episode One')

    def test_02_data_json_validation(self):
        self.ok('movie-2', {'data': '{"keep":true}'})
        for bad in ('{bad', '[1,2]', '"text"', '42', 'null', 'true',
                    '{"x": NaN}', '{"x": Infinity}', '{"x": -Infinity}'):
            self.rejected('movie-2', {'data': bad})
        self.rejected('movie-2', {'data': 123})
        self.assertEqual(self.item('movie-2')['Data'], '{"keep":true}')

        payload = ('{"u":"Zażółć gęślą jaźń 🎬","quote":"\\"x\\"",'
                   '"arr":[1,true,null],"nested":{"a":1}}')
        self.ok('movie-2', {'data': payload})
        item = self.item('movie-2')
        self.assertEqual(json.loads(item['Data']), json.loads(payload))
        self.assertIn('Zażółć', item['Data'])
        self.assertNotIn('"u": "', item['Data'])

        self.ok('movie-2', {'data': ''})
        self.assertIsNone(self.item('movie-2')['Data'])
        self.ok('movie-2', {'data': '   '})
        self.assertIsNone(self.item('movie-2')['Data'])
        self.ok('movie-2', {'data': '{}'})
        self.assertEqual(self.item('movie-2')['Data'], '{}')
        self.ok('movie-2', {'data': None})
        self.assertIsNone(self.item('movie-2')['Data'])

    def test_03_path_validation(self):
        self.rejected('movie-3', {'path': 123})
        self.rejected('movie-3', {'path': 'a' * 4097})
        self.ok('movie-3', {'path': 'a' * 4096})
        self.assertEqual(len(self.item('movie-3')['Path']), 4096)
        self.ok('movie-3', {'path': '  /media/ünïcode/Остров.mkv  '})
        self.assertEqual(self.item('movie-3')['Path'], '/media/ünïcode/Остров.mkv')
        sql_path = "'; DROP TABLE BaseItems; --"
        self.ok('movie-3', {'path': sql_path})
        self.assertEqual(self.item('movie-3')['Path'], sql_path)
        status, _ = self.server.get('/api/list?limit=1')
        self.assertEqual(status, 200)
        self.ok('movie-3', {'path': '  /media/a\nb.mkv  '})
        self.assertEqual(self.item('movie-3')['Path'], '/media/a\nb.mkv')
        self.ok('movie-3', {'path': ''})
        self.assertIsNone(self.item('movie-3')['Path'])

    def test_04_hierarchy_validation(self):
        valid = {
            'parentid': 'series-1', 'topparentid': 'series-1',
            'seriesid': 'series-1', 'seasonid': 'season-1',
            'primaryversionid': 'ep-3',
        }
        self.ok('movie-4', valid)
        for key in valid:
            self.rejected('movie-4', {key: 'missing-' + key})
        self.ok('movie-4', {key: '' for key in valid})
        for key in valid:
            self.rejected('movie-4', {key: 'movie-4'})
        self.ok('movie-4', {'parentid': '  series-2  '})
        self.assertEqual(self.item('movie-4')['ParentId'], 'series-2')
        self.rejected('movie-4', {'parentid': 123})
        self.rejected('movie-4', {'parentid': 'x' * 501})

        self.ok('cyc-b', {'parentid': 'cyc-a'})
        self.ok('cyc-c', {'parentid': 'cyc-b'})
        self.rejected('cyc-a', {'parentid': 'cyc-c'})
        self.assertIn(self.item('cyc-a')['ParentId'], ('', None))

        # a chain longer than the old 100-node guard must still be rejected
        self.rejected('target-long', {'parentid': 'chain-000'})
        self.assertIn(self.item('target-long')['ParentId'], ('', None))
        self.ok('movie-4', {'parentid': 'chain-110'})
        self.assertEqual(self.item('movie-4')['ParentId'], 'chain-110')

        status, _ = self.server.get('/api/item?id=missing-parent')
        self.assertEqual(status, 400)
        before_path = self.item('movie-4')['Path']
        self.rejected('movie-4', {
            'path': '/atomic/should/not/apply', 'parentid': 'missing-parent'})
        self.assertEqual(self.item('movie-4')['Path'], before_path)

    def test_05_advanced_flag_and_readonly(self):
        self.ok('flag-1', {
            'name': 'Flag Basic', 'path': '/ignored/path',
            'data': '{"ignored":true}', 'parentid': 'season-1',
            'forcedsortname': 'Ignored', 'originaltitle': 'Ignored',
        }, advanced=False)
        item = self.item('flag-1')
        self.assertEqual(item['Name'], 'Flag Basic')
        self.assertEqual(item['Path'], '/media/movies/flag.mkv')
        self.assertIsNone(item['Data'])
        self.assertEqual(item['ParentId'], '')
        self.assertIsNone(item['ForcedSortName'])
        self.assertIsNone(item['OriginalTitle'])

        self.rejected('flag-1', {'path': '/ignored'}, advanced=False)
        self.rejected('flag-1', {'unknownfield': 'x'}, advanced=True)
        self.ok('flag-1', {'name': 'Flag Unknown', 'unknownfield': 'x'})
        self.assertEqual(self.item('flag-1')['Name'], 'Flag Unknown')

        self.rejected('flag-1', {'id': 'hacked', 'type': 'Hacked'})
        self.ok('flag-1', {'name': 'Flag Readonly', 'id': 'hacked', 'type': 'Hacked'})
        item = self.item('flag-1')
        self.assertEqual(item['Id'], 'flag-1')
        self.assertEqual(item['Type'], 'MediaBrowser.Controller.Entities.Movies.Movie')
        self.assertEqual(item['Name'], 'Flag Readonly')

        self.rejected('flag-1', {'path': '/ignored'}, advanced=False)
        self.ok('flag-1', {'name': 'Flag Mixed', 'path': '/ignored'}, advanced=False)
        self.assertEqual(self.item('flag-1')['Name'], 'Flag Mixed')
        self.assertEqual(self.item('flag-1')['Path'], '/media/movies/flag.mkv')

    def test_06_basic_validation(self):
        self.rejected('basic-1', {'name': ''})
        self.rejected('basic-1', {'name': '   '})
        self.rejected('basic-1', {'name': 123})
        self.ok('basic-1', {'name': 'x' * 500})
        self.assertEqual(len(self.item('basic-1')['Name']), 500)
        self.rejected('basic-1', {'name': 'x' * 501})
        self.ok('basic-1', {'sortname': '  ', 'seriesname': '  '})
        self.assertIsNone(self.item('basic-1')['SortName'])
        self.assertIsNone(self.item('basic-1')['SeriesName'])

        self.ok('basic-1', {'productionyear': 0})
        self.assertEqual(self.item('basic-1')['ProductionYear'], 0)
        self.ok('basic-1', {'productionyear': 9999})
        self.assertEqual(self.item('basic-1')['ProductionYear'], 9999)
        for bad in (-1, 10000, 'abc', 2020.5, True, False):
            self.rejected('basic-1', {'productionyear': bad})
        self.ok('basic-1', {'productionyear': '2020'})
        self.assertEqual(self.item('basic-1')['ProductionYear'], 2020)
        self.ok('basic-1', {'productionyear': 2020.0})
        self.assertEqual(self.item('basic-1')['ProductionYear'], 2020)
        self.ok('basic-1', {'productionyear': None})
        self.assertIsNone(self.item('basic-1')['ProductionYear'])

        self.ok('basic-1', {'indexnumber': 1000000})
        self.assertEqual(self.item('basic-1')['IndexNumber'], 1000000)
        self.rejected('basic-1', {'indexnumber': 1000001})
        self.rejected('basic-1', {'indexnumber': -1})
        self.ok('basic-1', {'parentindexnumber': 0})
        self.assertEqual(self.item('basic-1')['ParentIndexNumber'], 0)

        self.ok('basic-1', {
            'name': 'Basic All', 'sortname': 'Basic, All',
            'productionyear': 1999, 'indexnumber': 7,
            'parentindexnumber': 3, 'seriesname': 'Basic Series',
        })
        item = self.item('basic-1')
        self.assertEqual(item['Name'], 'Basic All')
        self.assertEqual(item['SortName'], 'Basic, All')
        self.assertEqual(item['ProductionYear'], 1999)
        self.assertEqual(item['IndexNumber'], 7)
        self.assertEqual(item['ParentIndexNumber'], 3)
        self.assertEqual(item['SeriesName'], 'Basic Series')

        self.rejected('basic-1', {'unknownbasic': 'x'})
        status, _ = self.edit('missing', {'name': 'x'})
        self.assertEqual(status, 400)
        status, _ = self.server.post('/api/edit', {'id': 'basic-1', 'fields': []})
        self.assertEqual(status, 400)
        status, _ = self.server.post('/api/edit', {'id': 1, 'fields': {'name': 'x'}})
        self.assertEqual(status, 400)

        before = self.dirty()
        name_before = self.item('basic-2')['Name']
        self.rejected('basic-2', {'name': 'Atomic', 'productionyear': 10000})
        self.assertEqual(self.item('basic-2')['Name'], name_before)
        self.assertEqual(self.dirty(), before)
        res = self.ok('basic-2', {'name': 'Atomic One'})
        self.assertEqual(res['dirty'], before + 1)
        res2 = self.ok('basic-2', {'name': 'Atomic Two'})
        self.assertEqual(res2['dirty'], before + 1)

    def test_07_original_untouched_and_reload(self):
        original = self.original_row('movie-1')
        self.ok('movie-1', {
            'name': 'Movie One Edited',
            'path': '/media/movies/edited.mkv',
            'data': '{"Overview":"Edited overview"}',
            'parentid': 'series-1',
        })
        item = self.item('movie-1')
        self.assertEqual(item['Name'], 'Movie One Edited')
        self.assertEqual(item['Path'], '/media/movies/edited.mkv')
        self.assertEqual(item['ParentId'], 'series-1')
        self.assertEqual(json.loads(item['Data']), {'Overview': 'Edited overview'})
        self.assertEqual(self.original_row('movie-1'), original)

        status, body = self.server.post('/api/reload', {})
        self.assertEqual(status, 200, body)
        item = self.item('movie-1')
        self.assertEqual(
            (item['Name'], item['Path'], item['Data'], item['ParentId']), original)
        self.assertEqual(self.dirty(), 0)

    def test_08_advanced_edit_survives_upload(self):
        self.ok('movie-1', {
            'name': 'Movie One Uploaded',
            'path': '/media/movies/uploaded.mkv',
            'data': '{"Overview":"Uploaded"}',
            'parentid': 'series-1',
            'forcedsortname': 'Movie One, Uploaded',
        })
        status, up = self.server.post(
            '/api/upload', {'backup': False, 'ver': '10.10.7', 'force_schema': False})
        self.assertEqual(status, 200, up)
        self.assertEqual(self.dirty(), 0)
        self.assertEqual(self.original_row('movie-1'), (
            'Movie One Uploaded', '/media/movies/uploaded.mkv',
            '{"Overview":"Uploaded"}', 'series-1'))
        item = self.item('movie-1')
        self.assertEqual(item['Name'], 'Movie One Uploaded')
        self.assertEqual(item['Path'], '/media/movies/uploaded.mkv')
        self.assertEqual(item['ParentId'], 'series-1')
        self.assertEqual(item['ForcedSortName'], 'Movie One, Uploaded')
        self.assertEqual(json.loads(item['Data']), {'Overview': 'Uploaded'})

        status, history = self.server.get('/api/history')
        self.assertEqual(status, 200, history)
        rec = history['records'][0]
        self.assertGreaterEqual(rec['edited'], 1)
        edited = rec.get('items_edited') or []
        self.assertTrue(any(x.get('Id') == 'movie-1' for x in edited))


class CompareApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import shutil
        cls.tmp = tempfile.mkdtemp(prefix='jfcmpapi_')
        cls.db = os.path.join(cls.tmp, 'jellyfin.db')
        create_test_db(cls.db)
        with open(os.path.join(cls.tmp, 'device.txt'), 'w', encoding='utf-8') as f:
            f.write('a' * 32)
        cls.bak = os.path.join(cls.tmp, 'jellyfin.db-2026-01-01_00-00-00.bak')
        shutil.copyfile(cls.db, cls.bak)
        cls.server = Server(cls.db)
        cls.other = os.path.join(cls.tmp, 'other.db')
        shutil.copyfile(cls.db, cls.other)
        con = sqlite3.connect(cls.other)
        try:
            con.execute("UPDATE BaseItems SET Name='Item 010 changed' WHERE Id='item-010'")
            con.execute("DELETE FROM BaseItems WHERE Id='item-011'")
            con.execute("INSERT INTO BaseItems (Id, Name, Type, Path, ProductionYear) VALUES "
                        "('item-999','New item','MediaBrowser.Controller.Entities.Movies.Movie','/media/new.mkv',2024)")
            con.commit()
        finally:
            con.close()
        cls.other_instance = os.path.join(cls.tmp, 'other-instance')
        os.makedirs(cls.other_instance)
        cls.other_instance_db = os.path.join(cls.other_instance, 'jellyfin.db')
        shutil.copyfile(cls.db, cls.other_instance_db)
        with open(os.path.join(cls.other_instance, 'device.txt'), 'w', encoding='utf-8') as f:
            f.write('b' * 32)

    @classmethod
    def tearDownClass(cls):
        cls.server.close()
        import shutil
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_options_lists_baks(self):
        status, options = self.server.get('/api/compare')
        self.assertEqual(status, 200, options)
        self.assertEqual(options['a'], self.db)
        self.assertIn(self.bak, [b['path'] for b in options['baks']])

    def test_compare_added_removed_changed(self):
        status, res = self.server.post('/api/compare', {'path': self.other})
        self.assertEqual(status, 200, res)
        self.assertEqual(res['counts']['changed'], 1)
        self.assertEqual(res['counts']['removed'], 1)
        self.assertEqual(res['counts']['added'], 1)
        self.assertEqual(res['instance']['verdict'], 'same')
        self.assertFalse(res['schema']['mismatch'])
        self.assertEqual(res['changed'][0]['id'], 'item-010')
        self.assertEqual(res['changed'][0]['fields'][0]['name'], 'Name')

    def test_compare_different_instance_device_txt(self):
        status, res = self.server.post('/api/compare', {'path': self.other_instance_db})
        self.assertEqual(status, 200, res)
        self.assertEqual(res['instance']['verdict'], 'different')
        self.assertEqual(res['instance']['reason'], 'device')

    def test_compare_missing_file(self):
        status, res = self.server.post('/api/compare', {'path': os.path.join(self.tmp, 'missing.db')})
        self.assertEqual(status, 400, res)
        self.assertIn('error', res)


class BakPromptApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='jfbakprompt_')
        cls.db = os.path.join(cls.tmp, 'jellyfin.db')
        create_test_db(cls.db)
        now = time.time()
        for i in range(21):
            p = os.path.join(cls.tmp, f'jellyfin.db-2026-01-{i + 1:02d}_00-00-00.bak')
            with open(p, 'wb') as f:
                f.write(b'bak')
            os.utime(p, (now + i, now + i))
        cls.server = Server(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.server.close()
        import shutil
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def baks(self):
        return [n for n in os.listdir(self.tmp)
                if n.startswith('jellyfin.db-') and n.endswith('.bak')]

    def test_prompt_dismiss_and_cleanup(self):
        status, info = self.server.get('/api/info')
        self.assertEqual(status, 200, info)
        prompt = info.get('bak_prompt')
        self.assertEqual(prompt['count'], 21)
        self.assertEqual(prompt['limit'], 10)
        self.assertEqual(len(self.baks()), 21)

        status, dismissed = self.server.post('/api/bak', {'action': 'dismiss'})
        self.assertEqual(status, 200, dismissed)
        status, info = self.server.get('/api/info')
        self.assertIsNone(info.get('bak_prompt'))
        self.assertEqual(len(self.baks()), 21)

        status, result = self.server.post('/api/bak', {'action': 'cleanup'})
        self.assertEqual(status, 200, result)
        self.assertEqual(result['removed'], 11)
        self.assertEqual(result['failed'], 0)
        self.assertEqual(len(self.baks()), 10)
        status, info = self.server.get('/api/info')
        self.assertIsNone(info.get('bak_prompt'))


if __name__ == '__main__':
    unittest.main()
