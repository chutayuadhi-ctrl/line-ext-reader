"""macOS/POSIX process helpers (all mocked: no Chrome, no real signals)."""

import os
import signal
import subprocess

from line_ext_msg.browser import process
from tests.helpers import make_settings


def _use_temp_pid_file(monkeypatch, tmp_path):
    target = tmp_path / "session" / "chrome.pid"
    monkeypatch.setattr(process.paths, "CHROME_PID", str(target))
    return target


def test_pid_roundtrip(monkeypatch, tmp_path):
    _use_temp_pid_file(monkeypatch, tmp_path)
    settings = make_settings()
    assert process.read_pid(settings) is None
    process.write_pid(settings, 4321)
    assert process.read_pid(settings) == 4321
    process.clear_pid(settings)
    assert process.read_pid(settings) is None


def test_read_pid_ignores_garbage(monkeypatch, tmp_path):
    target = _use_temp_pid_file(monkeypatch, tmp_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("not-a-pid", encoding="utf-8")
    assert process.read_pid(make_settings()) is None


# ---- (ก) Chrome path on macOS -------------------------------------------

MAC = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def test_find_chrome_exe_returns_mac_path(monkeypatch):
    monkeypatch.setattr(process.os.path, "isfile", lambda p: p == MAC)
    assert process.find_chrome_exe() == MAC


def test_find_chrome_exe_none_when_missing(monkeypatch):
    monkeypatch.setattr(process.os.path, "isfile", lambda p: False)
    assert process.find_chrome_exe() is None


def test_default_profile_is_mac_library(monkeypatch):
    monkeypatch.delenv("LINE_EXT_MSG_PROFILE", raising=False)
    from line_ext_msg.config.settings import Settings

    assert Settings().profile_dir == "~/Library/Application Support/line-ext-reader"
    assert "%" not in process.expand(Settings().profile_dir)


# ---- (ข) terminate uses POSIX signals, not Windows tools -----------------


def _fake_posix(monkeypatch, cmdline, alive_after_term=False):
    """Record killpg calls; ps returns cmdline; pgrep returns nothing."""
    signals = []
    runs = []

    def fake_run(cmd, **kwargs):
        runs.append(cmd)
        out = cmdline if cmd[0] == "ps" else ""
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    monkeypatch.setattr(process.subprocess, "run", fake_run)
    monkeypatch.setattr(process.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(process.os, "killpg", lambda pgid, sig: signals.append((pgid, sig)))
    monkeypatch.setattr(process, "_alive", lambda pid: alive_after_term)
    monkeypatch.setattr(process.time, "sleep", lambda s: None)
    return signals, runs


def test_terminate_sigterms_recorded_group(monkeypatch, tmp_path):
    _use_temp_pid_file(monkeypatch, tmp_path)
    settings = make_settings()
    profile = process.expand(settings.profile_dir)
    process.write_pid(settings, 111)
    signals, runs = _fake_posix(monkeypatch, f"chrome --user-data-dir={profile}")
    process.terminate_debug_chrome(settings)
    assert signals == [(111, signal.SIGTERM)]
    assert process.read_pid(settings) is None
    flat = " ".join(" ".join(c) for c in runs).lower()
    for banned in ("taskkill", "powershell"):
        assert banned not in flat


def test_terminate_escalates_to_sigkill(monkeypatch, tmp_path):
    _use_temp_pid_file(monkeypatch, tmp_path)
    settings = make_settings()
    process.write_pid(settings, 222)
    profile = process.expand(settings.profile_dir)
    signals, _ = _fake_posix(monkeypatch, f"x --user-data-dir={profile}", alive_after_term=True)
    monkeypatch.setattr(process.time, "monotonic", iter(range(0, 100)).__next__)
    process.terminate_debug_chrome(settings)
    assert signals == [(222, signal.SIGTERM), (222, signal.SIGKILL)]


def test_terminate_refuses_recycled_pid(monkeypatch, tmp_path):
    """A stale PID whose command line is some other program is never signalled."""
    _use_temp_pid_file(monkeypatch, tmp_path)
    settings = make_settings()
    process.write_pid(settings, 333)
    signals, _ = _fake_posix(monkeypatch, "/usr/bin/vim notes.txt")
    process.terminate_debug_chrome(settings)
    assert signals == []
    assert process.read_pid(settings) is None


def test_fallback_uses_pgrep_with_escaped_marker(monkeypatch, tmp_path):
    _use_temp_pid_file(monkeypatch, tmp_path)
    seen = []

    def fake_run(cmd, **kwargs):
        seen.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=f"{os.getpid()}\n555\n", stderr="")

    monkeypatch.setattr(process.subprocess, "run", fake_run)
    assert process._debug_chrome_pids("/a b/(x)") == [555]
    assert seen[0][0] == "pgrep"
    assert r"\(x\)" in seen[0][-1]
