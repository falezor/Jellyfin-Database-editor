#!/usr/bin/env python3
"""
jf_browser.py - przeglądarka i czyszczarka jellyfin.db (tylko filmy i seriale).

Uruchomienie (Upload wymaga sudo i zatrzymanego Jellyfina):
    sudo systemctl stop jellyfin
    sudo python3 jf_browser.py
    # przeglądarka otworzy się sama: http://127.0.0.1:8099

Jak to działa (oryginał jest bezpieczny):
  * program kopiuje oryginalną bazę do katalogu tymczasowego i pracuje WYŁĄCZNIE na kopii roboczej,
  * "Usuń zaznaczone" kasuje wpisy tylko w kopii roboczej,
  * "Odśwież z oryginału" odrzuca zmiany i pobiera świeżą, niezmodyfikowaną bazę,
  * "Upload" podmienia bazę Jellyfina na kopię roboczą; opcjonalnie (fistaszek) robi najpierw
    kopię zapasową oryginału obok niego: jellyfin.db-2026-11-12_22-45-10.bak
Pliki mediów nigdy nie są ruszane.

Platformy:
  * Linux: pełne wsparcie (sudo, systemd/Docker, /proc, fstab, lsblk).
  * Windows: bez sudo/ADMIN — program działa na uprawnieniach użytkownika; systemctl/lsblk
    nie są używane, dyski są sprawdzane tylko przez istnienie ścieżek, ścieżki mają format C:\\...;
    wybór pliku działa przez tkinter, a UAC jest wykrywany przez IsUserAnAdmin().
  * macOS: nieprzetestowany — brak /proc (tylko brak folderu), sudo działa jak na Linuksie,
    sterowanie usługą systemd jest niedostępne.
"""
import argparse
import http.client
import ipaddress
import json
import gzip
import hashlib
import mimetypes
import os
import queue
import re
import secrets
import shutil
import signal
import socket
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlparse

IMG_TYPES = {0: 'Primary', 1: 'Art', 2: 'Backdrop', 3: 'Banner', 4: 'Logo', 5: 'Thumb',
             6: 'Disc', 7: 'Box', 8: 'Screenshot', 9: 'Menu', 10: 'Chapter',
             11: 'BoxRear', 12: 'Profile'}

LIB_TYPE = "Type LIKE '%.CollectionFolder'"   # biblioteka = wiersz CollectionFolder

STAT_CACHE = {}      # ścieżka -> (czas sprawdzenia, istnieje True/False/None)
STAT_TTL = 8.0
STATE = {'con': None, 'tmp': None, 'src': None, 'orig': None, 'work': None,
         'dirty': 0, 'sig': None, 'problems': None, 'pmap': None, 'libs': None, 'roots': [],
         'kind': 'path', 'label': None, 'nodb_reason': None, 'unreadable': 0, 'deleted': [], 'loading': False,
         'setup': False, 'sqljob': None, 'job': None, 'dialog': True,
         'nodb_reason_key': None, 'nodb_reason_args': {}}
CFG = {'service_check': True, 'token': secrets.token_hex(16)}


def app_dir():
    """Katalog, w którym fizycznie leży program (skrypt, .exe lub AppImage)."""
    ai = os.environ.get('APPIMAGE')
    if ai:
        return os.path.dirname(os.path.abspath(ai))
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


DATA_DIR = app_dir()
TMP_DIR = os.path.join(DATA_DIR, 'tmp')
HISTORY_DIR = os.path.join(DATA_DIR, 'history')
HISTORY_INDEX = os.path.join(HISTORY_DIR, 'index.json')


def dialog_available():
    try:
        import tkinter  # noqa: F401
    except Exception:
        return False
    if os.name == 'posix' and sys.platform != 'darwin':
        if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
            return False
    return True


def dir_writable(path):
    try:
        test = os.path.join(path, '.jfb-write-test')
        with open(test, 'w', encoding='utf-8') as f:
            f.write('ok')
        os.remove(test)
        return True
    except OSError:
        return False


def valid_data_dir(path):
    p = os.path.abspath(os.path.expanduser((path or '').strip()))
    if not p:
        raise ValueError(tr('e_dir_missing'))
    if os.path.dirname(p) == p:
        raise ValueError(tr('e_dir_root'))
    home = os.path.abspath(os.path.expanduser('~'))
    if os.path.normcase(p) == os.path.normcase(home):
        raise ValueError(tr('e_dir_home'))
    if not os.path.exists(p):
        try:
            os.makedirs(p, exist_ok=True)
        except OSError:
            raise ValueError(tr('e_dir_missing'))
    if not os.path.isdir(p):
        raise ValueError(tr('e_dir_missing'))
    try:
        os.makedirs(os.path.join(p, 'tmp', 'history'), exist_ok=True)
    except OSError:
        raise ValueError(tr('e_dir_write'))
    if not dir_writable(p):
        raise ValueError(tr('e_dir_write'))
    return p


def suggested_dir():
    cand = app_dir()
    if os.path.isdir(cand) and dir_writable(cand):
        return cand
    return os.path.join(os.path.expanduser('~'), 'JellyfinDBeditor')


def init_data_dir():
    """Folder danych: zapisany w ustawieniach; bez niego program prosi o konfigurację (instalator)."""
    p = SETTINGS.get('data_dir')
    if p:
        try:
            chosen = valid_data_dir(p)
        except ValueError:
            chosen = None
        if chosen:
            configure_data_dir(chosen)
            migrate_history()
            try:
                os.makedirs(HISTORY_DIR, exist_ok=True)
            except OSError:
                pass
            STATE['setup'] = False
            return chosen
    STATE['setup'] = True
    return None


def configure_data_dir(path):
    global DATA_DIR, TMP_DIR, HISTORY_DIR, HISTORY_INDEX
    DATA_DIR = os.path.abspath(path)
    TMP_DIR = os.path.join(DATA_DIR, 'tmp')
    HISTORY_DIR = os.path.join(DATA_DIR, 'history')
    HISTORY_INDEX = os.path.join(HISTORY_DIR, 'index.json')


def migrate_history():
    """Przenosi starą historię z tmp/history do history/ (nowe miejsce)."""
    old = os.path.join(TMP_DIR, 'history')
    if not os.path.isdir(old):
        return
    try:
        os.makedirs(HISTORY_DIR, exist_ok=True)
        for name in os.listdir(old):
            src = os.path.join(old, name)
            dst = os.path.join(HISTORY_DIR, name)
            if not os.path.exists(dst):
                shutil.move(src, dst)
        os.rmdir(old)
    except OSError:
        pass


def work_tmp():
    os.makedirs(TMP_DIR, exist_ok=True)
    return TMP_DIR


def cleanup_stale_sessions(max_age=24 * 3600):
    """Usuwa stare kopie sesji/uploadów z tmp (po SIGKILL/awarii); aktywne sesje mają świeży mtime."""
    now = time.time()
    removed = 0
    try:
        entries = list(os.scandir(TMP_DIR))
    except OSError:
        return 0
    for e in entries:
        if not e.name.startswith(('jfdb_', 'jfup_', 'jfexp_', 'import_')):
            continue
        try:
            if now - e.stat().st_mtime < max_age:
                continue
            if e.is_dir():
                shutil.rmtree(e.path, ignore_errors=True)
            else:
                os.remove(e.path)
            removed += 1
        except OSError:
            pass
    return removed


LOCK = threading.Lock()
NODB_OK = ('/', '/api/info', '/api/priv', '/api/jellyfin', '/api/service', '/api/open', '/api/load', '/api/reload',
           '/api/pick', '/api/history', '/api/settings', '/api/setup', '/api/pickdir', '/api/import-sql', '/api/sqljob',
           '/api/job', '/api/backups', '/api/pickpath')

from i18n import LANGS, LANG_NAMES, TEXT, tr, status_short, status_long, reason_text, set_lang


# ---------- wykrywanie działającego Jellyfina (GET /System/Info/Public) ----------

SETTINGS = {}                 # trwałe ustawienia (np. jf_port), plik JSON w katalogu konfiguracji użytkownika
JF = {'state': 'unknown', 'port': 8096, 'source': 'domyślny', 'info': None, 'detail': ''}


def _sudo_user_home():
    user = os.environ.get('SUDO_USER')
    if user and getattr(os, 'geteuid', lambda: 1)() == 0:
        try:
            import pwd
            pw = pwd.getpwnam(user)
            return pw.pw_dir, pw.pw_uid, pw.pw_gid
        except (KeyError, ImportError):
            pass
    return None


def config_path():
    p = os.environ.get('JF_BROWSER_CONFIG')
    if p:
        return p
    cached = CFG.get('config')
    if cached:
        return cached
    local = os.path.join(app_dir(), 'jf_browser.settings.json')
    if os.path.isdir(app_dir()) and dir_writable(app_dir()):
        CFG['config'] = local
        return local
    su = _sudo_user_home()
    base = os.path.join(su[0], '.config') if su else (
        os.environ.get('XDG_CONFIG_HOME') or os.path.join(os.path.expanduser('~'), '.config'))
    CFG['config'] = os.path.join(base, 'jf_browser', 'settings.json')
    return CFG['config']


def load_settings():
    try:
        with open(config_path(), encoding='utf-8') as f:
            d = json.load(f)
        if isinstance(d, dict):
            SETTINGS.update(d)
    except (OSError, ValueError):
        pass


def save_settings():
    """Zwraca True, jeśli zapisano na dysku."""
    path = config_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(SETTINGS, f, indent=1)
        su = _sudo_user_home()
        if su:  # pod sudo plik ma należeć do zwykłego użytkownika, nie do roota
            for p in (os.path.dirname(path), path):
                try:
                    os.chown(p, su[1], su[2])
                except OSError:
                    pass
        return True
    except OSError:
        return False


def read_network_xml():
    """Port i BaseUrl z network.xml Jellyfina (działa też, gdy serwer jest wyłączony)."""
    cands = []
    src = STATE.get('src')
    if src and STATE.get('kind') == 'path':
        cands.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(src))), 'config', 'network.xml'))
    cands += ['/etc/jellyfin/network.xml', '/var/lib/jellyfin/config/network.xml']
    for pth in cands:
        try:
            root = ET.parse(pth).getroot()
            port = int(root.findtext('InternalHttpPort'))
        except (OSError, ET.ParseError, TypeError, ValueError):
            continue
        base = (root.findtext('BaseUrl') or '').strip().rstrip('/')
        if base and not base.startswith('/'):
            base = '/' + base
        return port, base, pth
    return None


def jf_probe(port, base='', timeout=1.0, host='127.0.0.1'):
    """('jellyfin', info) | ('refused', None) | ('timeout', None) | ('other', opis)."""
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request('GET', base + '/System/Info/Public', headers={'Accept': 'application/json'})
        r = conn.getresponse()
        body = r.read(65536)
    except ConnectionRefusedError:
        return 'refused', None
    except (socket.timeout, TimeoutError):
        return 'timeout', None
    except (OSError, http.client.HTTPException):
        return 'other', 'brak poprawnej odpowiedzi HTTP'
    finally:
        conn.close()
    try:
        d = json.loads(body.decode('utf-8', 'replace'))
    except ValueError:
        d = None
    if r.status == 200 and isinstance(d, dict) and d.get('Version') and (d.get('ProductName') or d.get('ServerName')):
        return 'jellyfin', {k: d.get(k) for k in ('Version', 'ServerName', 'ProductName', 'Id', 'LocalAddress')}
    return 'other', f'HTTP {r.status}'


def jf_detect(only_port=None):
    """Kolejność: port wpisany > zapisany w ustawieniach > network.xml > 8096."""
    nx = read_network_xml()
    xml_base = nx[1] if nx else ''
    cands = []
    if only_port:
        cands.append((only_port, tr('src_manual')))
    elif SETTINGS.get('jf_port'):
        cands.append((int(SETTINGS['jf_port']), tr('src_saved')))
    else:
        if nx:
            cands.append((nx[0], 'network.xml'))
        cands.append((8096, tr('src_default')))
    seen, wrong = set(), None
    for port, source in cands:
        if port in seen:
            continue
        seen.add(port)
        st, data = jf_probe(port, xml_base)
        if st == 'jellyfin':
            return {'state': 'running', 'port': port, 'source': source, 'info': data, 'detail': ''}
        if st == 'other' and wrong is None:
            wrong = (port, source, data)
    if wrong:
        return {'state': 'wrong', 'port': wrong[0], 'source': wrong[1], 'info': None, 'detail': wrong[2]}
    port, source = cands[0]
    return {'state': 'off', 'port': port, 'source': source, 'info': None, 'detail': ''}


def listening_ports():
    ports = set()
    for f in ('/proc/net/tcp', '/proc/net/tcp6'):
        try:
            with open(f, encoding='utf-8') as fh:
                next(fh, None)
                for line in fh:
                    p = line.split()
                    if len(p) > 3 and p[3] == '0A':  # LISTEN
                        ports.add(int(p[1].rsplit(':', 1)[1], 16))
        except (OSError, ValueError):
            pass
    return sorted(ports)


def jf_scan():
    """Szuka Jellyfina wśród lokalnie nasłuchujących portów (GET tylko na 127.0.0.1), równolegle."""
    nx = read_network_xml()
    base = nx[1] if nx else ''
    ports = [p for p in listening_ports()[:300] if p != CFG.get('own_port')]
    if not ports:
        return None
    with ThreadPoolExecutor(max_workers=min(32, len(ports))) as ex:
        futs = {ex.submit(jf_probe, p, base, 0.5): p for p in ports}
        for f in as_completed(futs):
            try:
                st, data = f.result()
            except Exception:
                continue
            if st == 'jellyfin':
                return futs[f], data
    return None


def api_jellyfin(body):
    action = (body or {}).get('action')
    if action == 'scan':
        r = jf_scan()
        return {'found': r[0] if r else None, 'info': r[1] if r else None}
    try:
        port = int(body.get('port'))
    except (TypeError, ValueError):
        raise ValueError(tr('e_port_range'))
    if not 1 <= port <= 65535:
        raise ValueError(tr('e_port_range'))
    if action == 'test':
        return jf_detect(port)
    if action == 'save':
        SETTINGS['jf_port'] = port
        persisted = save_settings()
        res = jf_detect(port)
        JF.update(res)
        return dict(res, persisted=persisted)
    raise ValueError(tr('e_unknown_action'))


# ---------- uprawnienia: LIMITED / ADMIN (sudo) ----------

