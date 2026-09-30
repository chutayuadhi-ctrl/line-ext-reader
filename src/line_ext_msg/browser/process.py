"""OS-level helpers: locate Chrome, expand paths, kill debug processes.

macOS/POSIX port (line-ext-reader patch). Upstream was Windows-only
(Windows tools); every platform-specific call stays in this module.
"""

import os
import re
import signal
import subprocess
import time

from ..config import paths
from ..config.settings import Settings

MAC_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def expand(path: str) -> str:
    """Expand ~ and $VAR."""
    return os.path.expandvars(os.path.expanduser(path))


def find_chrome_exe() -> str | None:
    """Return the macOS Google Chrome binary path, or None when missing."""
    candidates = [
        MAC_CHROME,
        expand("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def is_profile_locked(data_dir: str) -> bool:
    """Detect SingletonLock (profile in use by a normal window)."""
    return any(
        os.path.exists(os.path.join(data_dir, name))
        for name in ("SingletonLock", "SingletonSocket", "SingletonCookie")
    )


def profile_marker(settings: Settings) -> str:
    """Substring identifying the debug profile in a process command line."""
    return os.path.basename(expand(settings.profile_dir)) or "line-chrome-debug"


def write_pid(settings: Settings, pid: int) -> None:
    """Record the PID of the debug Chrome we just launched."""
    path = expand(paths.CHROME_PID)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(str(int(pid)))
    except OSError:
        pass  # a missing PID file only costs us the slow fallback later


def read_pid(settings: Settings) -> int | None:
    """PID recorded by write_pid, or None when absent or unreadable."""
    try:
        with open(expand(paths.CHROME_PID), encoding="utf-8") as handle:
            return int(handle.read().strip())
    except (OSError, ValueError):
        return None


def clear_pid(settings: Settings) -> None:
    """Drop the recorded PID once that Chrome is gone."""
    try:
        os.remove(expand(paths.CHROME_PID))
    except OSError:
        pass


def _cmdline_of(pid: int) -> str:
    """Command line of a PID ('' when it does not exist)."""
    try:
        done = subprocess.run(
            ["ps", "-p", str(int(pid)), "-o", "command="],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _kill_group(pid: int, grace_s: float = 2.0) -> bool:
    """SIGTERM the process group (Chrome is started with start_new_session),
    then SIGKILL if it is still alive. True when a signal was delivered."""
    try:
        pgid = os.getpgid(pid)
    except ProcessLookupError:
        return False
    except OSError:
        pgid = pid
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    except OSError:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return False
    deadline = time.monotonic() + grace_s
    while time.monotonic() < deadline and _alive(pid):
        time.sleep(0.1)
    if _alive(pid):
        try:
            os.killpg(pgid, signal.SIGKILL)
        except OSError:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    return True


def _debug_chrome_pids(marker: str) -> list[int]:
    """PIDs whose command line carries our profile dir (pgrep -f, POSIX).

    The marker is regex-escaped, so a profile path cannot inject a pattern.
    """
    try:
        out = subprocess.run(
            ["pgrep", "-f", "--", "--user-data-dir=" + re.escape(marker)],
            capture_output=True, text=True, timeout=10,
        ).stdout
    except Exception:
        return []
    pids: list[int] = []
    for line in out.splitlines():
        try:
            pid = int(line.strip())
        except (TypeError, ValueError):
            continue
        if pid != os.getpid():
            pids.append(pid)
    return pids


def terminate_debug_chrome(settings: Settings) -> None:
    """Stop ONLY the debug-profile Chrome (POSIX signals).

    Fast path: the PID recorded at launch (only if its command line still
    names our profile, so a recycled PID is never killed). Fallback: pgrep
    by --user-data-dir. Never touches the normal Chrome (other profile).
    """
    profile = expand(settings.profile_dir)
    pid = read_pid(settings)
    if pid is not None and profile in _cmdline_of(pid) and _kill_group(pid):
        clear_pid(settings)
        return
    for other in _debug_chrome_pids(profile):
        _kill_group(other)
    clear_pid(settings)
