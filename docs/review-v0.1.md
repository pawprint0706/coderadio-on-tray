# v0.1 구현 검토 보고서

- 검토 기준: `docs/considerations.md` (설계·결정 사항)
- 검토 대상: `src/coderadio_tray/` 전체 (2026-07-25 시점)
- 실행 확인: Windows 11에서 트레이 표시, 좌클릭 토글, 우클릭 팝업, 볼륨/비트레이트/종료 동작 확인됨

---

## 1. 설계 문서 대비 적합성

### 1.1 닫힌 결정(하드 제약) 이행 여부

| 결정 사항 | 상태 | 비고 |
|-----------|------|------|
| 좌클릭 = Play/Pause | ✅ 구현 | `TrayController._on_activated` → Trigger |
| 우클릭 = 커스텀 비모달 팝업 | ✅ 구현 | `Qt.Popup` + frameless, 바깥 클릭 시 닫힘 |
| Qt(PySide6) 트레이, pystray 배제 | ✅ 구현 | `QSystemTrayIcon` + `QWidget` 팝업 |
| mpv 백엔드 + IPC | ✅ 구현 | JSON IPC (Windows named pipe / Unix socket) |
| URL 하드코딩 금지, API에서 동적 해석 | ✅ 구현 | `_mount_url()`이 mounts/listen_url 파싱. API 주소 자체만 상수 |
| 단독 빌드 배포 (Python 미설치 실행) | ❌ 미착수 | PyInstaller + mpv 번들 작업 남음 |
| Linux best-effort | ⚠️ 부분 | Unix socket 경로는 있으나 미검증 |

### 1.2 아키텍처 일치

문서 §5의 App Core / Tray·Popup / Metadata / Player 분리는 그대로 반영됨.
패키지 구조도 초안(`config.py`, `metadata/`, `player/`, `ui/`)과 일치.

한 가지 어긋남: 문서 §4.4 "Qt 슬롯에서 블로킹 호출 금지"가 **지켜지지 않았다** (아래 M-1).

---

## 2. 버그 및 리스크

### 심각도 High

**H-1. 사용자 터미널을 숨겨버리는 콘솔 숨김** — `platform_win.py`

`GetConsoleWindow()`는 *부모 셸의 콘솔*도 반환한다. 사용자가 자기 PowerShell에서
`python -m coderadio_tray`를 실행하면 **사용자의 터미널 창 자체가 숨겨진다**.

```7:13:src/coderadio_tray/platform_win.py
def hide_console_window() -> None:
    """Hide the console when launched via python.exe (tray-only app)."""
    if sys.platform != "win32":
        return
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
```

수정 방향: `GetConsoleProcessList()`로 콘솔을 우리 프로세스만 쓰는지 확인 후 숨기거나,
콘솔 숨김을 아예 포기하고 `pythonw`/gui-scripts 경로만 안내.

**H-2. Windows named pipe read가 무한 블로킹 가능** — `mpv_player.py`

`_WinPipeTransport.recv()`의 `self._fp.read(n)`은 데이터가 없으면 **timeout 없이 블로킹**된다.
`_command()`의 deadline 검사는 read가 반환된 뒤에만 도달하므로, mpv가 응답을 안 주는 상황
(프로세스 hang 등)이면 UI 스레드가 lock을 쥔 채 멈춘다. 앱 전체 프리즈로 이어질 수 있다.

수정 방향: overlapped I/O 또는 read 전용 백그라운드 스레드 + 큐, 최소한 `PeekNamedPipe`로
데이터 유무를 폴링.

**H-3. 스트림 사망·오프라인 시 상태 불일치** — `app.py`, `mpv_player.py`

- 네트워크가 끊겨 mpv가 idle로 떨어져도 앱은 `_playing=True`를 유지 → UI는 "Playing"인데 무음.
- 문서 §6.4의 "`is_online == false` → 재생 중단 + 안내"가 미구현: `_on_metadata`가 에러 표시만 하고 재생은 계속 시도.
- 자동 재시도(지수 백오프)도 미구현.