class NeedAdmin(RuntimeError):
    """Operacja wymaga uprawnień administratora (tryb ADMIN)."""


IS_ROOT = getattr(os, 'geteuid', lambda: 1)() == 0 and not os.environ.get('JF_FORCE_LIMITED')


def windows_admin():
    """Czy proces na Windows działa z podniesionymi uprawnieniami (UAC)."""
    if os.name != 'nt':
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


IS_WIN_ADMIN = windows_admin() and not os.environ.get('JF_FORCE_LIMITED')
SUDO = os.environ.get('JF_SUDO_CMD') or 'sudo'
IDLE_LIMIT = 15 * 60   # po tylu sekundach bezczynności sesja ADMIN wygasa
PRIV = {'proc': None, 'q': None, 'last': 0.0, 'seq': 0, 'nopw': None, 'nopw_t': 0.0}
PRIV_LOCK = threading.RLock()

# Kod współdzielony: używany lokalnie i w procesie pomocniczym uruchamianym przez sudo.
_SHARED_SRC = r"""
def stat1(p):
    # e: True / False / None (brak dostępu), d: katalog, n: katalog niepusty
    try:
        st = os.stat(p)
    except (FileNotFoundError, NotADirectoryError):
        return {'e': False}
    except OSError:
        return {'e': None}
    r = {'e': True, 'd': stat.S_ISDIR(st.st_mode), 's': st.st_size, 'm': st.st_mtime_ns,
         'mode': st.st_mode & 0o7777, 'u': st.st_uid, 'g': st.st_gid}
    if r['d']:
        try:
            r['n'] = any(True for _ in os.scandir(p))
        except OSError:
            r['n'] = None
    return r


def svc_cmd(kind, name, act):
    if act not in ('start', 'stop', 'restart', 'is-active', 'list') or not re.fullmatch(r'[A-Za-z0-9_.@-]*', name or ''):
        return None
    if kind == 'systemd' and act != 'list' and name:
        return ['systemctl', act, name]
    if kind == 'docker':
        if act == 'list':
            return ['docker', 'ps', '-a', '--format', '{{.Names}}\t{{.Image}}']
        if name and act == 'is-active':
            return ['docker', 'inspect', '-f', '{{.State.Running}}', name]
        if name:
            return ['docker', act, name]
    return None
"""
exec(_SHARED_SRC)

# Proces pomocniczy działający jako root (przez sudo). Wykonuje tylko stały zestaw operacji:
# stat, odczyt pliku do katalogu tymczasowego, atomowy zapis, usunięcie, start/stop usługi.
HELPER_CODE = 'import sys, os, stat, json, shutil, subprocess, re\n' + _SHARED_SRC + r"""
uid, gid = int(sys.argv[1]), int(sys.argv[2])


def handle(q):
    op = q.get('op')
    if op == 'ping':
        return {'ok': True}
    if op == 'stat':
        return {'ok': True, 'r': [stat1(p) for p in q['paths']]}
    if op == 'read':
        shutil.copyfile(q['src'], q['dst'])
        os.chown(q['dst'], uid, gid)
        os.chmod(q['dst'], 0o600)
        return {'ok': True}
    if op == 'install':
        dst = q['dst']
        tmp = dst + '.jfb-tmp'
        shutil.copyfile(q['src'], tmp)
        os.chmod(tmp, q['mode'])
        os.chown(tmp, q['uid'], q['gid'])
        fd = os.open(tmp, os.O_RDONLY)
        os.fsync(fd)
        os.close(fd)
        os.replace(tmp, dst)
        return {'ok': True}
    if op == 'remove':
        try:
            os.remove(q['path'])
        except FileNotFoundError:
            pass
        return {'ok': True}
    if op == 'svc':
        cmd = svc_cmd(q.get('kind'), q.get('name'), q.get('action'))
        if not cmd:
            return {'ok': False, 'err': 'niedozwolone polecenie'}
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        lim = 4000 if q.get('action') == 'list' else 400
        return {'ok': r.returncode == 0, 'rc': r.returncode, 'out': (r.stdout + r.stderr).strip()[-lim:]}
    return {'ok': False, 'err': 'nieznana operacja'}


print(json.dumps({'hello': 1}), flush=True)
for line in sys.stdin:
    try:
        q = json.loads(line)
    except ValueError:
        continue
    if not isinstance(q, dict):
        continue
    if q.get('op') == 'quit':
        break
    try:
        r = handle(q)
    except Exception as e:
        r = {'ok': False, 'err': repr(e)}
    r['id'] = q.get('id')
    print(json.dumps(r), flush=True)
"""


def sudo_available():
    if os.name == 'nt':
        return False
    return bool(shutil.which(SUDO))


def priv_alive():
    p = PRIV['proc']
    return bool(p) and p.poll() is None


def priv_mode():
    if IS_ROOT:
        return 'root'
    return 'admin' if priv_alive() else 'limited'


def _invalidate_fs_caches():
    STAT_CACHE.clear()
    STATE.update(libs=None, problems=None, pmap=None)


def _reader(p, qq):
    try:
        for line in p.stdout:
            try:
                qq.put(json.loads(line))
            except ValueError:
                pass
    finally:
        qq.put(None)


def priv_disable():
    with PRIV_LOCK:
        p, PRIV['proc'] = PRIV['proc'], None
        if p is not None and p.poll() is None:
            try:
                p.stdin.write(b'{"op": "quit"}\n')
                p.stdin.flush()
                p.stdin.close()
            except OSError:
                pass
            try:
                p.wait(3)
            except subprocess.TimeoutExpired:
                p.kill()
    _invalidate_fs_caches()


def priv_nopasswd():
    now = time.time()
    if PRIV['nopw'] is None or now - PRIV['nopw_t'] > 60:
        try:
            PRIV['nopw'] = subprocess.run([SUDO, '-n', 'true'], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL, timeout=5).returncode == 0
        except (OSError, subprocess.SubprocessError):
            PRIV['nopw'] = False
        PRIV['nopw_t'] = now
    return PRIV['nopw']


