from __future__ import annotations

import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


class MpvNotFoundError(RuntimeError):
    pass


class _IpcTransport:
    def send(self, data: bytes) -> None:  # pragma: no cover - protocol
        raise NotImplementedError

    def recv(self, n: int = 4096) -> bytes:  # pragma: no cover - protocol
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - protocol
        raise NotImplementedError


class _UnixSocketTransport(_IpcTransport):
    def __init__(self, path: str) -> None:
        self._sock = socket.socket(socket.AF_UNIX)
        self._sock.settimeout(1.0)
        self._sock.connect(path)

    def send(self, data: bytes) -> None:
        self._sock.sendall(data)

    def recv(self, n: int = 4096) -> bytes:
        return self._sock.recv(n)

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass


class _WinPipeTransport(_IpcTransport):
    """Named-pipe client for mpv on Windows (no AF_UNIX required)."""

    def __init__(self, path: str) -> None:
        # Python can open Win32 named pipes as files.
        self._fp = open(path, "r+b", buffering=0)

    def send(self, data: bytes) -> None:
        self._fp.write(data)
        self._fp.flush()

    def recv(self, n: int = 4096) -> bytes:
        return self._fp.read(n)

    def close(self) -> None:
        try:
            self._fp.close()
        except OSError:
            pass


