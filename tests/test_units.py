import importlib.util
import os
import re
import shutil
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

import jf_browser as j


ROOT = Path(__file__).resolve().parents[1]


class FakeRequest:
    def __init__(self, headers=None):
        self.headers = headers or {}


class HostHeaderTests(unittest.TestCase):
    def setUp(self):
        self.old = j.CFG.get('own_host')
        j.CFG['token'] = '0123456789abcdef0123456789abcdef'

    def tearDown(self):
        j.CFG['own_host'] = self.old

    def test_localhost_and_own_host(self):
        j.CFG['own_host'] = '127.0.0.1'
        self.assertTrue(j.host_ok('127.0.0.1:8099'))
        self.assertTrue(j.host_ok('localhost:8099'))
        self.assertTrue(j.host_ok('[::1]:8099'))
        self.assertFalse(j.host_ok('192.168.1.10:8099'))
        self.assertFalse(j.host_ok('evil.example'))

    def test_specific_lan_host(self):
        j.CFG['own_host'] = '192.168.1.10'
        self.assertTrue(j.host_ok('192.168.1.10:8099'))
        self.assertFalse(j.host_ok('192.168.1.11:8099'))

    def test_wildcard_allows_ip_but_not_domain(self):
        j.CFG['own_host'] = '0.0.0.0'
        self.assertTrue(j.host_ok('192.168.1.50:8099'))
        self.assertTrue(j.host_ok('10.0.0.2:8099'))
        self.assertFalse(j.host_ok('evil.example'))


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.old = j.CFG.get('token')
        j.CFG['token'] = '0123456789abcdef0123456789abcdef'

    def tearDown(self):
        j.CFG['token'] = self.old

    def test_cookie_header_and_query_token(self):
        h = FakeRequest({'Cookie': 'jfb_token=0123456789abcdef0123456789abcdef'})
        self.assertTrue(j.get_authorized(h, {}))
        h2 = FakeRequest({'X-Token': '0123456789abcdef0123456789abcdef'})
        self.assertTrue(j.get_authorized(h2, {}))
        self.assertTrue(j.get_authorized(FakeRequest(), {'t': ['0123456789abcdef0123456789abcdef']}))
        self.assertFalse(j.get_authorized(FakeRequest(), {}))


class BakRetentionTests(unittest.TestCase):
    def setUp(self):
        self.old_keep = j.SETTINGS.get('bak_keep')
        self.old_session = j.STATE.get('session_bak')
        self.tmp = tempfile.mkdtemp(prefix='jfbak_')

    def tearDown(self):
        j.SETTINGS['bak_keep'] = self.old_keep
        j.STATE['session_bak'] = self.old_session
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_default_keep_is_ten(self):
        j.SETTINGS.pop('bak_keep', None)
        self.assertEqual(j.bak_keep_limit(), 10)

    def test_keeps_session_bak_and_newest_old(self):
        db = os.path.join(self.tmp, 'jellyfin.db')
        with open(db, 'wb') as f:
            f.write(b'db')
        current = os.path.join(self.tmp, 'jellyfin.db-2999-01-01_00-00-00.bak')
        old1 = os.path.join(self.tmp, 'jellyfin.db-1999-01-01_00-00-00.bak')
        old2 = os.path.join(self.tmp, 'jellyfin.db-2000-01-01_00-00-00.bak')
        for p in (current, old1, old2):
            with open(p, 'wb') as f:
                f.write(b'bak')
        now = time.time()
        os.utime(current, (now + 30, now + 30))
        os.utime(old1, (now, now))
        os.utime(old2, (now + 10, now + 10))
        j.STATE['session_bak'] = current
        j.SETTINGS['bak_keep'] = 2
        removed = j.prune_bak_files(db)
        self.assertEqual(removed, 1)
        self.assertTrue(os.path.exists(current))
        self.assertTrue(os.path.exists(old2))
        self.assertFalse(os.path.exists(old1))


class HistoryLimitTests(unittest.TestCase):
    def setUp(self):
        self.old_dir, self.old_index = j.HISTORY_DIR, j.HISTORY_INDEX
        self.old_session = j.STATE.get('session_id')
        self.old_max = j.SETTINGS.get('history_max')
        self.old_size = j.SETTINGS.get('history_max_size_mb')
        self.tmp = tempfile.mkdtemp(prefix='jfhist_')
        j.HISTORY_DIR = self.tmp
        j.HISTORY_INDEX = os.path.join(self.tmp, 'index.json')
        j.STATE['session_id'] = 'session-test'
        j.SETTINGS['history_max'] = 5
        j.SETTINGS['history_max_size_mb'] = 1

    def tearDown(self):
        j.HISTORY_DIR, j.HISTORY_INDEX = self.old_dir, self.old_index
        j.STATE['session_id'] = self.old_session
        j.SETTINGS['history_max'] = self.old_max
        j.SETTINGS['history_max_size_mb'] = self.old_size
        shutil.rmtree(self.tmp, ignore_errors=True)

    def record(self, rid, size, role=None):
        folder = os.path.join(j.HISTORY_DIR, rid)
        os.makedirs(folder)
        path = os.path.join(folder, 'jellyfin.db')
        with open(path, 'wb') as f:
            f.write(b'x' * size)
        rec = {'id': rid, 'ts': rid, 'ver': '', 'removed': 0, 'added': 0,
               'items_removed': [], 'items_added': [], 'size': size,
               'file': rid + '/jellyfin.db', 'db_name': 'jellyfin.db'}
        if role:
            rec.update(role=role, session=j.STATE['session_id'])
        return rec

    def test_size_limit_keeps_newest_and_anchor(self):
        old1 = self.record('old1', 600000)
        old2 = self.record('old2', 600000)
        new = self.record('new', 600000)
        anchor = self.record('anchor', 100000, role='anchor')
        j.history_save([new, old2, old1, anchor])
        recs = j.history_prune()
        ids = {r['id'] for r in recs}
        self.assertIn('new', ids)
        self.assertIn('anchor', ids)
        self.assertNotIn('old1', ids)
        self.assertNotIn('old2', ids)
        self.assertTrue(os.path.exists(j.history_file(anchor)))
        self.assertFalse(os.path.exists(j.history_file(old1)))
        self.assertFalse(os.path.exists(j.history_file(old2)))