def priv_enable(password):
    """Włącza tryb ADMIN: hasło idzie wyłącznie na stdin polecenia sudo, nie jest nigdzie zapisywane."""
    if os.name == 'nt':
        raise RuntimeError(tr('e_admin_windows'))
    if IS_ROOT or priv_alive():
        return
    if not sudo_available():
        raise RuntimeError(tr('e_sudo_missing'))
    nopw = priv_nopasswd()
    wrong = tr('e_bad_sudo')
    if not nopw:
        try:
            v = subprocess.run([SUDO, '-S', '-p', '', '-v'], input=(password or '').encode('utf-8') + b'\n',
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        except (OSError, subprocess.SubprocessError):
            raise RuntimeError(wrong)
        if v.returncode != 0:
            raise RuntimeError(wrong)
    py = shutil.which('python3') or sys.executable
    cmd = [SUDO] + (['-n'] if nopw else ['-S', '-p', '']) + [py, '-u', '-c', HELPER_CODE,
                                                              str(os.getuid()), str(os.getgid())]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        if not nopw:
            p.stdin.write((password or '').encode('utf-8') + b'\n')
            p.stdin.flush()
    except OSError:
        pass
    qq = queue.Queue()
    threading.Thread(target=_reader, args=(p, qq), daemon=True).start()
    threading.Thread(target=lambda: [None for _ in p.stderr], daemon=True).start()
    try:
        hello = qq.get(timeout=12)
    except queue.Empty:
        hello = None
    if not hello or not hello.get('hello'):
        try:
            p.kill()
        except OSError:
            pass
        raise RuntimeError(wrong)
    PRIV.update(proc=p, q=qq, last=time.time())
    _invalidate_fs_caches()


def priv_call(req, timeout=120):
    if not priv_alive():
        raise NeedAdmin(tr('e_need_admin'))
    with PRIV_LOCK:
        PRIV['seq'] += 1
        req = dict(req, id=PRIV['seq'])
        try:
            PRIV['proc'].stdin.write((json.dumps(req) + '\n').encode('utf-8'))
            PRIV['proc'].stdin.flush()
        except OSError:
            priv_disable()
            raise NeedAdmin(tr('e_admin_expired'))
        while True:
            try:
                r = PRIV['q'].get(timeout=timeout)
            except queue.Empty:
                raise RuntimeError(tr('e_admin_noanswer'))
            if r is None:
                priv_disable()
                raise NeedAdmin(tr('e_admin_closed'))
            if r.get('id') == req['id']:
                PRIV['last'] = time.time()
                return r


def priv_idle_check():
    if priv_alive() and time.time() - PRIV['last'] > IDLE_LIMIT:
        priv_disable()
        return True
    return False


def _watchdog():
    while True:
        time.sleep(30)
        priv_idle_check()


def platform_name():
    return 'windows' if os.name == 'nt' else ('macos' if sys.platform == 'darwin' else 'linux')


def priv_label(platform, mode):
    """Etykieta aktywnego trybu uprawnień: root / admin / sudo / user."""
    if os.environ.get('JF_FORCE_LIMITED'):
        return 'user'
    if platform == 'windows':
        return 'admin' if IS_WIN_ADMIN else 'user'
    if platform == 'macos':
        if IS_ROOT:
            return 'root'
        if mode == 'admin':
            return 'sudo'
        try:
            return 'admin' if 80 in os.getgroups() else 'user'
        except Exception:
            return 'user'
    if IS_ROOT or mode == 'root':
        return 'root'
    if mode == 'admin':
        return 'sudo'
    return 'user'


def priv_state():
    platform = platform_name()
    mode = 'limited' if platform == 'windows' else priv_mode()
    src = STATE.get('src')
    can_write = None
    if STATE.get('kind') == 'path' and src:
        can_write = bool(IS_ROOT or (os.access(src, os.W_OK) and os.access(os.path.dirname(os.path.abspath(src)), os.W_OK)))
    return {'mode': mode, 'platform': platform, 'label': priv_label(platform, mode),
            'sudo': False if platform == 'windows' else sudo_available(),
            'nopasswd': False if platform == 'windows' or mode != 'limited' else (priv_nopasswd() if sudo_available() else False),
            'can_write_db': can_write,
            'idle_left': max(0, int(IDLE_LIMIT - (time.time() - PRIV['last']))) if mode == 'admin' else None,
            'unreadable': STATE.get('unreadable', 0)}


def api_priv(body):
    action = (body or {}).get('action')
    if action == 'enable':
        priv_enable(str(body.get('password') or ''))
    elif action == 'disable':
        priv_disable()
    else:
        raise ValueError(tr('e_unknown_action'))
    return priv_state()


# ---------- dostęp do plików: bezpośrednio albo przez proces ADMIN ----------

def fs_stat_many(paths):
    paths = list(paths)
    if priv_alive() and not IS_ROOT:
        try:
            out = []
            for i in range(0, len(paths), 400):
                out += priv_call({'op': 'stat', 'paths': paths[i:i + 400]})['r']
            return out
        except NeedAdmin:
            pass
    return [stat1(p) for p in paths]


def exists_map(paths):
    """ścieżka -> True / False / None (None = brak uprawnień, nie wiadomo); krótki cache TTL."""
    uniq = list(dict.fromkeys(paths))
    now = time.time()
    out, todo = {}, []
    for p in uniq:
        hit = STAT_CACHE.get(p)
        if hit and now - hit[0] <= STAT_TTL:
            out[p] = hit[1]
        else:
            todo.append(p)
    if todo:
        if len(STAT_CACHE) > 50000:
            STAT_CACHE.clear()
        for p, i in zip(todo, fs_stat_many(todo)):
            out[p] = i['e']
            STAT_CACHE[p] = (now, i['e'])
    return out


def annotate_exists(rows):
    ex = exists_map([r['Path'] for r in rows if r.get('Path')])
    for r in rows:
        has = bool(r.get('Path'))
        e = ex.get(r['Path']) if has else None
        r['exists'] = has and e is not False
        r['unk'] = has and e is None


def file_sig(path):
    out = []
    for suf, r in zip(('', '-wal'), fs_stat_many([path, path + '-wal'])):
        if r['e']:
            out.append((suf, r['s'], r['m']))
        elif r['e'] is False:
            out.append((suf, None, None))
        else:
            out.append((suf, '?', None))
    return out


def copy_from_protected(src, dst):
    """Kopiuje plik do dst; przy braku uprawnień używa procesu ADMIN."""
    try:
        shutil.copy2(src, dst)
        return
    except PermissionError:
        if IS_ROOT:
            raise
        if not priv_alive():
            raise NeedAdmin(tr('e_no_access', src=src))
    r = priv_call({'op': 'read', 'src': src, 'dst': dst})
    if not r.get('ok'):
        raise RuntimeError(r.get('err') or tr('e_read_failed'))


def install_file(tmp_src, dst, st):
    """Atomowy zapis do (być może chronionego) miejsca; właściciel i uprawnienia jak w oryginale."""
    folder = os.path.dirname(os.path.abspath(dst))
    if os.access(folder, os.W_OK):
        tmp = dst + '.jfb-tmp'
        shutil.copyfile(tmp_src, tmp)
        try:
            os.chmod(tmp, st['mode'])
        except OSError:
            pass
        try:
            os.chown(tmp, st['u'], st['g'])
        except (OSError, AttributeError):
            pass
        try:
            os.replace(tmp, dst)
            return
        except OSError:
            try:
                os.remove(tmp)
            except OSError:
                pass
    if not priv_alive():
        raise NeedAdmin(tr('e_write_admin'))
    r = priv_call({'op': 'install', 'src': tmp_src, 'dst': dst, 'mode': st['mode'], 'uid': st['u'], 'gid': st['g']})
    if not r.get('ok'):
        raise RuntimeError(r.get('err') or tr('e_write_failed'))


def free_backup_name(src):
    """Wolna nazwa kopii zapasowej; 'brak dostępu' (None) też traktujemy jako zajęte."""
    stamp = time.strftime('%Y-%m-%d_%H-%M-%S')
    backup = f'{src}-{stamp}.bak'
    n = 1
    while fs_stat_many([backup])[0]['e'] is not False:
        n += 1
        backup = f'{src}-{stamp}-{n}.bak'
    return backup


def remove_file(path):
    try:
        os.remove(path)
        return
    except FileNotFoundError:
        return
    except PermissionError:
        pass
    if not priv_alive():
        raise NeedAdmin(tr('e_remove_admin'))
    r = priv_call({'op': 'remove', 'path': path})
    if not r.get('ok'):
        raise RuntimeError(r.get('err') or tr('e_remove_failed'))


def read_protected(path):
    """Bajty pliku albo None; bez uprawnień czyta przez proces ADMIN (z cache w katalogu tymczasowym)."""
    try:
        with open(path, 'rb') as f:
            return f.read()
    except (FileNotFoundError, NotADirectoryError, IsADirectoryError):
        return None
    except PermissionError:
        if IS_ROOT or not priv_alive() or not STATE['tmp']:
            return None
    cache = os.path.join(STATE['tmp'], 'imgcache')
    os.makedirs(cache, exist_ok=True)
    dst = os.path.join(cache, hashlib.sha1(path.encode('utf-8')).hexdigest())
    if not os.path.exists(dst):
        try:
            r = priv_call({'op': 'read', 'src': path, 'dst': dst})
        except NeedAdmin:
            return None
        if not r.get('ok'):
            return None
    with open(dst, 'rb') as f:
        return f.read()


# ---------- usługa Jellyfina (systemd / Docker): start i stop ----------

SERVICE = {'kind': None, 'name': None, 'source': None, 't': 0.0}


def svc_detect(force=False):
    if not force and SERVICE['t'] and time.time() - SERVICE['t'] < 30:
        return SERVICE
    found = {'kind': None, 'name': None, 'source': None}
    spec = SETTINGS.get('jf_service') or ''
    if ':' in spec:
        kind, name = spec.split(':', 1)
        if svc_cmd(kind, name, 'is-active'):
            found = {'kind': kind, 'name': name, 'source': tr('src_settings')}
    if not found['kind'] and shutil.which('systemctl'):
        try:
            if subprocess.run(['systemctl', 'cat', 'jellyfin.service'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=5).returncode == 0:
                found = {'kind': 'systemd', 'name': 'jellyfin', 'source': tr('src_detected')}
        except (OSError, subprocess.SubprocessError):
            pass
    if not found['kind'] and shutil.which('docker'):
        out = None
        try:
            r = subprocess.run(svc_cmd('docker', '', 'list'), capture_output=True, text=True, timeout=8)
            if r.returncode == 0:
                out = r.stdout
        except (OSError, subprocess.SubprocessError):
            pass
        if out is None and priv_alive() and not IS_ROOT:
            try:
                r = priv_call({'op': 'svc', 'kind': 'docker', 'name': '', 'action': 'list'})
                out = r.get('out') if r.get('ok') else None
            except NeedAdmin:
                pass
        for line in (out or '').splitlines():
            if 'jellyfin' in line.lower() and line.split('\t')[0]:
                found = {'kind': 'docker', 'name': line.split('\t')[0], 'source': tr('src_detected')}
                break
    SERVICE.update(found, t=time.time())
    return SERVICE


def run_svc(sv, action):
    cmd = svc_cmd(sv['kind'], sv['name'], action)
    if not cmd:
        raise ValueError(tr('e_service_denied'))
    if sv['kind'] == 'docker' and not IS_ROOT:  # członek grupy docker może działać bez sudo
        try:
            if subprocess.run(cmd, capture_output=True, text=True, timeout=120).returncode == 0:
                return
        except (OSError, subprocess.SubprocessError):
            pass
    if IS_ROOT:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        ok, out = r.returncode == 0, (r.stdout + r.stderr).strip()
    elif priv_alive():
        r = priv_call({'op': 'svc', 'kind': sv['kind'], 'name': sv['name'], 'action': action}, timeout=130)
        ok, out = r.get('ok'), r.get('out') or r.get('err')
    else:
        raise NeedAdmin(tr('e_service_admin'))
    if not ok:
        raise RuntimeError(tr('e_service_failed', out=out))


def api_service(body):
    action = (body or {}).get('action')
    if action not in ('start', 'stop'):
        raise ValueError(tr('e_unknown_action'))
    sv = svc_detect(True)
    if not sv['kind']:
        raise ValueError(tr('e_no_service'))
    run_svc(sv, action)
    deadline = time.time() + (60 if action == 'start' else 30)
    res = jf_detect()
    while time.time() < deadline:
        res = jf_detect()
        if (action == 'stop' and res['state'] != 'running') or (action == 'start' and res['state'] == 'running'):
            break
        time.sleep(1.5)
    JF.update(res)
    return {'ok': True, 'state': res['state'], 'port': res['port']}


def open_copy(src, kind='path', label=None):
    """Pobiera świeżą kopię bazy: tmp/orig (nietknięta) + tmp/work.db (robocza).
    kind='path' - oryginał leży pod ścieżką src (Upload możliwy);
    kind='upload' - plik wczytany z komputera przez przeglądarkę (tylko eksport).
    Przy błędzie dotychczasowy stan zostaje nietknięty."""
    tmp = tempfile.mkdtemp(prefix='jfdb_', dir=work_tmp())
    try:
        sig = file_sig(src)
        od = os.path.join(tmp, 'orig')
        os.makedirs(od)
        orig = os.path.join(od, 'jellyfin.db')
        infos = fs_stat_many([src + suf for suf in ('', '-wal', '-shm')])
        if infos[0]['e'] is False:
            raise DbError('e_file_notfound', path=src)
        total = sum((i.get('s') or 0) for i in infos if i['e'])
        job_set('copy', 0, total or 1)
        for suf, inf in zip(('', '-wal', '-shm'), infos):
            if inf['e'] is not False:   # istnieje albo nie wiadomo (brak dostępu) - próbuj kopiować
                try:
                    copy_with_progress(src + suf, orig + suf, total)
                except FileNotFoundError:
                    if suf == '':
                        raise
        if file_sig(src) != sig:
            sig = None  # oryginał zmieniał się w trakcie kopiowania (działa Jellyfin?) - Upload będzie zablokowany
        work = os.path.join(tmp, 'work.db')
        o = sqlite3.connect(orig)
        w = sqlite3.connect(work)

        def _bp(status, remaining, total_pages):
            job_set('work', (total_pages - remaining) if total_pages else None, total_pages)

        o.backup(w, pages=2048, progress=_bp)
        w.close()
        o.close()
        con = sqlite3.connect(work, check_same_thread=False, isolation_level=None)
        con.row_factory = sqlite3.Row
        try:
            con.execute('SELECT 1 FROM BaseItems LIMIT 1')
        except sqlite3.OperationalError:
            con.close()
            raise DbError('e_not_jellyfin_db')
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    old_con, old_tmp = STATE['con'], STATE['tmp']
    STATE.update(con=con, tmp=tmp, src=src, orig=orig, work=work, dirty=0, sig=sig,
                 problems=None, pmap=None, libs=None, roots=[], kind=kind, label=label or src,
                 nodb_reason=None, unreadable=0, deleted=[])
    if old_con:
        old_con.close()
    if old_tmp:
        shutil.rmtree(old_tmp, ignore_errors=True)


def reset_work():
    """Odrzuca zmiany: kopia robocza odtwarzana z nietkniętego snapshotu (działa też dla plików z komputera)."""
    work = STATE['work'] + '.new'
    for suf in ('', '-wal', '-shm'):
        if os.path.exists(work + suf):
            os.remove(work + suf)
    o = sqlite3.connect(STATE['orig'])
    w = sqlite3.connect(work)
    try:
        o.backup(w)
    finally:
        w.close()
        o.close()
    old = STATE['con']
    if old:
        old.close()
    try:
        os.replace(work, STATE['work'])          # nadpisuje atomowo, stare pliki zostają do czasu sukcesu
        for suf in ('-wal', '-shm'):
            p = STATE['work'] + suf
            if os.path.exists(p):
                os.remove(p)
        con = sqlite3.connect(STATE['work'], check_same_thread=False, isolation_level=None)
        con.row_factory = sqlite3.Row
    except Exception:
        try:
            con = sqlite3.connect(STATE['work'], check_same_thread=False, isolation_level=None)
            con.row_factory = sqlite3.Row
            STATE['con'] = con
        except sqlite3.Error:
            STATE['con'] = None
        raise
    STATE.update(con=con, dirty=0, deleted=[], problems=None, pmap=None, libs=None)


def q(sql, args=()):
    with LOCK:
        return [dict(r) for r in STATE['con'].execute(sql, args).fetchall()]


def short(t):
    return (t or '').split('.')[-1]


def images_for(ids):
    out = {}
    ids = list(ids)
    for i in range(0, len(ids), 500):
        part = ids[i:i + 500]
        ph = ','.join('?' * len(part))
        for r in q(f'SELECT Id, ItemId, ImageType FROM BaseItemImageInfos '
                   f'WHERE ItemId IN ({ph}) ORDER BY ImageType', part):
            out.setdefault(r['ItemId'], []).append(
                {'id': r['Id'], 'type': IMG_TYPES.get(r['ImageType'], str(r['ImageType']))})
    return out


# ---------- problemy (brakujące pliki, duplikaty) ----------

def norm(x):
    return (x or '').replace('-', '').lower()


def real_path(p):
    return bool(p) and (p.startswith('/') or (len(p) > 2 and p[1] == ':'))


def _decode_mp(x):
    return x.replace('\\040', ' ').replace('\\011', '\t').replace('\\134', '\\')


def parse_mounts(lines):
    out = set()
    for l in lines:
        p = l.split()
        if len(p) >= 2:
            out.add(_decode_mp(p[1]))
    return out


def read_mounts():
    """Aktualnie zamontowane punkty (Linux: /proc/mounts); None gdy się nie da."""
    for f in ('/proc/mounts', '/proc/self/mounts'):
        try:
            with open(f, encoding='utf-8', errors='replace') as fh:
                return parse_mounts(fh)
        except OSError:
            continue
    return None


def parse_fstab(lines):
    out = set()
    for l in lines:
        p = l.split('#')[0].split()
        if len(p) >= 4 and p[1].startswith('/') and p[1] != '/' and p[2] != 'swap':
            if 'noauto' in p[3].split(','):
                continue
            out.add(_decode_mp(p[1]))
    return out


def read_fstab():
    """Punkty montowania, które system powinien mieć (/etc/fstab); pusty zbiór gdy brak pliku."""
    try:
        with open('/etc/fstab', encoding='utf-8', errors='replace') as f:
            return parse_fstab(f)
    except OSError:
        return set()


def under(p, mp):
    return p == mp or p.startswith(mp.rstrip('/') + '/')


STATUS_SHORT = {
    'unmounted_fstab': 'dysk niezamontowany',
    'unmounted': 'dysk obecny, niezamontowany',
    'detached': 'brak dysku (odłączony)',
    'empty': 'pusty punkt montowania (dysk niezamontowany?)',
    'missing': 'folder główny nie istnieje',
    'missing_mounted': 'folder główny usunięty (dysk zamontowany)',
    'empty_mounted': 'folder główny pusty (dysk zamontowany)',
}
STATUS_LONG = {
    'ok': 'dysk i folder są dostępne',
    'unmounted': 'urządzenie jest w systemie, ale nie jest zamontowane',
    'detached': 'urządzenie zniknęło z systemu (dysk odłączony)',
    'unknown': 'nie sprawdzono (brak dostępu do dysków na tym komputerze)',
    'unmounted_fstab': 'dysk niezamontowany (jest w /etc/fstab, nie ma go w /proc/mounts)',
    'empty': 'folder pusty, bez osobnego montowania - wygląda na punkt montowania bez dysku',
    'missing': 'folder nie istnieje (dysk niezamontowany albo folder usunięty - brak wpisu w fstab, nie rozróżnię)',
    'missing_mounted': 'dysk jest zamontowany, ale folderu nie ma (usunięty lub przeniesiony)',
    'empty_mounted': 'dysk jest zamontowany, ale folder jest pusty (pliki usunięte lub przeniesione)',
}


def job_set(phase=None, done=None, total=None, msg=None):
    j = STATE.get('job') or {}
    if phase:
        j['phase'] = phase
    if done is not None:
        j['done'] = done
    if total is not None:
        j['total'] = total
    if msg is not None:
        j['msg'] = msg
    STATE['job'] = j
    return j


def copy_db_files(src, dst):
    """Kopiuje bazę + -wal/-shm i pilnuje, żeby źródło nie zmieniło się w trakcie kopiowania."""
    sig = file_sig(src)
    infos = fs_stat_many([src + suf for suf in ('', '-wal', '-shm')])
    if infos[0]['e'] is False:
        raise DbError('e_file_notfound', path=src)
    total = sum((i.get('s') or 0) for i in infos if i['e'])
    for suf, inf in zip(('', '-wal', '-shm'), infos):
        if inf['e'] is not False:
            try:
                copy_with_progress(src + suf, dst + suf, total)
            except FileNotFoundError:
                if suf == '':
                    raise
    if file_sig(src) != sig:
        raise RuntimeError(tr('e_changing'))
    return sig


def copy_with_progress(src, dst, total=0):
    try:
        f = open(src, 'rb')
    except OSError:
        copy_from_protected(src, dst)
        return
    done = 0
    with f, open(dst, 'wb') as out:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            out.write(b)
            done += len(b)
            job_set('copy', done, total or done)
    try:
        shutil.copystat(src, dst)
    except OSError:
        pass


def parse_lsblk(text):
    data = json.loads(text)
    mounts, devs = {}, set()

    def walk(items):
        for it in items or []:
            name = it.get('name')
            mp = it.get('mountpoint')
            if name:
                devs.add(name)
            if name and mp:
                mounts[mp] = name
            walk(it.get('children'))

    walk(data.get('blockdevices'))
    return {'mounts': mounts, 'devices': devs}


def read_lsblk():
    exe = shutil.which('lsblk')
    if not exe:
        return None
    try:
        r = subprocess.run([exe, '-J', '-o', 'NAME,MOUNTPOINT,TYPE'], capture_output=True, timeout=5)
        if r.returncode != 0:
            return None
        return parse_lsblk(r.stdout.decode('utf-8', 'replace'))
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def best_mount(path, mounts, fstab, dmap):
    cands = []
    for src in (mounts, fstab, dmap):
        if src:
            cands += [mp for mp in src if under(path, mp)]
    return max(cands, key=len) if cands else ''


def root_status(path, mounts, fstab, trust, lsblk, dmap):
    """Status folderu głównego: montowania z /proc + lsblk + zapamiętana mapa ścieżka->urządzenie."""
    mp = best_mount(path, mounts, fstab, dmap)
    mounted = mounts is not None
    if mp and mounted and mp in mounts:
        return disk_status(path, mounts, fstab, trust)
    if mp and (mp in fstab or mp in dmap):
        if lsblk is None:
            return disk_status(path, mounts, fstab, trust)
        dev = dmap.get(mp)
        if dev:
            return 'unmounted' if dev in lsblk['devices'] else 'detached'
        return 'unmounted_fstab'
    return disk_status(path, mounts, fstab, trust)


def disk_status(path, mounts, fstab, trust):
    """Heurystyka: dlaczego folder główny jest (nie)dostępny. Pewność największa dla 'unmounted_fstab'."""
    if not trust and mounts is None:
        return 'unknown'
    p = path.rstrip('/') or '/'
    fs = [mp for mp in fstab if under(p, mp)]
    if fs and mounts is not None and max(fs, key=len) not in mounts:
        return 'unmounted_fstab'
    mounted_here = mounts is not None and any(mp != '/' and under(p, mp) for mp in mounts)
    inf = fs_stat_many([p])[0]
    if inf['e'] is None:
        return 'unknown'
    if inf['e'] is False or not inf['d']:
        return 'missing_mounted' if mounted_here else 'missing'
    if inf.get('n') is None:
        return 'unknown'
    if inf['n']:
        return 'ok'
    return 'empty_mounted' if mounted_here else 'empty'


def qi(name):
    """Bezpieczny identyfikator SQL (nazwa tabeli/kolumny z bazy)."""
    return '"' + str(name).replace('"', '""') + '"'


def orphan_targets():
    """Tabele/kolumny powiązane z BaseItems, które mogą zawierać sieroty (bez UserData)."""
    con = STATE['con']
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    out = []
    for t in tables:
        if t in ('BaseItems', 'UserData'):
            continue
        cols = set()
        try:
            for fk in con.execute(f'PRAGMA foreign_key_list({qi(t)})'):
                if fk[2] == 'BaseItems' and fk[3]:
                    cols.add(fk[3])
        except sqlite3.Error:
            pass
        if not cols and t.startswith('BaseItem'):
            try:
                names = {r[1] for r in con.execute(f'PRAGMA table_info({qi(t)})')}
                cols.update(names & {'ItemId', 'BaseItemId'})
            except sqlite3.Error:
                pass
        for col in sorted(cols):
            out.append((t, col))
    return out


def api_orphans(clean=False):
    removed, remaining = [], []
    with LOCK:
        con = STATE['con']
        targets = orphan_targets()
        if clean:
            con.execute('BEGIN')
            try:
                for t, col in targets:
                    where = (f'{qi(col)} IS NOT NULL AND NOT EXISTS '
                             f'(SELECT 1 FROM BaseItems b WHERE b.Id = {qi(t)}.{qi(col)})')
                    cur = con.execute(f'DELETE FROM {qi(t)} WHERE {where}')
                    if cur.rowcount:
                        removed.append({'table': t, 'column': col, 'rows': cur.rowcount})
                con.execute('COMMIT')
            except Exception:
                con.execute('ROLLBACK')
                raise
        for t, col in orphan_targets():
            n = con.execute(
                f'SELECT COUNT(*) FROM {qi(t)} WHERE {qi(col)} IS NOT NULL AND NOT EXISTS '
                f'(SELECT 1 FROM BaseItems b WHERE b.Id = {qi(t)}.{qi(col)})').fetchone()[0]
            if n:
                remaining.append({'table': t, 'column': col, 'rows': n})
        total = sum(x['rows'] for x in remaining)
        removed_total = sum(x['rows'] for x in removed)
        if removed_total:
            STATE['dirty'] += removed_total
            STATE['problems'] = None
            STATE['pmap'] = None
    return {'tables': remaining, 'total': total, 'removed': removed, 'removed_total': removed_total}


def ids_in(ids):
    """Bezpieczne 'IN (?,?,...)' dla listy identyfikatorów (bez tabel tymczasowych)."""
    ids = list(dict.fromkeys(i for i in ids if i))
    if not ids:
        return '(NULL)', []
    return '(' + ','.join('?' * len(ids)) + ')', ids


def libfolders_cte(libs):
    """CTE _libfolders(LibId,FolderId) z par biblioteka→folder (zamiast tabeli tymczasowej)."""
    pairs = list(dict.fromkeys((l['Id'], f) for l in libs for f in l.get('folders', []) if f))
    if not pairs:
        return '', []
    sql = 'WITH _libfolders(LibId,FolderId) AS (VALUES ' + ','.join('(?,?)' for _ in pairs) + ') '
    return sql, [v for p in pairs for v in p]


def libraries():
    """Biblioteki z bazy. Foldery fizyczne bierzemy z pola Data wiersza CollectionFolder
    (PhysicalFolderIds / PhysicalLocationsList). Dodatkowo wyznaczamy foldery osierocone
    (fizyczne, ale bez biblioteki) i stan każdego folderu (dysk zamontowany / brak)."""
    if STATE['libs'] is not None:
        return STATE['libs']
    cfs = q(f"SELECT Id, Name, Path, Data FROM BaseItems WHERE {LIB_TYPE} ORDER BY Name COLLATE NOCASE")
    phys = q("SELECT Id, Path FROM BaseItems WHERE TopParentId = Id")  # korzenie: foldery fizyczne
    by_norm = {norm(r['Id']): r['Id'] for r in phys}
    by_path = {}
    for r in phys:
        if r['Path']:
            by_path.setdefault(r['Path'].rstrip('/'), []).append(r['Id'])
    libs, pairs = [], []
    for cf in cfs:
        try:
            d = json.loads(cf['Data'] or '{}')
        except ValueError:
            d = {}
        fids = {by_norm[norm(x)] for x in d.get('PhysicalFolderIds', []) if norm(x) in by_norm}
        for pth in d.get('PhysicalLocationsList', []):
            fids.update(by_path.get(pth.rstrip('/'), []))
        libs.append({'Id': cf['Id'], 'Name': cf['Name'], 'Path': cf['Path'],
                     'CollectionType': d.get('CollectionType'), 'folders': sorted(fids)})
        pairs += [(cf['Id'], f) for f in fids]
    usable = bool(pairs)

    roots = []
    if usable:
        lib_of = {}
        for lid, f in pairs:
            lib_of.setdefault(f, lid)
        cand = [r for r in phys if real_path(r['Path'])]
        mounts, fstab = read_mounts(), read_fstab()
        ls = read_lsblk()
        if ls and ls.get('mounts'):
            dmap = dict(SETTINGS.get('disk_map') or {})
            changed = False
            for mp, dev in ls['mounts'].items():
                if dmap.get(mp) != dev:
                    dmap[mp] = dev
                    changed = True
            if changed:
                SETTINGS['disk_map'] = dmap
                save_settings()
        dmap = SETTINGS.get('disk_map') or {}
        trust = any(i['e'] and i['d'] for i in fs_stat_many([r['Path'] for r in cand]))  # żaden folder nie istnieje -> to chyba nie serwer
        seen = set()
        for r in cand:
            seen.add(r['Id'])
            roots.append({'Id': r['Id'], 'Path': r['Path'], 'LibId': lib_of.get(r['Id']),
                          'Kind': 'lib' if r['Id'] in lib_of else 'orph',
                          'Status': root_status(r['Path'], mounts, fstab, trust, ls, dmap)})
        for f, lid in lib_of.items():
            if f not in seen:
                roots.append({'Id': f, 'Path': '', 'LibId': lid, 'Kind': 'lib', 'Status': 'unknown'})
    STATE['roots'] = roots
    STATE['libs'] = libs if usable else []
    return STATE['libs']


def get_problems():
    if STATE['problems'] is not None:
        return STATE['problems']
    cols = ('Id, Name, Type, Path, ParentId, TopParentId, SeriesId, SeriesName, IndexNumber, '
            'ParentIndexNumber, ProductionYear, Size')
    bcols = ', '.join('b.' + c.strip() for c in cols.split(','))
    libs = libraries()
    has_libs = bool(libs)
    roots = STATE['roots']
    if has_libs:
        scope_ids, scope_args = ids_in([r['Id'] for r in roots])
        scope = f'TopParentId IN {scope_ids}'
    else:
        scope, scope_args = '1=1', []   # brak bibliotek w bazie -> skanuj wszystko
    items = {}
    status_of = {r['Id']: r['Status'] for r in roots}

    def add(r, reason):
        e = items.setdefault(r['Id'], dict(r, reasons=[]))
        if reason not in e['reasons']:
            e['reasons'].append(reason)

    if has_libs:  # wpisy pod folderami, których żadna biblioteka już nie obejmuje
        orph = [r['Id'] for r in roots if r['Kind'] == 'orph']
        if orph:
            ph, pa = ids_in(orph)
            for r in q(f"SELECT {cols} FROM BaseItems WHERE TopParentId IN {ph}", pa):
                add(r, 'r_orphan')
    cand = [r for r in q(f"SELECT {cols} FROM BaseItems WHERE {scope} AND Path IS NOT NULL AND Path != ''",
                         scope_args)
            if real_path(r['Path'])]
    ex = exists_map([r['Path'] for r in cand])
    STATE['unreadable'] = sum(1 for r in cand if ex[r['Path']] is None)
    for r in cand:
        if ex[r['Path']] is False:   # None (brak uprawnień) NIE jest uznawane za brak pliku
            st = status_of.get(r['TopParentId'])
            add(r, 'r_missing' if st in (None, 'ok', 'unknown')
                else 'r_root_down:' + st)
    for r in q(f"""SELECT {cols} FROM BaseItems WHERE {scope} AND (Path, Type) IN (
                     SELECT Path, Type FROM BaseItems
                     WHERE {scope} AND Path IS NOT NULL AND Path != ''
                     GROUP BY Path, Type HAVING COUNT(*) > 1)""", scope_args + scope_args):
        add(r, 'r_dup_path')
    if has_libs:  # ta sama pozycja (typ + nazwa + rok) dwa razy w jednej bibliotece, także na różnych dyskach
        cte, cte_args = libfolders_cte(libs)
        if cte:
            for r in q(cte + f"""SELECT {bcols} FROM BaseItems b JOIN _libfolders f ON f.FolderId = b.ParentId
                         WHERE (f.LibId, b.Type, lower(b.Name), COALESCE(b.ProductionYear, 0)) IN (
                           SELECT f2.LibId, b2.Type, lower(b2.Name), COALESCE(b2.ProductionYear, 0)
                           FROM BaseItems b2 JOIN _libfolders f2 ON f2.FolderId = b2.ParentId
                           GROUP BY f2.LibId, b2.Type, lower(b2.Name), COALESCE(b2.ProductionYear, 0)
                           HAVING COUNT(*) > 1)""", cte_args):
                add(r, 'r_dup_item')
    for r in q(f"""SELECT {cols} FROM BaseItems WHERE Type LIKE '%.Episode' AND PrimaryVersionId IS NULL
                     AND (SeriesId, ParentIndexNumber, IndexNumber) IN (
                       SELECT SeriesId, ParentIndexNumber, IndexNumber FROM BaseItems
                       WHERE Type LIKE '%.Episode' AND PrimaryVersionId IS NULL
                         AND SeriesId IS NOT NULL AND IndexNumber IS NOT NULL
                       GROUP BY SeriesId, ParentIndexNumber, IndexNumber HAVING COUNT(*) > 1)"""):
        add(r, 'r_dup_episode')

    out = list(items.values())

    def key(r):
        return ((r['SeriesName'] or r['Name'] or '').lower(),
                r['ParentIndexNumber'] if r['ParentIndexNumber'] is not None else -1,
                r['IndexNumber'] if r['IndexNumber'] is not None else -1,
                r['ProductionYear'] or 0,
                r['Id'])

    out.sort(key=key)
    STATE['problems'] = out
    return out


def problem_map():
    """id pozycji najwyższego poziomu (bezpośrednio w folderze fizycznym) oraz id samego folderu
    -> liczba i powody problemów pod nimi."""
    if STATE['pmap'] is not None:
        return STATE['pmap']
    libs = libraries()
    has_libs = bool(libs)
    phys, parent = set(), {}
    if has_libs:
        phys = {r['Id'] for r in STATE['roots']}
        ph, pa = ids_in(phys)
        parent = {r['Id']: r['ParentId'] for r in q(
            f"SELECT Id, ParentId FROM BaseItems WHERE TopParentId IN {ph}", pa)}

    def top(i):
        cur = i
        for _ in range(60):
            p = parent.get(cur)
            if p is None or p in phys or p not in parent:
                return cur
            cur = p
        return cur

    pm = {}

    def bump(k, reasons):
        e = pm.setdefault(k, {'n': 0, 'reasons': set()})
        e['n'] += 1
        e['reasons'].update(reasons)

    for r in get_problems():
        if has_libs:
            bump(top(r['Id']), r['reasons'])
            root = r.get('TopParentId')
            if root and root != r['Id'] and root in phys:
                bump(root, r['reasons'])
        else:
            bump(r['SeriesId'] or r['Id'], r['reasons'])
    STATE['pmap'] = pm
    return pm


def api_problems(params):
    allp = get_problems()
    out = [dict(r) for r in allp[:5000]]
    for r in out:
        r['reasons'] = [reason_text(x) for x in r['reasons']]
    imgs = images_for([r['Id'] for r in out])
    for r in out:
        r['depth'] = 0
        r['short'] = short(r['Type'])
        r['images'] = imgs.get(r['Id'], [])
    annotate_exists(out)
    annotate_disks(out)
    annotate_suggest(out)
    return {'items': out, 'total': len(allp), 'limit': 5000}


# ---------- lista i drzewo ----------

def disk_color(status, items):
    if items == 0:
        return 'blue'
    if status == 'ok':
        return 'green'
    if status == 'unknown':
        return 'gray'
    if status in ('missing', 'detached'):
        return 'red'
    return 'orange'


def disk_counts():
    rows = q('SELECT TopParentId, COUNT(*) AS n FROM BaseItems WHERE TopParentId IS NOT NULL GROUP BY TopParentId')
    return {r['TopParentId']: r['n'] for r in rows}


def disk_mount_point(path, mounts):
    """Punkt montowania dysku dla ścieżki (np. /mnt/SG1/Films -> /mnt/SG1)."""
    if not path:
        return ''
    if mounts:
        cands = [mp for mp in mounts if mp != '/' and under(path.rstrip('/'), mp)]
        if cands:
            return max(cands, key=len)
    p = path.rstrip('/')
    if p.startswith('/'):
        parts = p.split('/')
        if len(parts) >= 3:
            return '/'.join(parts[:3])
    if len(p) > 2 and p[1] == ':':
        return p[:3]
    return p


def disk_list():
    libs = libraries()
    if not STATE['roots']:
        return []
    cnt = disk_counts()
    names = {l['Id']: (l['Name'] or l['Id']) for l in libs}
    mounts = read_mounts()
    out = []
    for r in STATE['roots']:
        n = cnt.get(r['Id'], 0)
        out.append({'id': r['Id'], 'path': r['Path'], 'lib': r['LibId'], 'libname': names.get(r['LibId']),
                    'kind': r['Kind'], 'status': r['Status'], 'items': n,
                    'mount': disk_mount_point(r['Path'], mounts),
                    'color': disk_color(r['Status'], n)})
    order = {'red': 0, 'orange': 1, 'gray': 2, 'green': 3, 'blue': 4}
    out.sort(key=lambda x: (order.get(x['color'], 9), (x['path'] or '').lower()))
    return out


def mount_list(disks):
    """Dyski fizyczne: grupowanie folderów bibliotek po punkcie montowania."""
    worst = {'red': 4, 'orange': 3, 'gray': 2, 'green': 1, 'blue': 0}
    order = {'red': 0, 'orange': 1, 'gray': 2, 'green': 3, 'blue': 4}
    by = {}
    for d in disks:
        mp = d.get('mount') or d.get('path') or d.get('id')
        e = by.setdefault(mp, {'path': mp, 'items': 0, 'color': 'green', 'status': 'ok'})
        e['items'] += d['items']
        if worst.get(d['color'], 0) > worst.get(e['color'], 0):
            e['color'] = d['color']
            e['status'] = d['status']
    out = list(by.values())
    for e in out:
        if e['items'] == 0:
            e['color'] = 'blue'
    out.sort(key=lambda x: (order.get(x['color'], 9), (x['path'] or '').lower()))
    return out


def disk_color_map():
    if not STATE['roots']:
        return {}
    return {d['id']: d['color'] for d in disk_list()}


def annotate_disks(rows):
    cols = disk_color_map()
    for r in rows:
        r['dcolor'] = cols.get(r.get('TopParentId')) if cols else None


def annotate_suggest(rows):
    """Dla grup duplikatów: wpisy bez istniejących plików sugerujemy do usunięcia."""
    groups = {}
    for r in rows:
        t = short(r.get('Type'))
        if t == 'Episode' and r.get('SeriesId') and r.get('IndexNumber') is not None:
            k = ('ep', r.get('SeriesId'), r.get('ParentIndexNumber'), r.get('IndexNumber'))
        else:
            k = ('it', r.get('Type'), (r.get('Name') or '').lower(), r.get('ProductionYear') or 0)
        groups.setdefault(k, []).append(r)
    for g in groups.values():
        if len(g) < 2:
            continue
        ex = [r for r in g if r.get('exists')]
        if not ex or len(ex) == len(g):
            continue
        for r in g:
            r['suggest'] = not r.get('exists')


def risky_disks(ids):
    """Dyski o statusie innym niż ok/unknown, na których leżą wybrane wpisy."""
    roots = {r['Id']: r for r in STATE['roots']}
    if not roots:
        return []
    ids = list(ids)
    found = {}
    for i in range(0, len(ids), 400):
        part = ids[i:i + 400]
        ph = ','.join('?' * len(part))
        for r in q(f'SELECT Id, TopParentId FROM BaseItems WHERE Id IN ({ph})', part):
            root = roots.get(r['TopParentId'])
            if not root or root['Status'] in ('ok', 'unknown'):
                continue
            e = found.setdefault(r['TopParentId'], {'path': root['Path'], 'status': root['Status'], 'n': 0})
            e['n'] += 1
    out = list(found.values())
    out.sort(key=lambda x: (x['status'] != 'missing', x['path'] or ''))
    return out


def api_disks(params):
    if params.get('refresh'):
        _invalidate_fs_caches()
    disks = disk_list()
    return {'disks': disks, 'mounts': mount_list(disks)}


def api_types():
    libs = libraries()
    if libs:
        cte, cte_args = libfolders_cte(libs)
        cnt = ({r['LibId']: r['n'] for r in q(
            cte + "SELECT f.LibId, COUNT(*) AS n FROM BaseItems b JOIN _libfolders f ON f.FolderId = b.ParentId "
                  "GROUP BY f.LibId", cte_args)} if cte else {})
        items = [{'key': 'lib:' + l['Id'], 'label': l['Name'] or l['Id'], 'n': cnt.get(l['Id'], 0)}
                 for l in libs]
        roots = STATE['roots']
        ph, pa = ids_in([r['Id'] for r in roots])
        kids = {r['ParentId']: r['n'] for r in q(
            f"SELECT ParentId, COUNT(*) AS n FROM BaseItems WHERE ParentId IN {ph} GROUP BY ParentId", pa)}
        bad = [r for r in roots if r['Kind'] == 'lib' and r['Status'] not in ('ok', 'unknown')]
        orph = [r for r in roots if r['Kind'] == 'orph']
        if bad:
            items.append({'key': 'nodisk', 'label': tr('cat_nodisk'),
                          'n': sum(kids.get(r['Id'], 0) for r in bad)})
            for r in sorted(bad, key=lambda x: x['Path']):
                items.append({'key': 'root:' + r['Id'], 'n': kids.get(r['Id'], 0),
                              'label': tr('cat_root_bad', path=r['Path'], status=status_short(r['Status']))})
        if orph:
            items.append({'key': 'orph', 'label': tr('cat_orph'), 'n': len(orph)})
            for r in sorted(orph, key=lambda x: x['Path']):
                items.append({'key': 'root:' + r['Id'], 'n': kids.get(r['Id'], 0),
                              'label': tr('cat_root_orph', path=r['Path'], status=status_long(r['Status']))})
        return {'mode': 'library', 'items': items}
    rows = q('SELECT Type, COUNT(*) AS n FROM BaseItems GROUP BY Type ORDER BY n DESC')
    return {'mode': 'type',
            'items': [{'key': 'type:' + r['Type'], 'label': short(r['Type']), 'n': r['n']} for r in rows]}


def api_list(params):
    t = params.get('type', [''])[0]
    text = params.get('q', [''])[0]
    sort = params.get('sort', ['name'])[0]
    try:
        limit = int(params.get('limit', ['2000'])[0])
    except (TypeError, ValueError):
        limit = 2000
    limit = max(1, min(5000, limit))
    try:
        offset = int(params.get('offset', ['0'])[0])
    except (TypeError, ValueError):
        offset = 0
    offset = max(0, offset)
    libs = libraries()
    where, args = [], []
    if t.startswith('lib:'):
        lib = next((l for l in libs if l['Id'] == t[4:]), None) if t[4:] else None
        ph, pa = ids_in(lib['folders'] if lib else [])
        where.append(f'ParentId IN {ph}')
        args += pa
    elif t.startswith('type:'):
        where.append('Type = ?')
        args.append(t[5:])
    elif t == 'nodisk':
        ids = [r['Id'] for r in STATE['roots']
               if r['Kind'] == 'lib' and r['Status'] not in ('ok', 'unknown')]
        ph, pa = ids_in(ids)
        where.append(f'ParentId IN {ph}')
        args += pa
    elif t == 'orph':
        ph, pa = ids_in([r['Id'] for r in STATE['roots'] if r['Kind'] == 'orph'])
        where.append(f'Id IN {ph}')
        args += pa
    elif t.startswith('root:'):
        where.append('ParentId = ?')
        args.append(t[5:])
    elif libs:
        ph, pa = ids_in(f for l in libs for f in l.get('folders', []))
        where.append(f'ParentId IN {ph}')
        args += pa
    disk = params.get('disk', [''])[0]
    if disk:
        where.append('TopParentId = ?')
        args.append(disk)
    if text:
        where.append('(Name LIKE ? OR Path LIKE ? OR SeriesName LIKE ?)')
        args += [f'%{text}%'] * 3
    w = ('WHERE ' + ' AND '.join(where)) if where else ''
    scan_all = sort in ('only', 'problems')  # te tryby muszą znać problemy wszystkich pozycji
    sql = ('SELECT Id, Name, Type, Path, TopParentId, ProductionYear, SeriesName FROM BaseItems ' + w
           + ' ORDER BY lower(COALESCE(NULLIF(Name, \'\'), SortName)), COALESCE(ProductionYear,0), Id')
    if scan_all:
        rows = q(sql, args)
    else:
        rows = q(sql + ' LIMIT ? OFFSET ?', args + [limit, offset])
    pm = problem_map()
    for r in rows:
        e = pm.get(r['Id'])
        r['problems'] = e['n'] if e else 0
        r['reasons'] = sorted(reason_text(x) for x in e['reasons']) if e else []
    annotate_disks(rows)
    if scan_all:
        if sort == 'only':
            rows = [r for r in rows if r['problems']]
        rows.sort(key=lambda r: -r['problems'])  # sort stabilny: w grupie zostaje kolejność alfabetyczna
        rows = rows[offset:offset + limit]
    imgs = images_for([r['Id'] for r in rows])
    for r in rows:
        r['short'] = short(r['Type'])
        r['images'] = imgs.get(r['Id'], [])
    annotate_exists(rows)
    annotate_suggest(rows)
    return rows


def api_tree(params):
    root_id = params.get('id', [''])[0]
    root = q('SELECT * FROM BaseItems WHERE Id = ?', (root_id,))
    if not root:
        return []
    cols = 'Id, Name, Type, Path, ParentId, TopParentId, SeriesId, IndexNumber, ParentIndexNumber, ProductionYear, Size'
    desc = q(f'''WITH RECURSIVE t(Id) AS (
                   SELECT Id FROM BaseItems WHERE Id = ?
                   UNION
                   SELECT b.Id FROM BaseItems b JOIN t ON b.ParentId = t.Id)
                 SELECT {cols} FROM BaseItems WHERE Id IN (SELECT Id FROM t)''', (root_id,))
    in_tree = {r['Id'] for r in desc}
    extra = q(f'SELECT {cols} FROM BaseItems WHERE (SeriesId = ? OR SeasonId = ?)', (root_id, root_id))
    extra = [r for r in extra if r['Id'] not in in_tree]
    for r in extra:
        r['extra'] = True

    children = {}
    for r in desc:
        children.setdefault(r['ParentId'], []).append(r)

    def key(r):
        return (r['ParentIndexNumber'] if r['ParentIndexNumber'] is not None else -1,
                r['IndexNumber'] if r['IndexNumber'] is not None else -1,
                (r['Name'] or '').lower())

    ordered = []

    def walk(node, depth):
        node['depth'] = depth
        ordered.append(node)
        for c in sorted(children.get(node['Id'], []), key=key):
            walk(c, depth + 1)

    walk(next(r for r in desc if r['Id'] == root_id), 0)
    for r in sorted(extra, key=key):
        r['depth'] = 1
        ordered.append(r)

    by_id = {r['Id']: r['reasons'] for r in get_problems()}
    imgs = images_for([r['Id'] for r in ordered])
    for r in ordered:
        r['short'] = short(r['Type'])
        r['images'] = imgs.get(r['Id'], [])
        r['reasons'] = [reason_text(x) for x in by_id.get(r['Id'], [])]
    annotate_exists(ordered)
    annotate_disks(ordered)
    annotate_suggest(ordered)
    return ordered


# ---------- usuwanie (kopia robocza) i upload (oryginał) ----------

def api_delete(ids, force=False):
    if not isinstance(ids, list) or not ids or not all(isinstance(x, str) for x in ids):
        raise ValueError(tr('e_no_ids'))
    if len(ids) > 50000:
        raise ValueError(tr('e_too_many'))
    risky = risky_disks(ids)
    red = [d for d in risky if d['status'] == 'missing']
    if red and not force:
        lst = ', '.join(f"{d['path'] or d['status']} ({d['n']})" for d in red)
        raise ValueError(tr('e_disk_blocked', disks=lst))
    with LOCK:
        con = STATE['con']
        con.execute('BEGIN')
        deleted = 0
        try:
            for i in range(0, len(ids), 500):
                part = ids[i:i + 500]
                cur = con.execute(f'DELETE FROM BaseItems WHERE Id IN ({",".join("?" * len(part))})', part)
                deleted += cur.rowcount
            con.execute('COMMIT')
        except Exception:
            con.execute('ROLLBACK')
            raise
        STATE['dirty'] += deleted
        STATE['deleted'] = list(dict.fromkeys(STATE['deleted'] + ids))
        STATE['problems'] = None
        STATE['pmap'] = None
        STATE['libs'] = None
        return {'deleted': deleted, 'requested': len(ids), 'dirty': STATE['dirty']}


def rebase_work():
    """Oryginał zmienił się od pobrania kopii (typowo: Jellyfin zapisuje bazę przy zamykaniu).
    Pobiera go ponownie i stosuje te same usunięcia (po GUID), więc zmiany Jellyfina zostają zachowane."""
    ids = list(STATE['deleted'])
    before = STATE['dirty']
    with LOCK:
        open_copy(STATE['src'])
    if STATE['sig'] is None:
        raise RuntimeError(tr('e_changing'))
    if ids:
        api_delete(ids)
    if STATE['dirty'] == 0:
        raise ValueError(tr('e_nothing_left'))
    return {'before': before, 'after': STATE['dirty']}


class SchemaWarning(RuntimeError):
    """Baza nie zawiera tabel obecnych w oryginale — wymaga potwierdzenia (force_schema)."""

    def __init__(self, msg, missing=None):
        super().__init__(msg)
        self.missing = list(missing or [])


def schema_missing(orig_path, new_path):
    """Tabele obecne w oryginale, których brakuje w nowej bazie (bez sqlite_*)."""
    def names(p):
        con = ro_connect(p)
        try:
            return {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        finally:
            con.close()
    try:
        a = names(orig_path)
        b = names(new_path)
    except sqlite3.Error:
        return []
    return sorted(a - b)


class DbError(ValueError):
    """Błąd otwarcia bazy z kluczem tłumaczenia (powód lokalizowany przy żądaniu)."""

    def __init__(self, key, **kw):
        super().__init__(tr(key, **kw))
        self.key = key
        self.kw = kw


def api_upload(do_backup, ver='', force_schema=False):
    if STATE['kind'] == 'upload':
        raise ValueError(tr('e_upload_mode'))
    src = STATE['src']
    if STATE['dirty'] == 0:
        raise ValueError(tr('e_no_changes'))
    if CFG['service_check'] and shutil.which('systemctl'):
        if subprocess.run(['systemctl', 'is-active', '--quiet', 'jellyfin'],
                          stderr=subprocess.DEVNULL).returncode == 0:
            raise RuntimeError(tr('e_jf_running_unit'))
    if CFG['service_check']:
        st = jf_detect()
        if st['state'] == 'running':
            raise RuntimeError(tr('e_jf_running_port', port=st['port'], ver=st['info']['Version']))
    folder = os.path.dirname(os.path.abspath(src))
    writable = IS_ROOT or (os.access(src, os.W_OK) and os.access(folder, os.W_OK))
    if not writable and not priv_alive():
        raise NeedAdmin(tr('e_write_src', src=src))
    rebased = None
    if STATE['sig'] is None or file_sig(src) != STATE['sig']:
        rebased = rebase_work()
    st = fs_stat_many([src])[0]
    if not st['e']:
        raise RuntimeError(tr('e_read_src', src=src))

    scratch = tempfile.mkdtemp(prefix='jfup_', dir=work_tmp())
    hist = None
    try:
        backup = None
        sig_live = file_sig(src)
        if do_backup:
            backup = free_backup_name(src)
            tb = os.path.join(scratch, 'backup.db')
            live = os.path.join(scratch, 'live.db')
            sig_live = copy_db_files(src, live)  # kopia z żywego pliku, nie ze snapshotu
            o = ro_connect(live)
            b = sqlite3.connect(tb)
            o.backup(b)
            b.close()
            o.close()
            install_file(tb, backup, st)

        tn = os.path.join(scratch, 'new.db')
        with LOCK:
            w = sqlite3.connect(tn)
            STATE['con'].backup(w)
            w.close()
        c = sqlite3.connect(tn)
        res = c.execute('PRAGMA quick_check').fetchone()[0]
        c.close()
        if res != 'ok':
            raise RuntimeError(tr('e_quickcheck', res=str(res)))
        missing = schema_missing(STATE['orig'], tn)
        if missing and not force_schema:
            raise SchemaWarning(tr('e_schema_blocked', tables=', '.join(missing)), missing)
        if file_sig(src) != sig_live:
            raise RuntimeError(tr('e_changing'))  # Jellyfin zdążył zapisać bazę przed podmianą
        install_file(tn, src, st)          # atomowa podmiana (zapis obok + rename)
        for suf in ('-wal', '-shm'):       # stare pliki WAL/SHM oryginału nie mogą zostać przy nowej bazie
            remove_file(src + suf)
        try:
            hist = history_add(ver, tn)
        except (OSError, sqlite3.Error):
            hist = None
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    sent = STATE['dirty']
    with LOCK:
        open_copy(src)
    return {'sent': sent, 'backup': backup, 'rebased': rebased, 'history': hist['id'] if hist else None}


# ---------- historia uploadów ----------

def history_limit():
    try:
        n = int(SETTINGS.get('history_max', 5))
    except (TypeError, ValueError):
        n = 5
    return max(1, min(50, n))


def history_load():
    try:
        with open(HISTORY_INDEX, encoding='utf-8') as f:
            d = json.load(f)
        return d if isinstance(d, list) else []
    except (OSError, ValueError):
        return []


def history_save(recs):
    os.makedirs(HISTORY_DIR, exist_ok=True)
    tmp = HISTORY_INDEX + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(recs, f, ensure_ascii=False, indent=1)
    os.replace(tmp, HISTORY_INDEX)


def history_file(rec):
    return os.path.join(HISTORY_DIR, rec.get('file') or (rec.get('id', '') + '.db'))


def history_prune():
    recs = history_load()
    keep = history_limit()
    if len(recs) <= keep:
        return recs
    for old in recs[keep:]:
        f = history_file(old)
        try:
            os.remove(f)
        except OSError:
            pass
        try:
            os.rmdir(os.path.dirname(f))
        except OSError:
            pass
    recs = recs[:keep]
    history_save(recs)
    return recs


def history_clear():
    """Czyści TYLKO automatyczną historię uploadów (tmp/history). Ręczne kopie zostają."""
    recs = history_load()
    for r in recs:
        f = history_file(r)
        try:
            os.remove(f)
        except OSError:
            pass
        try:
            os.rmdir(os.path.dirname(f))
        except OSError:
            pass
    try:
        os.remove(HISTORY_INDEX)
    except OSError:
        pass
    try:
        os.rmdir(HISTORY_DIR)
    except OSError:
        pass
    return len(recs)


def history_verify():
    """Przy starcie sprawdza, czy pliki kopii nadal istnieją."""
    missing = [r.get('id', '?') for r in history_load() if not os.path.exists(history_file(r))]
    if missing:
        print('Historia: brak pliku kopii dla wpisów: ' + ', '.join(missing))
    return missing


def ro_connect(path):
    p = path.replace('\\', '/')
    return sqlite3.connect('file:' + quote(p, safe='/:') + '?mode=ro', uri=True)


def db_ids(path):
    con = ro_connect(path)
    try:
        return {r[0] for r in con.execute('SELECT Id FROM BaseItems')}
    finally:
        con.close()


def db_rows(path, ids):
    out = []
    con = ro_connect(path)
    try:
        ids = list(ids)
        for i in range(0, len(ids), 400):
            part = ids[i:i + 400]
            ph = ','.join('?' * len(part))
            for r in con.execute(f'SELECT Id, Name, Type, Path FROM BaseItems WHERE Id IN ({ph})', part):
                out.append({'Id': r[0], 'Name': r[1] or '', 'Type': short(r[2]), 'Path': r[3] or ''})
    finally:
        con.close()
    return out


def work_ids():
    with LOCK:
        return {r[0] for r in STATE['con'].execute('SELECT Id FROM BaseItems')}


def history_add(ver, snapshot_path):
    """Zapisuje kopię wgranej bazy i wpis w historii (różnica względem snapshotu orig)."""
    try:
        orig_ids = db_ids(STATE['orig'])
    except sqlite3.Error:
        orig_ids = set()
    cur_ids = work_ids()
    rem_ids = orig_ids - cur_ids
    add_ids = cur_ids - orig_ids
    removed = db_rows(STATE['orig'], rem_ids)
    added = db_rows(STATE['work'], add_ids)

    os.makedirs(HISTORY_DIR, exist_ok=True)
    rid = time.strftime('%Y%m%d-%H%M%S')
    n = 1
    while os.path.exists(os.path.join(HISTORY_DIR, rid)):
        n += 1
        rid = time.strftime('%Y%m%d-%H%M%S') + '-' + str(n)
    base = os.path.basename(STATE.get('src') or '') or 'jellyfin.db'
    folder = os.path.join(HISTORY_DIR, rid)
    os.makedirs(folder, exist_ok=True)
    dst = os.path.join(folder, base)
    shutil.copyfile(snapshot_path, dst)
    rec = {'id': rid, 'ts': time.strftime('%Y-%m-%d %H:%M:%S'), 'ver': (ver or '').strip(),
           'removed': len(rem_ids), 'added': len(add_ids),
           'items_removed': removed[:1000], 'items_added': added[:1000],
           'size': os.path.getsize(dst), 'file': rid + '/' + base, 'db_name': base}
    history_save([rec] + history_load())
    history_prune()
    return rec


def api_history(params):
    rid = params.get('id', [''])[0]
    recs = history_load()
    if rid:
        for r in recs:
            if r.get('id') == rid:
                return r
        raise ValueError(tr('e_history_missing'))
    out = [{k: v for k, v in r.items() if k not in ('items_removed', 'items_added')} for r in recs]
    for r in out:
        r['exists'] = os.path.exists(history_file(r))
    return {'limit': history_limit(), 'records': out}


def api_history_post(body):
    action = (body or {}).get('action')
    if action == 'clear':
        return {'ok': True, 'cleared': history_clear()}
    raise ValueError(tr('e_unknown_action'))


def api_settings(body):
    body = body or {}
    if 'history_max' in body:
        try:
            n = int(body['history_max'])
        except (TypeError, ValueError):
            raise ValueError(tr('e_history_max'))
        if not 1 <= n <= 50:
            raise ValueError(tr('e_history_max'))
        SETTINGS['history_max'] = n
        persisted = save_settings()
        history_prune()
        return {'ok': True, 'persisted': persisted, 'history_max': n}
    if 'data_dir' in body:
        p = valid_data_dir(str(body.get('data_dir') or ''))
        SETTINGS['data_dir'] = p
        persisted = save_settings()
        configure_data_dir(p)
        migrate_history()
        try:
            os.makedirs(HISTORY_DIR, exist_ok=True)
        except OSError:
            pass
        return {'ok': True, 'persisted': persisted, 'data_dir': p}
    raise ValueError(tr('e_unknown_action'))


def setup_state():
    cands = default_db_candidates()
    found = detect_db_path()
    saved = SETTINGS.get('db_path')
    if saved and foreign_path_style(saved):
        saved = None
    return {'setup': STATE.get('setup', False), 'data_dir': DATA_DIR, 'default': suggested_dir(),
            'dialog': STATE.get('dialog', True), 'platform': platform_name(),
            'db': saved or found or (cands[0][0] if cands else ''),
            'db_default': cands[0][0] if cands else '',
            'db_found': found,
            'db_options': [{'path': p, 'exists': ok} for p, ok in cands]}


def api_setup_save(body):
    body = body or {}
    p = body.get('path')
    if not isinstance(p, str) or not p.strip():
        raise ValueError(tr('e_dir_missing'))
    p = valid_data_dir(p)
    db = body.get('db')
    if isinstance(db, str) and db.strip():
        db = valid_db_file(db)
    else:
        db = SETTINGS.get('db_path') or detect_db_path() or (default_db_candidates()[0][0] if default_db_candidates() else '')
    SETTINGS['data_dir'] = p
    SETTINGS['db_path'] = db
    persisted = save_settings()
    configure_data_dir(p)
    migrate_history()
    try:
        os.makedirs(HISTORY_DIR, exist_ok=True)
    except OSError:
        pass
    STATE['setup'] = False
    STATE['src'] = db
    if db:
        STATE['loading'] = True
        threading.Thread(target=_load_db, args=(db,), daemon=True).start()
    return {'ok': True, 'data_dir': p, 'db': db, 'persisted': persisted}


def backups_dir():
    d = os.path.join(DATA_DIR, 'backups')
    os.makedirs(d, exist_ok=True)
    return d


def backups_index_path():
    return os.path.join(backups_dir(), 'index.json')


def backups_load():
    try:
        with open(backups_index_path(), encoding='utf-8') as f:
            d = json.load(f)
        return d if isinstance(d, list) else []
    except (OSError, ValueError):
        return []


def backups_save(recs):
    p = backups_index_path()
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(recs, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def api_backup(body):
    if STATE['con'] is None:
        raise ValueError(tr('e_no_db'))
    stamp = time.strftime('%Y-%m-%d_%H-%M-%S')
    rid = time.strftime('%Y%m%d-%H%M%S')
    path = os.path.join(backups_dir(), f'jellyfin-{stamp}.db')
    n = 1
    while os.path.exists(path):
        n += 1
        path = os.path.join(backups_dir(), f'jellyfin-{stamp}-{n}.db')
        rid = time.strftime('%Y%m%d-%H%M%S') + '-' + str(n)
    with LOCK:
        job_set('backup', 0, 1)
        w = sqlite3.connect(path)
        try:
            def _bp(status, remaining, total_pages):
                job_set('backup', (total_pages - remaining) if total_pages else None, total_pages)
            STATE['con'].backup(w, pages=2048, progress=_bp)
        finally:
            w.close()
    job_set('done', 1, 1)
    rec = {'id': rid, 'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'ver': str((body or {}).get('ver') or '').strip(),
           'size': os.path.getsize(path), 'file': os.path.basename(path)}
    backups_save([rec] + backups_load())
    return {'ok': True, 'path': path, **rec}


def api_backups(params):
    recs = backups_load()
    rid = params.get('id', [''])[0]
    if not rid:
        return {'records': [{**r, 'exists': os.path.exists(os.path.join(backups_dir(), r.get('file') or ''))}
                            for r in recs]}
    rec = next((r for r in recs if r.get('id') == rid), None)
    if not rec:
        raise ValueError(tr('e_backup_missing'))
    path = os.path.join(backups_dir(), rec.get('file') or '')
    if not os.path.exists(path):
        raise ValueError(tr('e_backup_file_missing'))
    if STATE['con'] is None:
        raise ValueError(tr('e_no_db'))
    b_ids = db_ids(path)
    cur_ids = work_ids()
    in_backup = sorted(b_ids - cur_ids)
    in_cur = sorted(cur_ids - b_ids)
    out = dict(rec)
    out['items_backup'] = db_rows(path, in_backup)[:1000]
    out['items_current'] = db_rows(STATE['work'], in_cur)[:1000]
    out['added'] = len(in_backup)
    out['removed'] = len(in_cur)
    return out


def api_backups_post(body):
    body = body or {}
    action = body.get('action')
    rid = body.get('id')
    recs = backups_load()
    if action == 'delete':
        rec = next((r for r in recs if r.get('id') == rid), None)
        if not rec:
            raise ValueError(tr('e_backup_missing'))
        path = os.path.join(backups_dir(), rec.get('file') or '')
        try:
            os.remove(path)
        except OSError:
            pass
        backups_save([r for r in recs if r.get('id') != rid])
        return {'ok': True, 'deleted': rid, 'path': path}
    raise ValueError(tr('e_unknown_action'))


def api_job():
    return STATE.get('job') or {}


def api_revert(body):
    """Przywraca bazę z wpisu historii — podmiana oryginału jak przy Uploadzie."""
    body = body or {}
    rid = body.get('id')
    rec = next((r for r in history_load() if r.get('id') == rid), None) if isinstance(rid, str) else None
    if not rec:
        raise ValueError(tr('e_history_missing'))
    hist = history_file(rec)
    if not os.path.exists(hist):
        raise ValueError(tr('e_history_file_missing'))
    if STATE['kind'] == 'upload':
        raise ValueError(tr('e_upload_mode'))
    src = STATE['src']
    if CFG['service_check'] and shutil.which('systemctl'):
        if subprocess.run(['systemctl', 'is-active', '--quiet', 'jellyfin'],
                          stderr=subprocess.DEVNULL).returncode == 0:
            raise RuntimeError(tr('e_jf_running_unit'))
    if CFG['service_check']:
        st = jf_detect()
        if st['state'] == 'running':
            raise RuntimeError(tr('e_jf_running_port', port=st['port'], ver=st['info']['Version']))
    folder = os.path.dirname(os.path.abspath(src))
    writable = IS_ROOT or (os.access(src, os.W_OK) and os.access(folder, os.W_OK))
    if not writable and not priv_alive():
        raise NeedAdmin(tr('e_write_src', src=src))
    st = fs_stat_many([src])[0]
    if not st['e']:
        raise RuntimeError(tr('e_read_src', src=src))

    c = ro_connect(hist)
    try:
        res = c.execute('PRAGMA quick_check').fetchone()[0]
    finally:
        c.close()
    if res != 'ok':
        raise RuntimeError(tr('e_quickcheck', res=str(res)))

    missing = schema_missing(STATE['orig'], hist)
    if missing and not body.get('force_schema'):
        raise SchemaWarning(tr('e_schema_blocked', tables=', '.join(missing)), missing)

    scratch = tempfile.mkdtemp(prefix='jfup_', dir=work_tmp())
    backup = None
    try:
        if body.get('backup'):
            backup = free_backup_name(src)
            tb = os.path.join(scratch, 'backup.db')
            copy_from_protected(src, tb)
            install_file(tb, backup, st)
        install_file(hist, src, st)        # atomowa podmiana (zapis obok + rename)
        for suf in ('-wal', '-shm'):       # stare pliki WAL/SHM nie mogą zostać przy nowej bazie
            remove_file(src + suf)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    with LOCK:
        open_copy(src)
    return {'ok': True, 'id': rid, 'backup': backup}


def sql_job(phase=None, done=None, total=None, msg=None):
    j = STATE.get('sqljob') or {}
    if phase:
        j['phase'] = phase
    if done is not None:
        j['done'] = done
    if total is not None:
        j['total'] = total
    if msg is not None:
        j['msg'] = msg
    STATE['sqljob'] = j
    return j


def clean_err(s):
    s = ''.join(ch if (' ' <= ch <= '~' or ch in '\n\t') else ' ' for ch in (s or ''))
    lines = [l.strip() for l in s.splitlines() if l.strip()]
    return '\n'.join(lines)[-600:]


def build_sql_db(sqlpath, dbpath):
    """Odtwarza bazę z dumpu SQL: sqlite3 CLI gdy jest, inaczej strumieniowo w Pythonie."""
    total = max(1, os.path.getsize(sqlpath))
    exe = shutil.which('sqlite3')
    if exe:
        sql_job('import', 0, total)
        with open(sqlpath, 'rb') as inp:
            r = subprocess.run([exe, dbpath], stdin=inp, capture_output=True, timeout=7200)
        if r.returncode != 0:
            err = clean_err((r.stderr or b'').decode('utf-8', 'replace'))
            raise RuntimeError(tr('e_sql_failed', err=err or 'sqlite3'))
        sql_job('import', total, total)
        return
    con = sqlite3.connect(dbpath, isolation_level=None)
    done = 0
    last = 0
    buf = ''
    try:
        with open(sqlpath, encoding='utf-8', errors='replace') as f:
            for line in f:
                done += len(line)
                buf += line
                if sqlite3.complete_statement(buf):
                    con.execute(buf)
                    buf = ''
                    if done - last > (1 << 20):
                        sql_job('import', done, total)
                        last = done
        if buf.strip():
            con.execute(buf)
        con.commit()
    except sqlite3.Error as e:
        raise RuntimeError(tr('e_sql_failed', err=clean_err(str(e))))
    finally:
        con.close()
    sql_job('import', total, total)


def api_import_sql(h, n):
    name = unquote(h.headers.get('X-Filename') or 'import.sql')
    work = work_tmp()
    raw = os.path.join(work, 'import_%s.bin' % secrets.token_hex(4))
    sql = raw
    db = os.path.join(work, 'import_%s.db' % secrets.token_hex(4))
    try:
        sql_job('upload', 0, max(1, n), name)
        with open(raw, 'wb') as f:
            left = n
            done = 0
            try:
                h.connection.settimeout(30)
            except OSError:
                pass
            try:
                while left > 0:
                    chunk = h.rfile.read(min(1 << 20, left))
                    if not chunk:
                        break
                    f.write(chunk)
                    left -= len(chunk)
                    done += len(chunk)
                    sql_job('upload', done, max(1, n))
            except (socket.timeout, TimeoutError):
                raise ValueError(tr('e_upload_timeout'))
        with open(raw, 'rb') as f:
            magic = f.read(16)
        if magic.startswith(b'SQLite format 3'):
            raise ValueError(tr('e_sql_is_db'))
        with open(raw, 'rb') as f:
            probe = f.read(4096)
        if b'\x00' in probe:
            raise ValueError(tr('e_not_sql'))
        if magic[:2] == b'\x1f\x8b' or name.lower().endswith('.gz'):
            total = max(1, os.path.getsize(raw))
            sql = raw + '.sql'
            done = 0
            with gzip.open(raw, 'rb') as src, open(sql, 'wb') as dst:
                while True:
                    b = src.read(1 << 20)
                    if not b:
                        break
                    dst.write(b)
                    done += len(b)
                    sql_job('unzip', min(done, total), total)
        if os.path.exists(db):
            os.remove(db)
        build_sql_db(sql, db)
        c = sqlite3.connect(db)
        try:
            c.execute('SELECT 1 FROM BaseItems LIMIT 1')
        except sqlite3.OperationalError:
            raise RuntimeError(tr('e_sql_no_base'))
        finally:
            c.close()
        with LOCK:
            open_copy(db, 'upload', name)
        sql_job('done', 1, 1, name)
        return {'ok': True, 'label': name}
    except Exception as e:
        sql_job('error', 0, 0, str(e))
        raise
    finally:
        for p in {raw, sql, db, db + '-wal', db + '-shm'}:
            try:
                os.remove(p)
            except OSError:
                pass


def serve_export_sql(h, params):
    gz = params.get('gz', [''])[0] == '1'
    stamp = time.strftime('%Y-%m-%d_%H-%M-%S')
    suffix = '.sql.gz' if gz else '.sql'
    fd, tmpf = tempfile.mkstemp(prefix='jfsql_', suffix=suffix, dir=work_tmp())
    os.close(fd)
    try:
        src = sqlite3.connect(STATE['work'])
        try:
            fh = gzip.open(tmpf, 'wt', encoding='utf-8', newline='\n') if gz else open(tmpf, 'w', encoding='utf-8', newline='\n')
            try:
                for line in src.iterdump():
                    fh.write(line)
                    fh.write('\n')
            finally:
                fh.close()
        finally:
            src.close()
        size = os.path.getsize(tmpf)
        h.send_response(200)
        h.send_header('Content-Type', 'application/gzip' if gz else 'text/plain; charset=utf-8')
        h.send_header('Content-Length', str(size))
        h.send_header('Content-Disposition',
                      f'attachment; filename="jellyfin-{stamp}{suffix}"')
        h.end_headers()
        with open(tmpf, 'rb') as f:
            shutil.copyfileobj(f, h.wfile, 1 << 20)
    finally:
        try:
            os.remove(tmpf)
        except OSError:
            pass


def default_db_candidates():
    """Typowe lokalizacje jellyfin.db (platforma + kontener + folder programu)."""
    cands = []

    def add(p):
        if not p:
            return
        ap = os.path.abspath(os.path.expanduser(p))
        if ap not in [c[0] for c in cands]:
            cands.append((ap, os.path.isfile(ap)))

    if os.name == 'nt':
        for env, rest in ((os.environ.get('ProgramData'), ('Jellyfin', 'Server', 'data')),
                          (os.environ.get('LOCALAPPDATA'), ('jellyfin', 'data')),
                          (os.environ.get('APPDATA'), ('Jellyfin', 'Server', 'data'))):
            if env:
                add(os.path.join(env, *rest, 'jellyfin.db'))
    else:
        add('/var/lib/jellyfin/data/jellyfin.db')
        add('/config/data/jellyfin.db')          # Docker (linuxserver)
        add('/data/jellyfin.db')
        add(os.path.expanduser('~/jellyfin/data/jellyfin.db'))
    add(os.path.join(DATA_DIR, 'jellyfin.db'))
    return cands


def detect_db_path():
    for p, ok in default_db_candidates():
        if ok:
            return p
    return None


def resolve_db_path(cli_path=None):
    if cli_path:
        if foreign_path_style(cli_path):
            print(f'Pomijam --db w formacie innego systemu: {cli_path}')
            cands = default_db_candidates()
            return cands[0][0] if cands else ''
        return cli_path
    saved = SETTINGS.get('db_path')
    if saved and not foreign_path_style(saved):
        return saved
    return detect_db_path() or (default_db_candidates()[0][0] if default_db_candidates() else '')


def foreign_path_style(p):
    """Ścieżka absolutna w stylu innego systemu (np. /... na Windows, C:\\... na Linuksie)."""
    if os.name == 'nt':
        return p.startswith('/') and not p.startswith('//')
    return len(p) >= 3 and p[1] == ':' and p[2] in '\\/'


def valid_db_file(path):
    raw = os.path.expanduser((path or '').strip())
    if foreign_path_style(raw):
        raise ValueError(tr('e_path_style'))
    p = os.path.abspath(raw)
    if not p or not os.path.isfile(p):
        raise ValueError(tr('e_db_missing', path=p or '(pusta)'))
    try:
        with open(p, 'rb') as f:
            hdr = f.read(16)
    except PermissionError:
        return p          # plik istnieje, ale odczyt wymaga ADMIN — zostaw ścieżkę
    except OSError:
        raise ValueError(tr('e_db_missing', path=p))
    if hdr != b'SQLite format 3\x00':
        raise ValueError(tr('e_not_sqlite'))
    try:
        con = ro_connect(p)
        try:
            con.execute('SELECT 1 FROM BaseItems LIMIT 1')
        finally:
            con.close()
    except sqlite3.Error:
        raise ValueError(tr('e_not_jellyfin_db'))
    return p


def api_pick_path():
    path = pick_db_dialog()
    if not path:
        raise ValueError(tr('e_pick_cancelled'))
    return {'path': os.path.abspath(path)}


def api_open(path):
    path = os.path.expanduser((path or '').strip())
    if not path:
        raise ValueError(tr('e_empty_path'))
    if foreign_path_style(path):
        raise ValueError(tr('e_path_style'))
    inf = fs_stat_many([path])[0]
    if inf['e'] is False or (inf['e'] and inf['d']):
        raise ValueError(tr('e_file_notfound', path=path))
    open_copy(os.path.abspath(path))     # brak uprawnień -> NeedAdmin
    return {'ok': True, 'src': STATE['src']}


def serve_export(h):
    stamp = time.strftime('%Y-%m-%d_%H-%M-%S')
    fd, tmpf = tempfile.mkstemp(prefix='jfexp_', suffix='.db', dir=work_tmp())
    os.close(fd)
    try:
        with LOCK:
            w = sqlite3.connect(tmpf)
            STATE['con'].backup(w)
            w.close()
        size = os.path.getsize(tmpf)
        h.send_response(200)
        h.send_header('Content-Type', 'application/octet-stream')
        h.send_header('Content-Length', str(size))
        h.send_header('Content-Disposition', f'attachment; filename="jellyfin-kopia-robocza_{stamp}.db"')
        h.end_headers()
        with open(tmpf, 'rb') as f:
            shutil.copyfileobj(f, h.wfile, 1 << 20)
    finally:
        os.remove(tmpf)


def serve_image(h, params):
    iid = params.get('id', [''])[0]
    rows = q('SELECT Path FROM BaseItemImageInfos WHERE Id = ?', (iid,))
    data = read_protected(rows[0]['Path']) if rows else None
    if data is None:
        h.send_error(404)
        return
    ctype = mimetypes.guess_type(rows[0]['Path'])[0] or 'image/jpeg'
    h.send_response(200)
    h.send_header('Content-Type', ctype)
    h.send_header('Content-Length', str(len(data)))
    h.send_header('Cache-Control', 'max-age=300')
    h.end_headers()
    h.wfile.write(data)


def _set_lang(headers):
    set_lang(headers.get('X-Lang'))


def host_ok(value):
    """Dozwolone Host: localhost, adresy IP (LAN) i dokładnie --host. Blokuje domeny (DNS rebinding)."""
    h = (value or '').strip()
    if not h:
        return False
    if h.startswith('['):
        end = h.find(']')
        host = h[1:end] if end > 0 else h
    elif h.count(':') == 1:
        host = h.rsplit(':', 1)[0]
    else:
        host = h
    host = host.lower().rstrip('.')
    if host in ('localhost', '127.0.0.1', '::1'):
        return True
    if host == (CFG.get('own_host') or '').lower():
        return True
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def page_html():
    return (html_template().replace('__TOKEN__', CFG['token'])
                .replace('__I18N__', json.dumps(TEXT, ensure_ascii=False))
                .replace('__LANGS__', json.dumps(list(LANGS)))
                .replace('__LANGNAMES__', json.dumps(LANG_NAMES, ensure_ascii=False)))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send_json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        _set_lang(self.headers)
        if not host_ok(self.headers.get('Host')):
            self.send_json({'error': tr('e_bad_host')}, 403)
            return
        u = urlparse(self.path)
        try:
            if u.path not in ('/api/delete', '/api/upload', '/api/reload', '/api/open', '/api/load', '/api/jellyfin',
                              '/api/priv', '/api/service', '/api/pick', '/api/settings', '/api/history', '/api/revert',
                              '/api/setup', '/api/pickdir', '/api/import-sql', '/api/backup', '/api/backups', '/api/pickpath',
                              '/api/export', '/api/export-sql', '/api/orphans'):
                self.send_error(404)
                return
            if u.path in ('/api/export', '/api/export-sql'):
                # Pobieranie przez formularz POST: token nie trafia do URL/historii przeglądarki.
                n = int(self.headers.get('Content-Length') or 0)
                form = parse_qs((self.rfile.read(n) if n else b'').decode('utf-8', 'replace'))
                token = self.headers.get('X-Token') or (form.get('t') or [''])[0]
                if token != CFG['token']:
                    self.send_json({'error': tr('e_bad_token')}, 403)
                    return
                if STATE['con'] is None:
                    self.send_json({'error': tr('e_no_db'), 'nodb': True, 'loading': STATE.get('loading', False)}, 409)
                    return
                if u.path == '/api/export':
                    serve_export(self)
                else:
                    serve_export_sql(self, form)
                return
            if self.headers.get('X-Token') != CFG['token']:
                self.send_json({'error': tr('e_bad_token')}, 403)
                return
            if STATE['con'] is None and u.path not in NODB_OK:
                self.send_json({'error': tr('e_no_db'), 'nodb': True, 'loading': STATE.get('loading', False)}, 409)
                return
            n = int(self.headers.get('Content-Length') or 0)
            if u.path == '/api/load':  # plik bazy z komputera (surowe bajty)
                fd, path = tempfile.mkstemp(prefix='jfup_', suffix='.db', dir=work_tmp())
                try:
                    with os.fdopen(fd, 'wb') as f:
                        left = n
                        try:
                            self.connection.settimeout(30)
                        except OSError:
                            pass
                        try:
                            while left > 0:
                                chunk = self.rfile.read(min(1 << 20, left))
                                if not chunk:
                                    break
                                f.write(chunk)
                                left -= len(chunk)
                        except (socket.timeout, TimeoutError):
                            raise ValueError(tr('e_upload_timeout'))
                    with open(path, 'rb') as f:
                        if f.read(16) != b'SQLite format 3\x00':
                            raise ValueError(tr('e_not_sqlite'))
                    name = unquote(self.headers.get('X-Filename') or 'baza.db')
                    with LOCK:
                        open_copy(path, 'upload', name)
                finally:
                    os.remove(path)
                self.send_json({'ok': True, 'label': STATE['label']})
                return
            if u.path == '/api/import-sql':  # dump SQL z komputera (surowe bajty)
                self.send_json(api_import_sql(self, n))
                return
            body = json.loads(self.rfile.read(n) or b'{}')
            if u.path == '/api/delete':
                self.send_json(api_delete(body.get('ids'), bool(body.get('force'))))
            elif u.path == '/api/upload':
                self.send_json(api_upload(bool(body.get('backup')), str(body.get('ver') or ''),
                                          bool(body.get('force_schema'))))
            elif u.path == '/api/jellyfin':
                self.send_json(api_jellyfin(body))
            elif u.path == '/api/priv':
                self.send_json(api_priv(body))
            elif u.path == '/api/service':
                self.send_json(api_service(body))
            elif u.path == '/api/open':
                with LOCK:
                    self.send_json(api_open(body.get('path')))
            elif u.path == '/api/pick':
                with LOCK:
                    self.send_json(api_pick())
            elif u.path == '/api/settings':
                self.send_json(api_settings(body))
            elif u.path == '/api/history':
                self.send_json(api_history_post(body))
            elif u.path == '/api/revert':
                self.send_json(api_revert(body))
            elif u.path == '/api/setup':
                self.send_json(api_setup_save(body))
            elif u.path == '/api/pickdir':
                self.send_json(api_pickdir())
            elif u.path == '/api/pickpath':
                self.send_json(api_pick_path())
            elif u.path == '/api/backup':
                self.send_json(api_backup(body))
            elif u.path == '/api/backups':
                self.send_json(api_backups_post(body))
            elif u.path == '/api/orphans':
                self.send_json(api_orphans(bool(body.get('clean'))))
            else:
                with LOCK:
                    if STATE['kind'] == 'upload' and STATE['con'] is not None:
                        reset_work()
                    else:
                        open_copy(STATE['src'])
                self.send_json({'ok': True})
        except NeedAdmin as e:
            self.send_json({'error': str(e), 'need_admin': True}, 403)
        except SchemaWarning as e:
            self.send_json({'error': str(e), 'schema': True, 'schema_missing': getattr(e, 'missing', [])}, 409)
        except (ValueError, RuntimeError, sqlite3.Error, OSError) as e:
            self.send_json({'error': str(e)}, 400)
        except Exception as e:
            self.send_json({'error': repr(e)}, 500)

    def do_GET(self):
        _set_lang(self.headers)
        if not host_ok(self.headers.get('Host')):
            self.send_json({'error': tr('e_bad_host')}, 403)
            return
        u = urlparse(self.path)
        p = parse_qs(u.query)
        try:
            if STATE['con'] is None and u.path not in NODB_OK:
                self.send_json({'error': tr('e_no_db'), 'nodb': True, 'loading': STATE.get('loading', False)}, 409)
                return
            if u.path == '/':
                data = page_html().encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            elif u.path == '/api/info':
                self.send_json({'src': STATE['src'], 'dirty': STATE['dirty'], 'kind': STATE['kind'], 'label': STATE['label'],
                                'nodb': STATE['con'] is None,
                                'platform': platform_name(),
                                'nodb_reason': (tr(STATE['nodb_reason_key'], **STATE.get('nodb_reason_args', {}))
                                                if STATE.get('nodb_reason_key') else STATE['nodb_reason']),
                                'loading': STATE.get('loading', False), 'setup': STATE.get('setup', False),
                                'dialog': STATE.get('dialog', True)})
            elif u.path == '/api/setup':
                self.send_json(setup_state())
            elif u.path == '/api/types':
                self.send_json(api_types())
            elif u.path == '/api/list':
                self.send_json(api_list(p))
            elif u.path == '/api/tree':
                self.send_json(api_tree(p))
            elif u.path == '/api/problems':
                self.send_json(api_problems(p))
            elif u.path == '/api/disks':
                self.send_json(api_disks(p))
            elif u.path == '/api/history':
                self.send_json(api_history(p))
            elif u.path == '/api/jellyfin':
                if p.get('refresh') or JF['state'] == 'unknown':
                    JF.update(jf_detect())
                self.send_json(JF)
            elif u.path == '/api/priv':
                self.send_json(priv_state())
            elif u.path == '/api/service':
                sv = svc_detect()
                self.send_json({'kind': sv['kind'], 'name': sv['name'], 'source': sv['source']})
            elif u.path == '/api/export':
                if p.get('t', [''])[0] != CFG['token']:
                    self.send_json({'error': tr('e_bad_token')}, 403)
                else:
                    serve_export(self)
            elif u.path == '/api/export-sql':
                if p.get('t', [''])[0] != CFG['token']:
                    self.send_json({'error': tr('e_bad_token')}, 403)
                else:
                    serve_export_sql(self, p)
            elif u.path == '/api/sqljob':
                self.send_json(STATE.get('sqljob') or {})
            elif u.path == '/api/job':
                self.send_json(api_job())
            elif u.path == '/api/backups':
                self.send_json(api_backups(p))
            elif u.path == '/api/orphans':
                self.send_json(api_orphans())
            elif u.path == '/img':
                serve_image(self, p)
            else:
                self.send_error(404)
        except Exception as e:  # log po stronie serwera, klient dostaje ogólny komunikat
            print(f'GET {u.path}: {e!r}', file=sys.stderr)
            try:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(tr('e_internal').encode('utf-8'))
            except OSError:
                pass


def html_path():
    base = getattr(sys, '_MEIPASS', app_dir())
    return os.path.join(base, 'ui', 'index.html')


_HTML_CACHE = None


def html_template():
    global _HTML_CACHE
    if _HTML_CACHE is None:
        with open(html_path(), encoding='utf-8') as f:
            _HTML_CACHE = f.read()
    return _HTML_CACHE




PICK_CODE = r"""
print('__NOGUI__')
import tkinter as tk
from tkinter import filedialog
try:
    root = tk.Tk()
except Exception:
    raise SystemExit(0)
root.withdraw()
try:
    root.attributes('-topmost', True)
except Exception:
    pass
p = filedialog.askopenfilename(title='jellyfin.db',
                               filetypes=[('SQLite / Jellyfin', '*.db'), ('*', '*')])
root.destroy()
print(p or '')
"""


def _gui_subprocess_flags():
    """Na Windows ukrywa okno konsoli towarzyszące procesowi z oknem Tk."""
    return {'creationflags': 0x08000000} if os.name == 'nt' else {}


def pick_db_dialog():
    """Systemowe okno wyboru pliku (osobny proces, żeby nie blokować serwera)."""
    try:
        r = subprocess.run([sys.executable, '-c', PICK_CODE], capture_output=True, text=True,
                           timeout=300, **_gui_subprocess_flags())
    except (OSError, subprocess.SubprocessError):
        raise RuntimeError(tr('e_tk_missing'))
    out = [x for x in (r.stdout or '').splitlines() if x.strip() and x.strip() != '__NOGUI__']
    if '__NOGUI__' in (r.stdout or ''):
        raise RuntimeError(tr('e_tk_missing'))
    return out[-1] if out else ''


def api_pick():
    path = pick_db_dialog()
    if not path:
        raise ValueError(tr('e_pick_cancelled'))
    open_copy(os.path.abspath(path))
    return {'ok': True, 'src': STATE['src']}


PICK_DIR_CODE = r"""
print('__NOGUI__')
import tkinter as tk
from tkinter import filedialog
try:
    root = tk.Tk()
except Exception:
    raise SystemExit(0)
root.withdraw()
try:
    root.attributes('-topmost', True)
except Exception:
    pass
p = filedialog.askdirectory(title='Folder danych')
root.destroy()
print(p or '')
"""


def pick_dir_dialog():
    try:
        r = subprocess.run([sys.executable, '-c', PICK_DIR_CODE], capture_output=True, text=True,
                           timeout=300, **_gui_subprocess_flags())
    except (OSError, subprocess.SubprocessError):
        raise RuntimeError(tr('e_tk_missing'))
    if '__NOGUI__' in (r.stdout or ''):
        raise RuntimeError(tr('e_tk_missing'))
    out = [x for x in (r.stdout or '').splitlines() if x.strip()]
    return out[-1] if out else ''


def api_pickdir():
    path = pick_dir_dialog()
    if not path:
        raise ValueError(tr('e_pick_cancelled'))
    return {'path': os.path.abspath(path)}


def open_ui(url):
    """Otwiera przeglądarkę GRAFICZNĄ przez xdg-open (nigdy tekstowej w3m/lynx - ta nie obsłuży interfejsu).
    Pod sudo uruchamia ją jako zwykły użytkownik. Gdy się nie da, tylko wypisuje adres."""
    disp, wayl = os.environ.get('DISPLAY'), os.environ.get('WAYLAND_DISPLAY')
    if not (disp or wayl) or not shutil.which('xdg-open'):
        print(f'Otwórz ręcznie w przeglądarce: {url}')
        return
    cmd = ['xdg-open', url]
    user = os.environ.get('SUDO_USER')
    try:
        if user and os.geteuid() == 0:
            import pwd
            uid = pwd.getpwnam(user).pw_uid
            env = [f'XDG_RUNTIME_DIR=/run/user/{uid}',
                   f'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus']
            if disp:
                env.append(f'DISPLAY={disp}')
                xa = os.path.join(pwd.getpwnam(user).pw_dir, '.Xauthority')
                if os.path.exists(xa):
                    env.append(f'XAUTHORITY={xa}')
            if wayl:
                env.append(f'WAYLAND_DISPLAY={wayl}')
            cmd = ['sudo', '-u', user, 'env'] + env + cmd
        subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except (OSError, KeyError):
        print(f'Otwórz ręcznie w przeglądarce: {url}')


def startup_db(path):
    """Start bez wczytanej bazy jest dozwolony: interfejs pozwoli włączyć tryb ADMIN albo wskazać plik."""
    STATE['src'] = path
    try:
        open_copy(path)
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as e:
        STATE['nodb_reason'] = str(e)
        STATE['nodb_reason_key'] = getattr(e, 'key', None) if isinstance(e, DbError) else None
        STATE['nodb_reason_args'] = getattr(e, 'kw', {}) if isinstance(e, DbError) else {}
        print(f'Nie wczytano bazy: {e}\nOtwórz program w przeglądarce: włącz tryb ADMIN albo wskaż inny plik.')


def _load_db(path):
    try:
        with LOCK:
            startup_db(path)
    finally:
        STATE['loading'] = False


def cleanup_session():
    """Zamyka bazę i usuwa kopie robocze z katalogu tmp (idempotentne)."""
    priv_disable()
    con, tmp = STATE['con'], STATE['tmp']
    STATE.update(con=None, tmp=None)
    if con:
        try:
            con.close()
        except sqlite3.Error:
            pass
    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)
    try:
        os.rmdir(TMP_DIR)
    except OSError:
        pass


def _on_signal(signum, frame):
    raise SystemExit(0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=None,
                    help='ścieżka bazy (domyślnie: zapisana w configu lub automatycznie wykryta)')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=8099)
    ap.add_argument('--no-browser', action='store_true')
    ap.add_argument('--jf-service', help='usługa Jellyfina, np. systemd:jellyfin albo docker:nazwa_kontenera')
    ap.add_argument('--jf-port', type=int, help='port HTTP Jellyfina (domyślnie: z network.xml albo 8096)')
    ap.add_argument('--no-service-check', action='store_true',
                    help='nie blokuj Upload, gdy Jellyfin działa')
    a = ap.parse_args()
    STATE['dialog'] = dialog_available()
    try:
        html_template()
    except OSError as e:
        raise SystemExit(f'Nie można wczytać interfejsu ({html_path()}): {e}')
    CFG['service_check'] = not a.no_service_check
    load_settings()
    chosen = init_data_dir()
    if chosen:
        stale = cleanup_stale_sessions()
        if stale:
            print(f'Usunięto starych plików tymczasowych: {stale}')
    history_prune()
    history_verify()
    if a.jf_port:
        SETTINGS['jf_port'] = a.jf_port  # tylko na tę sesję, bez zapisu
    if a.jf_service:
        SETTINGS['jf_service'] = a.jf_service
    db_path = resolve_db_path(a.db)
    STATE['src'] = db_path
    if chosen and db_path:
        STATE['loading'] = True
        threading.Thread(target=_load_db, args=(db_path,), daemon=True).start()
    else:
        STATE['loading'] = False
    threading.Thread(target=_watchdog, daemon=True).start()
    import atexit
    atexit.register(cleanup_session)
    for name in ('SIGINT', 'SIGTERM', 'SIGHUP'):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), _on_signal)
    srv = None
    for port in range(a.port, a.port + 10):
        try:
            srv = ThreadingHTTPServer((a.host, port), Handler)
            break
        except OSError:
            continue
    if srv is None:
        raise SystemExit(tr('e_no_port'))
    CFG['own_port'] = srv.server_address[1]
    CFG['own_host'] = a.host
    url = f'http://{a.host}:{srv.server_address[1]}'
    print(f'Kopia bazy: {STATE["tmp"]}\nOtwórz: {url}  (Ctrl+C kończy)')
    if not a.no_browser:
        threading.Timer(0.8, lambda: open_ui(url)).start()
    try:
        srv.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        srv.server_close()
        cleanup_session()


if __name__ == '__main__':
    main()
