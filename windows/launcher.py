#!/usr/bin/env python3
"""Windows launcher for Jellyfin DB Editor.

The application is a local HTTP server. This launcher starts it in a child
process and displays it in a native WebView2 window (pywebview). If WebView2 or
pywebview is unavailable, it opens the default browser and shows a small
control window so the server can still be stopped.

Internal modes:
    --server          run jf_browser.py in this process (used by the launcher)
    --pick-dialog db  run the Tk file dialog (used by the frozen app)
    --pick-dialog dir run the Tk directory dialog
"""
from __future__ import annotations

import atexit
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

APP = "jellyfin-db-editor"
SELFTEST = os.environ.get("JF_WEBVIEW_SELFTEST") == "1"
LOGF = None
LOG_PATH = None

USAGE = """Jellyfin DB Editor - local viewer and cleaner for jellyfin.db

Usage: jellyfin-db-editor [options]

Window options:
  --browser           use the default browser instead of the native window
  --no-window         server only: no window and no browser
  -h, --help          show this help
  --version           show the application version

Server options (passed through to jf_browser.py):
  --db PATH           database path (default: saved config or auto-detect)
  --host HOST         bind address (default: 127.0.0.1)
  --port PORT         port (default: automatic free port)
  --jf-service NAME   Jellyfin service, e.g. systemd:jellyfin or docker:name
  --jf-port PORT      Jellyfin HTTP port
  --no-service-check  do not block Upload while Jellyfin is running
"""


def _log_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(base) / "JellyfinDBEditor" / "logs" / "launcher.log"


def setup_streams() -> None:
    """Windowed builds have no console; write diagnostics to a UTF-8 log."""
    global LOGF, LOG_PATH
    LOG_PATH = str(_log_path())
    try:
        if LOG_PATH:
            os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        LOGF = open(LOG_PATH, "a", encoding="utf-8", buffering=1)
    except OSError:
        LOGF = None
    if LOGF is None and (sys.stdout is None or sys.stderr is None):
        try:
            sink = open(os.devnull, "w", encoding="utf-8")
        except OSError:
            sink = None
        if sys.stdout is None:
            sys.stdout = sink
        if sys.stderr is None:
            sys.stderr = sink
    if LOGF is not None and (sys.stdout is None or sys.stderr is None):
        if sys.stdout is None:
            sys.stdout = LOGF
        if sys.stderr is None:
            sys.stderr = LOGF
    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


def note(message: str) -> None:
    if sys.stdout is not None:
        print(message, flush=True)
    if LOGF is not None:
        LOGF.write(message + "\n")
        LOGF.flush()


def log_tail(lines: int = 30) -> str:
    try:
        text = Path(LOG_PATH).read_text(encoding="utf-8", errors="replace")
    except (OSError, TypeError):
        return ""
    return "\n".join(text.splitlines()[-lines:])


def show_message(text: str, title: str = "Jellyfin DB Editor", error: bool = False) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass
        if error:
            messagebox.showerror(title, text)
        else:
            messagebox.showinfo(title, text)
        root.destroy()
    except Exception:
        note(text)


def webview2_version() -> str | None:
    """Return the installed WebView2 Runtime version, or None.

    pywebview silently falls back to MSHTML/IE11 when WebView2 is missing, so
    the launcher must check before creating the window.
    """
    if os.name != "nt":
        return "non-windows"
    for env in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if not base:
            continue
        folder = Path(base) / "Microsoft" / "EdgeWebView" / "Application"
        if not folder.is_dir():
            continue
        try:
            versions = [p.name for p in folder.iterdir()
                        if (p / "msedgewebview2.exe").is_file()]
        except OSError:
            continue
        if versions:
            return sorted(versions)[-1]
    try:
        import winreg
        subkeys = (
            r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients"
            r"\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
            r"SOFTWARE\Microsoft\EdgeUpdate\Clients"
            r"\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
        )
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for subkey in subkeys:
                try:
                    with winreg.OpenKey(root, subkey) as key:
                        version, _ = winreg.QueryValueEx(key, "pv")
                    if version:
                        return str(version)
                except OSError:
                    continue
    except Exception:
        pass
    return None


def find_opt(args: list[str], name: str) -> str | None:
    for i, arg in enumerate(args):
        if arg == name and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith(name + "="):
            return arg.split("=", 1)[1]
    return None


def strip_launcher_args(args: list[str]) -> list[str]:
    out = []
    for arg in args:
        if arg in ("--browser", "--no-window", "--no-browser"):
            continue
        out.append(arg)
    return out