수정 방향: mpv `end-file`/`idle` 이벤트 구독(이벤트 리스너 스레드), 오프라인 시 `stop()` 호출, 재연결 백오프 루프.

### 심각도 Medium

**M-1. UI 스레드에서 블로킹 IPC** — `app.py`

`toggle_playback` / `_start_playback` / `_on_volume`이 Qt 슬롯에서 mpv IPC를 동기 호출한다.
`play()`는 첫 호출 시 `start_idle()`로 **최대 5초** 대기할 수 있어 그동안 UI가 멈춘다.
문서 §4.4 지침 위반. 수정 방향: 플레이어 명령을 워커 스레드/큐로 이관.

**M-2. 더블클릭 시 토글 중복 실행** — `ui/tray.py`

Windows에서 더블클릭은 `Trigger` → `DoubleClick` 순으로 **둘 다 발화**한다.
현재 두 reason 모두 토글에 매핑되어 있어 빠르게 두 번 클릭하면 상태가 오락가락한다.
수정 방향: `DoubleClick` 제거 또는 Trigger에 짧은 지연을 두고 DoubleClick 도착 시 취소.

**M-3. 일시정지 중 비트레이트 변경 후 resume하면 이전 스트림 재생** — `app.py`

`_on_bitrate`는 `was_playing`일 때만 `_start_playback()`을 호출한다. 일시정지 상태에서
비트레이트를 바꾸면 `_stream_url`만 갱신되고, 이후 좌클릭 resume은 mpv에 로드된
**기존 비트레이트 스트림**을 이어 재생한다.
수정 방향: 일시정지 중 변경 시 pending 플래그를 두고 resume 시 새 URL로 `play()`.

**M-4. 볼륨 드래그 중 매 틱마다 디스크 쓰기 + IPC** — `app.py`, `ui/popup.py`

`valueChanged`가 슬라이더 드래그 중 연속 발화하는데 `_on_volume`이 매번 `save_config()`
(파일 쓰기)와 IPC를 수행한다. 동작은 하지만 낭비가 크다.
수정 방향: 저장은 `sliderReleased` 시점 또는 500ms 디바운스.

### 심각도 Low

| ID | 내용 | 위치 |
|----|------|------|
| L-1 | `field` import 미사용 | `config.py` |
| L-2 | `remaining` 변수 계산 후 미사용 | `mpv_player.py` `_command` |
| L-3 | `USER_AGENT` 버전 "0.1.0" 하드코딩 — `__init__.__version__`과 이중 관리 | `config.py` |
| L-4 | 앱이 `getattr(self._player, "_playing")`으로 **비공개 속성 접근** — `RadioPlayer` 프로토콜에 상태 조회가 부족한 신호. `toggle_pause()`는 정의만 되고 미사용 | `app.py` |
| L-5 | 자동 재생 시작(첫 메타데이터 수신 시)은 문서에서 결정된 적 없는 제품 동작 — 의도 확인 필요 | `app.py` `_on_metadata` |
| L-6 | 에러 발생 시 `_error`가 다음 성공 이벤트까지 남아 재생 중에도 "Error:" 표시 가능 | `app.py` `_update_ui` |
| L-7 | 팝업 위치가 트레이 geometry가 아닌 커서 기준 — 문서에서 허용했으나 키보드 호출 등에서 어긋날 수 있음 | `ui/popup.py` |
| L-8 | 단일 인스턴스 미구현 (문서 §3.4 권장) — 두 번 실행하면 mpv 2개 | 전역 |

### 안전성 확인된 것

- 백그라운드 스레드 → Qt Signal 마샬링은 올바르게 queued connection으로 처리됨
- `httpx.Client`는 요청 수준에서 스레드 세이프, 폴링 주기(15s) > 타임아웃(10s)이라 중첩 제한적
- config 로드 실패 시 기본값 폴백, 알 수 없는 키 필터링 정상
- mpv 프로세스 종료 경로(terminate → kill)와 Unix socket 파일 정리 정상
- 설정 clamp(volume 0–100, poll 5–120s) 정상

---

## 3. 진척도

