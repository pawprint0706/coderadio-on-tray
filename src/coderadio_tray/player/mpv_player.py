from __future__ import annotations

import ctypes
import json
import logging
import os
import queue
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
    def send(self, data: bytes) -> None:
        raise NotImplementedError

    def recv(self, n: int = 4096) -> bytes:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    def fileno(self) -> int:
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

    def fileno(self) -> int:
        return self._sock.fileno()


class _WinPipeTransport(_IpcTransport):
    def __init__(self, path: str) -> None:
        import msvcrt

        self._fp = open(path, "r+b", buffering=0)
        self._handle = msvcrt.get_osfhandle(self._fp.fileno())

        self._peek = ctypes.windll.kernel32.PeekNamedPipe
        self._peek.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.c_void_p,
        ]
        self._peek.restype = ctypes.c_long

    def send(self, data: bytes) -> None:
        self._fp.write(data)
        self._fp.flush()

    def recv(self, n: int = 4096) -> bytes:
        available = ctypes.c_ulong(0)
        ok = self._peek(
            self._handle, None, 0, None, ctypes.byref(available), None
        )
        if not ok or available.value == 0:
            raise BlockingIOError("no data available")
        to_read = min(n, available.value)
        return os.read(self._fp.fileno(), to_read)

    def close(self) -> None:
        try:
            self._fp.close()
        except OSError:
            pass

    def fileno(self) -> int:
        return self._fp.fileno()


class MpvPlayer:
    def __init__(self, mpv_path: str = "mpv", volume: int = 70) -> None:
        self._mpv_path = self._resolve_mpv(mpv_path)
        self._volume = max(0, min(100, volume))
        self._proc: subprocess.Popen[bytes] | None = None
        self._ipc_path = self._make_ipc_path()
        self._transport: _IpcTransport | None = None
        self._cmd_lock = threading.RLock()
        self._state_lock = threading.RLock()
        self._playing = False
        self._paused = False
        self._current_url = ""
        self._request_id = 0
        self._recv_buffer = b""

        self._cmd_queue: queue.Queue[tuple[int, bytes]] = queue.Queue()
        self._response_events: dict[int, threading.Event] = {}
        self._responses: dict[int, dict] = {}
        self._reader_running = False
        self._reader_thread: threading.Thread | None = None

        self._event_callback = None

    def set_event_callback(self, callback) -> None:
        self._event_callback = callback

    @staticmethod
    def _resolve_mpv(mpv_path: str) -> str:
        candidates: list[str] = []
        if mpv_path:
            candidates.append(mpv_path)
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
        with self._cmd_lock:
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
                creationflags = subprocess.CREATE_NO_WINDOW
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
        self._start_reader()

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

    def _start_reader(self) -> None:
        if self._reader_thread and self._reader_thread.is_alive():
            return
        self._reader_running = True
        self._reader_thread = threading.Thread(
            target=self._reader_loop, daemon=True, name="mpv-ipc-reader"
        )
        self._reader_thread.start()

    def _reader_loop(self) -> None:
        while self._reader_running:
            transport = self._transport
            if transport is None:
                time.sleep(0.05)
                continue

            try:
                _req_id, data_bytes = self._cmd_queue.get_nowait()
                transport.send(data_bytes)
            except queue.Empty:
                pass

            try:
                chunk = transport.recv(4096)
                if not chunk:
                    break
            except BlockingIOError:
                time.sleep(0.01)
                continue
            except OSError:
                break

            self._recv_buffer += chunk

            while b"\n" in self._recv_buffer:
                line, self._recv_buffer = self._recv_buffer.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue
                req_id = msg.get("request_id")
                if req_id is not None and req_id in self._response_events:
                    self._responses[req_id] = msg
                    self._response_events[req_id].set()
                elif req_id is None:
                    self._handle_event(msg)

    def _handle_event(self, msg: dict) -> None:
        event = msg.get("event", "")
        if event == "end-file":
            with self._state_lock:
                self._playing = False
                self._paused = False
                self._current_url = ""
            logger.info("mpv reported end-file")
        elif event == "file-loaded":
            with self._state_lock:
                self._playing = True
        if self._event_callback:
            self._event_callback(event, msg)

    def _command(self, *args: object, timeout: float = 5.0) -> dict:
        with self._cmd_lock:
            self._ensure_connection()
            assert self._transport is not None
            self._request_id += 1
            req_id = self._request_id
            payload = {"command": list(args), "request_id": req_id}
            data_bytes = (json.dumps(payload) + "\n").encode("utf-8")

            ev = threading.Event()
            self._response_events[req_id] = ev
            self._cmd_queue.put((req_id, data_bytes))

        ok = ev.wait(timeout=timeout)
        self._response_events.pop(req_id, None)
        msg = self._responses.pop(req_id, None)
        if not ok:
            raise TimeoutError(f"mpv IPC response timeout for {args[0] if args else '?'}")
        if msg is None:
            raise RuntimeError("mpv IPC connection closed")
        if msg.get("error") not in (None, "success"):
            raise RuntimeError(f"mpv error: {msg.get('error')}")
        return msg

    def play(self, url: str) -> None:
        if not url:
            raise ValueError("empty stream url")
        with self._cmd_lock:
            self.start_idle()
            self._command("loadfile", url, "replace")
            self._command("set_property", "pause", False)
            self._command("set_property", "volume", self._volume)
            self._current_url = url
        with self._state_lock:
            self._playing = True
            self._paused = False

    def pause(self) -> None:
        with self._state_lock:
            if not self._playing:
                return
        with self._cmd_lock:
            self._command("set_property", "pause", True)
        with self._state_lock:
            self._paused = True

    def resume(self) -> None:
        with self._state_lock:
            if not self._playing:
                return
        with self._cmd_lock:
            self._command("set_property", "pause", False)
        with self._state_lock:
            self._paused = False

    def toggle_pause(self) -> None:
        with self._state_lock:
            if not self._playing:
                return
            was_paused = self._paused
        if was_paused:
            self.resume()
        else:
            self.pause()

    def stop(self) -> None:
        with self._cmd_lock:
            try:
                if self._proc and self._proc.poll() is None and self._transport is not None:
                    self._command("stop")
            except Exception:
                logger.exception("stop failed")
        with self._state_lock:
            self._playing = False
            self._paused = False
            self._current_url = ""

    def set_volume(self, volume: int) -> None:
        self._volume = max(0, min(100, int(volume)))
        with self._cmd_lock:
            if self._proc and self._proc.poll() is None and self._transport is not None:
                try:
                    self._command("set_property", "volume", self._volume)
                except Exception:
                    logger.exception("set_volume failed")

    def get_volume(self) -> int:
        return self._volume

    def is_playing(self) -> bool:
        with self._state_lock:
            return self._playing and not self._paused

    def is_paused(self) -> bool:
        with self._state_lock:
            return self._paused

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def shutdown(self) -> None:
        self._reader_running = False
        if self._reader_thread:
            self._reader_thread.join(timeout=1)
        with self._cmd_lock:
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
        with self._state_lock:
            self._playing = False
            self._paused = False