class JfVersionCacheTests(unittest.TestCase):
    def setUp(self):
        self.old_ver = j.SETTINGS.get('jf_version')
        self.old_save = j.save_settings
        j.save_settings = lambda: True

    def tearDown(self):
        j.SETTINGS['jf_version'] = self.old_ver
        j.save_settings = self.old_save

    def test_latest_detection_wins(self):
        j.remember_jf_version({'Version': '10.10.7'})
        self.assertEqual(j.SETTINGS['jf_version'], '10.10.7')
        j.remember_jf_version({'Version': '10.11.0'})
        self.assertEqual(j.SETTINGS['jf_version'], '10.11.0')
        self.assertEqual(j.last_known_jf_version(), '10.11.0')


class ValidDbFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='jfvalid_')
        self.db = os.path.join(self.tmp, 'jellyfin.db')
        con = sqlite3.connect(self.db)
        con.execute('CREATE TABLE BaseItems (Id TEXT PRIMARY KEY)')
        con.commit()
        con.close()
        self.old_ro = j.ro_connect

    def tearDown(self):
        j.ro_connect = self.old_ro
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_permission_error_defers_to_load(self):
        def deny(path):
            raise sqlite3.OperationalError('unable to open database file')
        j.ro_connect = deny
        self.assertEqual(j.valid_db_file(self.db), os.path.abspath(self.db))

    def test_missing_table_with_wal_defers_to_load(self):
        with open(self.db + '-wal', 'wb') as f:
            f.write(b'')
        def no_table(path):
            raise sqlite3.OperationalError('no such table: BaseItems')
        j.ro_connect = no_table
        self.assertEqual(j.valid_db_file(self.db), os.path.abspath(self.db))

    def test_plain_sqlite_without_baseitems_is_rejected(self):
        other = os.path.join(self.tmp, 'other.db')
        con = sqlite3.connect(other)
        con.execute('CREATE TABLE Something (Id TEXT)')
        con.commit()
        con.close()
        with self.assertRaises(ValueError):
            j.valid_db_file(other)


class VersionTests(unittest.TestCase):
    def test_app_version_matches_changelog(self):
        text = (ROOT / 'Versions.md').read_text(encoding='utf-8')
        match = re.search(r'^### (\d+\.\d+\.\d+)', text, re.M)
        self.assertIsNotNone(match)
        self.assertEqual(j.APP_VERSION, match.group(1))


class OrphanHelperTests(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(':memory:')
        self.con.execute('CREATE TABLE BaseItems (Id TEXT PRIMARY KEY)')
        self.con.execute("INSERT INTO BaseItems VALUES ('ok')")
        self.con.execute('CREATE TABLE Child (ItemId TEXT, Name TEXT, Blob BLOB)')
        self.con.execute("INSERT INTO Child VALUES ('missing', 'x', ?)", (b'abc',))
        self.con.execute("INSERT INTO Child VALUES ('', 'empty', NULL)")
        self.con.execute("INSERT INTO Child VALUES ('00000000-0000-0000-0000-000000000000', 'zero', NULL)")
        self.con.execute("INSERT INTO Child VALUES ('ok', 'ok', NULL)")
        self.con.commit()

    def tearDown(self):
        self.con.close()

    def test_empty_and_zero_guid_are_not_orphans(self):
        self.assertEqual(j.orphan_count(self.con, 'Child', ['ItemId']), 1)

    def test_samples_include_values_and_mask_blobs(self):
        samples = j.orphan_samples(self.con, 'Child', ['ItemId'])
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0]['ItemId'], 'missing')
        self.assertEqual(samples[0]['Name'], 'x')
        self.assertIn('<BLOB', samples[0]['Blob'])


class ReleaseFilterTests(unittest.TestCase):
    def test_light_release_allowlist(self):
        spec = importlib.util.spec_from_file_location('build_release', ROOT / 'scripts' / 'build_release.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(mod.included('jf_browser.py'))
        self.assertTrue(mod.included('README.md'))
        self.assertTrue(mod.included('ui/index.html'))
        self.assertFalse(mod.included('DB/jellyfin_mini.db'))
        self.assertFalse(mod.included('potencjalne poprawki/analiza.md'))
        self.assertFalse(mod.included('tmp/jfdb_x/work.db'))


if __name__ == '__main__':
    unittest.main()