문서 §13 마일스톤 기준:

| # | 마일스톤 | 진척 | 내용 |
|---|----------|------|------|
| 1 | Spike (스트림 재생 + API 파싱) | **100%** | 완료, 실동작 확인 |
| 2 | Core (Player + Metadata + Config) | **90%** | 동작함. H-2/M-1 구조 개선 여지 |
| 3 | Tray MVP (좌클릭 토글, 우클릭 팝업) | **95%** | 사용자 검증 완료. M-2 잔존 |
| 4 | Robustness (재연결·오프라인·단일 인스턴스) | **10%** | H-3, L-8 대부분 미구현 |
| 5 | Polish (아이콘 상태, bitrate, 문서) | **60%** | 2상태+에러 아이콘, bitrate 완료. Linux 문서화·README 보강 남음 |
| 6 | Standalone release (PyInstaller + mpv 번들) | **0%** | 미착수. **하드 제약이므로 릴리스 게이트** |
| 7 | Optional (핫키, OS 미디어 연동) | **0%** | 계획대로 후순위 |

기능 단위 요약:

| 영역 | 상태 |
|------|------|
| 스트림 재생 (128/64) | ✅ |
| 곡 정보 표시·폴링 | ✅ |
| 트레이 아이콘 (idle/playing/error) | ✅ |
| 좌클릭 토글 / 우클릭 팝업 | ✅ |
| 볼륨/비트레이트/설정 저장 | ✅ |
| 콘솔 숨김 | ⚠️ 동작하나 H-1 부작용 |
| 재연결·오프라인 처리 | ❌ |
| 단일 인스턴스 | ❌ |
| 단독 빌드 (exe + mpv 번들) | ❌ |
| macOS/Linux 검증 | ❌ |

---

## 4. 남은 작업 목록 (우선순위순)

### P0 — 다음 작업 권장 (안정성 버그)

1. H-1: 콘솔 숨김이 사용자 터미널을 숨기지 않도록 수정 (콘솔 소유 확인)
2. H-2: named pipe read 블로킹 해소 (이벤트 리더 스레드 도입)
3. H-3: mpv 이벤트 구독으로 재생 상태 동기화 + 오프라인 시 정지 + 재연결 백오프
4. M-1: 플레이어 명령을 UI 스레드 밖으로 이관 (H-2와 같은 리팩터링으로 해결 가능)

### P1 — 릴리스 게이트 (하드 제약)

5. PyInstaller onedir 빌드 스크립트 (windowed, mpv.exe 동봉, 리소스 경로 처리)
6. Python·mpv 없는 클린 환경 스모크 테스트
7. 단일 인스턴스 가드 (`QLocalServer`/뮤텍스)

### P2 — 품질

8. M-2: 더블클릭 중복 토글 정리
9. M-3: 일시정지 중 비트레이트 변경 처리
10. M-4: 볼륨 저장 디바운스
11. L-3/L-4: 버전 단일화, `RadioPlayer` 인터페이스에 상태 조회 추가
12. 단위 테스트 (metadata 파싱 픽스처, config clamp, URL 선택)

### P3 — 확장 (문서 §1.2)

13. macOS 검증 (메뉴바 클릭 관례, `LSUIElement`)
14. Linux 스모크 (Ubuntu 1종, best-effort)
15. 앨범 아트·다음 곡 표시, 자동 시작(로그인), 전역 핫키, SMTC/MPRIS 연동
16. 독자 아이콘 디자인 (현재는 프로그래매틱 도형)

---

## 5. 총평

MVP 범위(마일스톤 1–3)는 문서의 닫힌 결정을 충실히 따라 구현되었고 Windows 실사용 검증까지 끝났다.
현재 코드의 약점은 기능이 아니라 **장애 경로**다: IPC 블로킹(H-2), 상태 불일치(H-3), 콘솔 숨김 부작용(H-1)은
"코딩 중 하루 종일 켜두는 앱"이라는 제품 성격상 반드시 해소해야 한다.
그 다음이 하드 제약인 단독 빌드(P1)이며, 이는 릴리스의 전제 조건이다.