def start_server(core_args: list[str]):
    frozen = bool(getattr(sys, "frozen", False))
    port = find_opt(core_args, "--port")
    if port is None:
        # Let the OS pick an ephemeral loopback port. The real URL is written
        # to the URL file by the server, so a race with another process cannot
        # make the window point at a foreign listener.
        core_args = core_args + ["--port", "0"]
    url_file = Path(tempfile.gettempdir()) / f"jf-launcher-{os.getpid()}-{time.time_ns()}.url"
    quit_file = Path(tempfile.gettempdir()) / f"jf-launcher-{os.getpid()}-{time.time_ns()}.quit"
    for path in (url_file, quit_file):
        try:
            path.unlink()
        except OSError:
            pass
    env = dict(
        os.environ,
        JF_URL_FILE=str(url_file),
        JF_QUIT_FILE=str(quit_file),
        JF_LOG_FILE=LOG_PATH or "",
        PYTHONUTF8="1",
        PYTHONIOENCODING="utf-8",
        PYTHONUNBUFFERED="1",
    )
    cmd = [sys.executable]
    if not frozen:
        cmd.append(str(Path(__file__).resolve()))
    cmd += ["--server", "--no-browser"] + core_args
    creationflags = 0x08000000 if os.name == "nt" else 0
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    return proc, url_file, quit_file


def wait_server(proc: subprocess.Popen, url_file: Path, timeout: float = 45.0) -> str | None:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return None
        try:
            url = url_file.read_text(encoding="utf-8").strip()
        except OSError:
            url = ""
        if url:
            try:
                with opener.open(url + "/", timeout=1.0) as response:
                    response.read(1)
                return url
            except urllib.error.HTTPError as exc:
                if exc.code < 500:
                    return url
            except Exception:
                pass
        time.sleep(0.2)
    return None


def stop_server(proc: subprocess.Popen, quit_file: Path | None = None) -> None:
    if proc.poll() is not None:
        return
    if quit_file is not None:
        try:
            quit_file.write_text("quit\n", encoding="utf-8")
        except OSError:
            pass
        try:
            proc.wait(timeout=5)
            return
        except subprocess.TimeoutExpired:
            pass
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def run_control_window(url: str, proc: subprocess.Popen, quit_file: Path,
                       detail: str = "") -> None:
    """Browser fallback with a window that keeps the server stoppable."""
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("Jellyfin DB Editor")
    root.geometry("620x230")
    root.minsize(520, 200)

    frame = ttk.Frame(root, padding=14)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="The interface is open in your browser.",
              font=("Segoe UI", 11, "bold")).pack(anchor="w")
    if detail:
        ttk.Label(frame, text=detail, wraplength=570,
                  foreground="#666").pack(anchor="w", pady=(4, 0))

    row = ttk.Frame(frame)
    row.pack(fill="x", pady=(12, 0))
    entry = ttk.Entry(row)
    entry.insert(0, url)
    entry.configure(state="readonly")
    entry.pack(side="left", fill="x", expand=True)
    ttk.Button(row, text="Open again",
               command=lambda: webbrowser.open(url)).pack(side="left", padx=(8, 0))

    ttk.Label(frame,
              text="Closing this window stops the local server.",
              foreground="#666").pack(anchor="w", pady=(12, 0))
    ttk.Button(frame, text="Stop server",
               command=root.destroy).pack(anchor="e", pady=(10, 0))

    root.protocol("WM_DELETE_WINDOW", root.destroy)
    try:
        root.mainloop()
    finally:
        stop_server(proc, quit_file)


