import importlib.util
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