class MpvPlayer:
    """Control mpv via JSON IPC (subprocess). Suitable for later bundling mpv.exe."""

    def __init__(self, mpv_path: str = "mpv", volume: int = 70) -> None:
        self._mpv_path = self._resolve_mpv(mpv_path)
        self._volume = max(0, min(100, volume))
        self._proc: subprocess.Popen[bytes] | None = None
        self._ipc_path = self._make_ipc_path()
        self._transport: _IpcTransport | None = None
        self._lock = threading.RLock()
        self._playing = False
        self._paused = False
        self._current_url = ""
        self._request_id = 0
        self._recv_buffer = b""

    @staticmethod
    def _resolve_mpv(mpv_path: str) -> str:
        candidates: list[str] = []
        if mpv_path:
            candidates.append(mpv_path)
        # Dev convenience: portable mpv checked into .tools (gitignored)
        here = Path(__file__).resolve()
        repo_tools = here.parents[3] / ".tools" / "mpv" / "extract" / ("mpv.exe" if sys.platform == "win32" else "mpv")
        candidates.append(str(repo_tools))
        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                return str(Path(candidate))
        found = shutil.which(mpv_path) or shutil.which("mpv.exe") or shutil.which("mpv")
        if not found:
            raise MpvNotFoundError(
                "mpv was not found on PATH. Install mpv for development "
                "(e.g. winget install shinchiro.mpv) or set config mpv_path."
            )
        return found

    @staticmethod
    def _make_ipc_path() -> str:
        token = uuid.uuid4().hex[:8]
        if sys.platform == "win32":
            return rf"\\.\pipe\coderadio-tray-{token}"
        return str(Path(tempfile.gettempdir()) / f"coderadio-tray-{token}.sock")

    def start_idle(self) -> None:
        with self._lock:
            if self._proc and self._proc.poll() is None:
                return
            if sys.platform != "win32" and os.path.exists(self._ipc_path):
                try:
                    os.unlink(self._ipc_path)
                except OSError:
                    pass
            cmd = [
                self._mpv_path,
                "--no-video",
                "--idle=yes",
                "--force-window=no",
                "--keep-open=no",
                "--cache=yes",
                "--no-terminal",
                "--input-media-keys=no",
                f"--title=Code Radio Tray",
                f"--volume={self._volume}",
                f"--input-ipc-server={self._ipc_path}",
                "--msg-level=all=error",
            ]
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
            self._wait_for_ipc(timeout=5.0)

    def _wait_for_ipc(self, timeout: float) -> None:
        deadline = time.time() + timeout
        last_err: Exception | None = None
        while time.time() < deadline:
            try:
                self._connect()
                return
            except OSError as exc:
                last_err = exc
                time.sleep(0.05)
        raise RuntimeError(f"mpv IPC not ready: {last_err}")

    def _connect(self) -> None:
        if self._transport is not None:
            return
        if sys.platform == "win32":
            self._transport = _WinPipeTransport(self._ipc_path)
        elif hasattr(socket, "AF_UNIX"):
            self._transport = _UnixSocketTransport(self._ipc_path)
        else:
            raise RuntimeError("No supported IPC transport for mpv on this platform")
        self._recv_buffer = b""

    def _ensure_connection(self) -> None:
        if self._proc is None or self._proc.poll() is not None:
            if self._transport is not None:
                try:
                    self._transport.close()
                except OSError:
                    pass
                self._transport = None
            self.start_idle()
            return
        if self._transport is None:
            self._connect()

    def _command(self, *args: object, timeout: float = 2.0) -> dict:
        with self._lock:
            self._ensure_connection()
            assert self._transport is not None
            self._request_id += 1
            req_id = self._request_id
            payload = {"command": list(args), "request_id": req_id}
            data = (json.dumps(payload) + "\n").encode("utf-8")
            self._transport.send(data)

            deadline = time.time() + timeout
            while time.time() < deadline:
                if b"\n" not in self._recv_buffer:
                    remaining = max(0.05, deadline - time.time())
                    # ReadFile is blocking; rely on short pipe reads
                    chunk = self._transport.recv(4096)
                    if not chunk:
                        self._transport = None
                        raise RuntimeError("mpv IPC connection closed")
                    self._recv_buffer += chunk
                while b"\n" in self._recv_buffer:
                    line, self._recv_buffer = self._recv_buffer.split(b"\n", 1)
                    if not line.strip():
                        continue
                    msg = json.loads(line.decode("utf-8"))
                    if msg.get("request_id") != req_id:
                        continue
                    if msg.get("error") not in (None, "success"):
                        raise RuntimeError(f"mpv error: {msg.get('error')}")
                    return msg
            raise TimeoutError("mpv IPC response timeout")

    def play(self, url: str) -> None:
        if not url:
            raise ValueError("empty stream url")
        with self._lock:
            self.start_idle()
            self._command("loadfile", url, "replace")
            self._command("set_property", "pause", False)
            self._command("set_property", "volume", self._volume)
            self._current_url = url
            self._playing = True
            self._paused = False

    def pause(self) -> None:
        with self._lock:
            if not self._playing:
                return
            self._command("set_property", "pause", True)
            self._paused = True

    def resume(self) -> None:
        with self._lock:
            if not self._playing:
                return
            self._command("set_property", "pause", False)
            self._paused = False

    def toggle_pause(self) -> None:
        with self._lock:
            if not self._playing:
                return
            if self._paused:
                self.resume()
            else:
                self.pause()

    def stop(self) -> None:
        with self._lock:
            try:
                if self._proc and self._proc.poll() is None and self._transport is not None:
                    self._command("stop")
            except Exception:
                logger.exception("stop failed")
            self._playing = False
            self._paused = False
            self._current_url = ""

    def set_volume(self, volume: int) -> None:
        self._volume = max(0, min(100, int(volume)))
        with self._lock:
            if self._proc and self._proc.poll() is None and self._transport is not None:
                try:
                    self._command("set_property", "volume", self._volume)
                except Exception:
                    logger.exception("set_volume failed")

    def get_volume(self) -> int:
        return self._volume

    def is_playing(self) -> bool:
        return self._playing and not self._paused

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def shutdown(self) -> None:
        with self._lock:
            transport = self._transport
            self._transport = None
            if transport is not None:
                try:
                    transport.close()
                except OSError:
                    pass
            proc = self._proc
            self._proc = None
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=2)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            if sys.platform != "win32":
                try:
                    if os.path.exists(self._ipc_path):
                        os.unlink(self._ipc_path)
                except OSError:
                    pass
            self._playing = False
            self._paused = False
