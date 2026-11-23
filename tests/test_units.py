import importlib.util
import os
import re
import shutil
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

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


class JfStopGuardTests(unittest.TestCase):
    def setUp(self):
        self.old = j.CFG.get('service_check')

    def tearDown(self):
        j.CFG['service_check'] = self.old

    def test_service_check_off_never_blocks(self):
        j.CFG['service_check'] = False
        with mock.patch.object(j, 'jf_detect',
                               side_effect=AssertionError('must not probe')):
            j.ensure_jf_stopped()

    def test_running_port_blocks(self):
        j.CFG['service_check'] = True
        detected = {'state': 'running', 'port': 8096, 'info': {'Version': '10.10.7'}}
        with mock.patch('jf_browser.shutil.which', return_value=None), \
                mock.patch.object(j, 'jf_detect', return_value=detected):
            with self.assertRaisesRegex(RuntimeError, '8096'):
                j.ensure_jf_stopped()

    def test_active_systemd_unit_blocks_without_probe(self):
        j.CFG['service_check'] = True
        done = mock.Mock(returncode=0)
        with mock.patch('jf_browser.shutil.which', return_value='/usr/bin/systemctl'), \
                mock.patch('jf_browser.subprocess.run', return_value=done), \
                mock.patch.object(j, 'jf_detect',
                                  side_effect=AssertionError('must not probe')):
            with self.assertRaises(RuntimeError):
                j.ensure_jf_stopped()

    def test_stopped_jellyfin_is_allowed(self):
        j.CFG['service_check'] = True
        detected = {'state': 'off', 'port': 8096, 'info': None}
        with mock.patch('jf_browser.shutil.which', return_value=None), \
                mock.patch.object(j, 'jf_detect', return_value=detected):
            j.ensure_jf_stopped()