def run_native(url: str):
    """Return (status, detail): ok | fallback."""
    version = webview2_version()
    if version is None:
        return "fallback", ("WebView2 Runtime is not installed; "
                            "install it from https://go.microsoft.com/fwlink/p/?LinkId=2124703")
    try:
        import webview
    except Exception as exc:
        return "fallback", f"pywebview unavailable ({exc})"
    state = {
        "loaded": False,
        "closed": False,
        "edge": False,
        "ua": "",
        "title": "",
        "timeout": False,
    }
    timer = None
    try:
        try:
            webview.settings["ALLOW_DOWNLOADS"] = True
            webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] = False
        except Exception:
            pass
        storage = Path(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"))
        storage = storage / "JellyfinDBEditor" / "webview"
        try:
            storage.mkdir(parents=True, exist_ok=True)
        except OSError:
            storage = None
        kwargs = dict(width=1280, height=820, min_size=(800, 600))
        try:
            window = webview.create_window("Jellyfin DB Editor", url, **kwargs)
        except TypeError:
            window = webview.create_window("Jellyfin DB Editor", url, width=1280, height=820)
        if window is None:
            return "fallback", "pywebview did not create a window"

        def loaded():
            if state["loaded"]:
                return
            state["loaded"] = True
            try:
                state["ua"] = str(window.evaluate_js("navigator.userAgent") or "")
            except Exception:
                pass
            try:
                state["title"] = str(window.evaluate_js("document.title") or "")
            except Exception:
                pass
            ua = state["ua"]
            state["edge"] = (("Edg/" in ua) or ("Chrome/" in ua)) and (
                "Trident/" not in ua and "MSHTML" not in ua)
            if SELFTEST:
                if state["edge"]:
                    note(f"WEBVIEW_OK {ua}")
                else:
                    note(f"WEBVIEW_WRONG_ENGINE {ua or '<empty UA>'}")

                def verify():
                    try:
                        body = str(window.evaluate_js("document.body.innerText") or "")
                    except Exception as exc:
                        body = f"<evaluate failed: {exc}>"
                    state["body"] = body[:1000]
                    flat = " | ".join(line.strip() for line in body.splitlines() if line.strip())
                    note(f"WEBVIEW_BODY {flat[:500]}")
                    try:
                        window.destroy()
                    except Exception:
                        pass

                threading.Timer(2.0, verify).start()

        def closed():
            state["closed"] = True

        try:
            window.events.loaded += loaded
            window.events.closed += closed
        except Exception:
            pass

        def timed_out():
            if state["loaded"]:
                return
            state["timeout"] = True
            note("WEBVIEW_TIMEOUT")
            try:
                window.destroy()
            except Exception:
                pass

        timer = threading.Timer(20.0, timed_out)
        timer.daemon = True
        timer.start()
        webview.start(
            debug=False,
            private_mode=False,
            storage_path=str(storage) if storage else None,
        )
        timer.cancel()
        if state["timeout"]:
            return "fallback", "WebView2 did not load the page in time"
        if state["closed"] and not state["loaded"]:
            return "ok", None  # the user closed the window while loading
        if not state["loaded"]:
            return "fallback", "WebView2 window closed before the page loaded"
        if not state["edge"]:
            return "fallback", f"WebView2 used a non-Edge engine ({state['ua'] or 'unknown'})"
        note(f"WEBVIEW_OK {version} title={state['title']!r}")
        return "ok", None
    except Exception as exc:
        return "fallback", f"WebView2 failed ({exc})"
    finally:
        if timer is not None:
            timer.cancel()


def main() -> int:
    setup_streams()
    args = sys.argv[1:]

    if "--server" in args:
        args = [arg for arg in args if arg != "--server"]
        import jf_browser
        sys.argv = [sys.argv[0]] + args
        return jf_browser.main()

    if "--pick-dialog" in args:
        kind = find_opt(args, "--pick-dialog")
        if kind not in ("db", "dir"):
            note("invalid --pick-dialog value")
            return 2
        import jf_browser
        return jf_browser.run_pick_dialog(kind)

    if any(arg in ("-h", "--help") for arg in args):
        if LOGF is not None and getattr(sys, "frozen", False):
            show_message(USAGE)
        else:
            print(USAGE)
        return 0

    if "--version" in args:
        import jf_browser
        text = f"Jellyfin DB Editor {jf_browser.APP_VERSION}"
        if LOGF is not None and getattr(sys, "frozen", False):
            show_message(text)
        else:
            print(text)
        return 0

    force_browser = "--browser" in args
    no_window = "--no-window" in args or "--no-browser" in args
    core_args = strip_launcher_args(args)

    note(f"--- launch {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
    note(f"python={sys.executable} frozen={bool(getattr(sys, 'frozen', False))}")
    proc, url_file, quit_file = start_server(core_args)
    atexit.register(stop_server, proc, quit_file)
    try:
        url = wait_server(proc, url_file)
        if not url:
            note("SERVER_FAILED")
            show_message(
                "Could not start the local server.\n\n"
                + (log_tail(20) or "See launcher.log for details."),
                error=True,
            )
            return 1
        note(f"Open: {url}")

        if no_window:
            try:
                proc.wait()
            except KeyboardInterrupt:
                pass
            return 0
        if force_browser:
            try:
                webbrowser.open(url)
            except Exception as exc:
                note(f"could not open browser: {exc}")
            run_control_window(url, proc, quit_file)
            return 0

        status, detail = run_native(url)
        if status == "ok":
            return 0
        note(f"{detail}; opening the browser")
        try:
            webbrowser.open(url)
        except Exception as exc:
            note(f"could not open browser: {exc}")
        run_control_window(url, proc, quit_file, detail)
        return 0
    finally:
        stop_server(proc, quit_file)
        for path in (url_file, quit_file):
            try:
                path.unlink()
            except OSError:
                pass
        if LOGF is not None:
            LOGF.close()


if __name__ == "__main__":
    raise SystemExit(main())