class BakRetentionTests(unittest.TestCase):
    def setUp(self):
        self.old_keep = j.SETTINGS.get('bak_keep')
        self.old_session = j.STATE.get('session_bak')
        self.old_prompt = j.STATE.get('bak_prompt')
        self.tmp = tempfile.mkdtemp(prefix='jfbak_')

    def tearDown(self):
        j.SETTINGS['bak_keep'] = self.old_keep
        j.STATE['session_bak'] = self.old_session
        j.STATE['bak_prompt'] = self.old_prompt
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

    def test_details_report_removed_count(self):
        db = os.path.join(self.tmp, 'jellyfin.db')
        with open(db, 'wb') as f:
            f.write(b'db')
        current = os.path.join(self.tmp, 'jellyfin.db-2999-01-01_00-00-00.bak')
        old = os.path.join(self.tmp, 'jellyfin.db-1999-01-01_00-00-00.bak')
        for p in (current, old):
            with open(p, 'wb') as f:
                f.write(b'bak')
        now = time.time()
        os.utime(current, (now + 30, now + 30))
        os.utime(old, (now, now))
        j.STATE['session_bak'] = current
        j.SETTINGS['bak_keep'] = 1
        result = j.prune_bak_files(db, details=True)
        self.assertEqual(result, {'removed': 1, 'failed': 0})
        self.assertTrue(os.path.exists(current))
        self.assertFalse(os.path.exists(old))

    def test_bak_files_only_program_copies(self):
        db = os.path.join(self.tmp, 'jellyfin.db')
        with open(db, 'wb') as f:
            f.write(b'db')
        names = ('jellyfin.db-2020-01-01_00-00-00.bak', 'manual.bak', 'other.db-2020-01-01_00-00-00.bak',
                 'jellyfin.db-2020-01-01_00-00-00.bak.jfb-tmp')
        for n in names:
            with open(os.path.join(self.tmp, n), 'wb') as f:
                f.write(b'bak')
        found = [os.path.basename(p) for _, p in j.bak_files(db)]
        self.assertEqual(found, ['jellyfin.db-2020-01-01_00-00-00.bak'])

    def test_prompt_only_above_twice_the_limit(self):
        db = os.path.join(self.tmp, 'jellyfin.db')
        with open(db, 'wb') as f:
            f.write(b'db')
        for i in range(3):
            with open(os.path.join(self.tmp, f'jellyfin.db-2020-01-0{i + 1}_00-00-00.bak'), 'wb') as f:
                f.write(b'bak')
        j.SETTINGS['bak_keep'] = 2
        self.assertIsNone(j.bak_prompt_state(db))
        with open(os.path.join(self.tmp, 'jellyfin.db-2020-01-04_00-00-00.bak'), 'wb') as f:
            f.write(b'bak')
        prompt = j.bak_prompt_state(db)
        self.assertEqual(prompt['count'], 4)
        self.assertEqual(prompt['limit'], 2)
        j.SETTINGS['bak_keep'] = 1
        self.assertEqual(j.bak_prompt_state(db)['count'], 4)
        j.SETTINGS['bak_keep'] = 0
        self.assertIsNone(j.bak_prompt_state(db))

    def test_details_flag_need_admin(self):
        db = os.path.join(self.tmp, 'jellyfin.db')
        with open(db, 'wb') as f:
            f.write(b'db')
        for i in range(2):
            with open(os.path.join(self.tmp, f'jellyfin.db-2020-01-0{i + 1}_00-00-00.bak'), 'wb') as f:
                f.write(b'bak')
        j.STATE['session_bak'] = None
        j.SETTINGS['bak_keep'] = 1
        with mock.patch.object(j, 'remove_file', side_effect=j.NeedAdmin('x')):
            result = j.prune_bak_files(db, details=True)
        self.assertEqual(result['removed'], 0)
        self.assertEqual(result['failed'], 1)
        self.assertTrue(result['need_admin'])

    def test_api_bak_cleanup_asks_for_admin(self):
        j.STATE['bak_prompt'] = {'count': 21, 'limit': 10}
        with mock.patch.object(j, 'IS_ROOT', False), \
                mock.patch.object(j, 'priv_alive', return_value=False), \
                mock.patch.object(j, 'prune_bak_files',
                                  return_value={'removed': 0, 'failed': 1, 'need_admin': True}):
            with self.assertRaises(j.NeedAdmin):
                j.api_bak({'action': 'cleanup'})
        self.assertEqual(j.api_bak({'action': 'dismiss'}), {'ok': True})
        self.assertIsNone(j.STATE.get('bak_prompt'))


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='jfcmpunit_')
        self.old_tmp_dir = j.TMP_DIR
        j.TMP_DIR = os.path.join(self.tmp, 'work')
        os.makedirs(j.TMP_DIR)

    def tearDown(self):
        j.TMP_DIR = self.old_tmp_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    @staticmethod
    def row(rid, name, data=None, saved='2026-01-01'):
        return (rid, name, 'MediaBrowser.Controller.Entities.Movies.Movie',
                f'/media/{rid}.mkv', None, 2020, data, saved)

    def make_db(self, folder, rows, users=('u1', 'u2'), device=None):
        base = os.path.join(self.tmp, folder)
        os.makedirs(base)
        path = os.path.join(base, 'jellyfin.db')
        con = sqlite3.connect(path)
        try:
            con.execute('CREATE TABLE BaseItems (Id TEXT PRIMARY KEY, Name TEXT, Type TEXT, Path TEXT, '
                        'ParentId TEXT, ProductionYear INTEGER, Data TEXT, DateLastSaved TEXT)')
            con.execute('CREATE TABLE Users (Id TEXT PRIMARY KEY, Username TEXT)')
            con.executemany('INSERT INTO BaseItems VALUES (?,?,?,?,?,?,?,?)', rows)
            con.executemany('INSERT INTO Users VALUES (?,?)', [(u, u) for u in users])
            con.commit()
        finally:
            con.close()
        if device:
            with open(os.path.join(base, 'device.txt'), 'w', encoding='utf-8') as f:
                f.write(device)
        return path

    def test_added_removed_changed_and_json(self):
        a = self.make_db('a', [
            self.row('id1', 'Movie A', '{"b":2,"a":1}'),
            self.row('id2', 'Movie B'),
            self.row('id3', 'Movie C'),
        ])
        b = self.make_db('b', [
            self.row('id1', 'Movie A edited', '{"a":1, "b":2}'),
            self.row('id2', 'Movie B', ''),
            self.row('id4', 'Movie D'),
        ])
        res = j.compare_databases(a, b, a_origin=a)
        self.assertEqual(res['counts']['added'], 1)
        self.assertEqual(res['counts']['removed'], 1)
        self.assertEqual(res['counts']['changed'], 2)
        self.assertEqual([x['id'] for x in res['added']], ['id4'])
        self.assertEqual([x['id'] for x in res['removed']], ['id3'])
        changed = {x['id']: x for x in res['changed']}
        self.assertEqual([f['name'] for f in changed['id1']['fields']], ['Name'])
        self.assertEqual([f['name'] for f in changed['id2']['fields']], ['Data'])
        data_field = changed['id2']['fields'][0]
        self.assertTrue(data_field['a_null'])
        self.assertFalse(data_field['b_null'])
        self.assertEqual(data_field['b'], '')
        self.assertEqual(res['instance']['verdict'], 'same')
        self.assertFalse(res['schema']['mismatch'])

    def test_technical_columns_are_optional(self):
        a = self.make_db('a', [self.row('id1', 'Movie A', saved='old')])
        b = self.make_db('b', [self.row('id1', 'Movie A', saved='new')])
        res = j.compare_databases(a, b, a_origin=a)
        self.assertEqual(res['counts']['changed'], 0)
        res = j.compare_databases(a, b, a_origin=a, include_technical=True)
        self.assertEqual(res['counts']['changed'], 1)
        self.assertEqual(res['changed'][0]['fields'][0]['name'], 'DateLastSaved')

    def test_device_txt_detects_different_instance(self):
        a = self.make_db('a', [self.row('id1', 'Movie A')], device='a' * 32)
        b = self.make_db('b', [self.row('id1', 'Movie A')], device='b' * 32)
        inst = j.compare_databases(a, b, a_origin=a)['instance']
        self.assertEqual(inst['verdict'], 'different')
        self.assertEqual(inst['reason'], 'device')

    def test_no_common_ids_is_different_instance(self):
        a = self.make_db('a', [self.row('id1', 'Movie A'), self.row('id2', 'Movie B')])
        b = self.make_db('b', [self.row('id8', 'Movie X'), self.row('id9', 'Movie Y')])
        inst = j.compare_databases(a, b, a_origin=a)['instance']
        self.assertEqual(inst['verdict'], 'different')
        self.assertEqual(inst['reason'], 'ids')

    def test_missing_baseitems_is_rejected(self):
        base = os.path.join(self.tmp, 'empty')
        os.makedirs(base)
        path = os.path.join(base, 'jellyfin.db')
        con = sqlite3.connect(path)
        con.execute('CREATE TABLE Other (Id TEXT)')
        con.commit()
        con.close()
        with self.assertRaises(ValueError):
            j.compare_databases(path, path, a_origin=path)


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


class DataDirChangeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='jfdata_')
        self.old = os.path.join(self.tmp, 'old')
        self.new = os.path.join(self.tmp, 'new')
        os.makedirs(os.path.join(self.old, 'history', '20260101-000000'))
        os.makedirs(os.path.join(self.old, 'backups'))
        with open(os.path.join(self.old, 'history', 'index.json'), 'w', encoding='utf-8') as f:
            f.write('[]')
        with open(os.path.join(self.old, 'history', '20260101-000000', 'jellyfin.db'), 'wb') as f:
            f.write(b'db')
        with open(os.path.join(self.old, 'backups', 'index.json'), 'w', encoding='utf-8') as f:
            f.write('[]')
        with open(os.path.join(self.old, 'backups', 'manual.db'), 'wb') as f:
            f.write(b'bak')
        self.old_data = j.DATA_DIR
        self.old_setting = j.SETTINGS.get('data_dir')
        self.old_save = j.save_settings
        self.old_state = {k: j.STATE.get(k) for k in
                          ('con', 'tmp', 'src', 'kind', 'dirty', 'setup', 'job', 'loading')}
        j.save_settings = lambda: True
        j.configure_data_dir(self.old)
        j.SETTINGS['data_dir'] = self.old
        j.STATE.update(con=None, tmp=None, src='', kind='path', dirty=0, setup=False)

    def tearDown(self):
        j.configure_data_dir(self.old_data)
        j.SETTINGS['data_dir'] = self.old_setting
        j.save_settings = self.old_save
        for k, v in self.old_state.items():
            j.STATE[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_moves_history_and_backups(self):
        result = j.change_data_dir(self.new, force=True)
        self.assertEqual(result['data_dir'], os.path.abspath(self.new))
        self.assertEqual(result['moved'], {'history': 2, 'backups': 2})
        self.assertFalse(result['reloaded'])
        self.assertTrue(os.path.isfile(os.path.join(self.new, 'history', 'index.json')))
        self.assertTrue(os.path.isfile(os.path.join(
            self.new, 'history', '20260101-000000', 'jellyfin.db')))
        self.assertTrue(os.path.isfile(os.path.join(self.new, 'backups', 'index.json')))
        self.assertTrue(os.path.isfile(os.path.join(self.new, 'backups', 'manual.db')))
        self.assertFalse(os.path.exists(os.path.join(self.old, 'history')))
        self.assertFalse(os.path.exists(os.path.join(self.old, 'backups')))
        self.assertEqual(j.SETTINGS['data_dir'], os.path.abspath(self.new))

    def test_refuses_non_empty_target(self):
        os.makedirs(os.path.join(self.new, 'history'))
        with open(os.path.join(self.new, 'history', 'keep.db'), 'wb') as f:
            f.write(b'x')
        with self.assertRaises(ValueError):
            j.change_data_dir(self.new, force=True)
        self.assertTrue(os.path.isfile(os.path.join(self.old, 'history', 'index.json')))
        self.assertEqual(j.SETTINGS['data_dir'], self.old)

    def test_refuses_nested_target(self):
        with self.assertRaises(ValueError):
            j.change_data_dir(os.path.join(self.old, 'nested'), force=True)

    def test_refuses_upload_database(self):
        j.STATE.update(kind='upload', con=object())
        with self.assertRaises(ValueError):
            j.change_data_dir(self.new, force=True)

    def test_requires_force_when_dirty(self):
        j.STATE['dirty'] = 2
        with self.assertRaises(ValueError):
            j.change_data_dir(self.new)
        self.assertEqual(j.SETTINGS['data_dir'], self.old)


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
