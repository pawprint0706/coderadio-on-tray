# v0.2 구현 검토 보고서

- 검토 기준: `docs/considerations.md`, `docs/review-v0.1.md`
- 검토 대상: `src/coderadio_tray/` 전체 + 런처·패키징 메타 (`pyproject.toml`, `dev_start.*`)
- 기준 커밋: `e928611` (2026-07-26)
- 패키지 버전: 여전히 `0.1.0` (`pyproject.toml` / `__version__`) — 본 문서는 **검토 리비전**이며 릴리스 태그 아님
- 실행 확인: Windows·macOS 양쪽에서 트레이/팝업/재생·비트레이트 전환 검증됨

---

## 0. v0.1 → v0.2 한줄 요약

v0.1에서 지적한 **안정성 High/Medium 이슈(H-1..H-3, M-1..M-4)는 해소**되었고,
이어 **크로스플랫폼 UX 폴리시**(테마·아이콘·팝업 앵커·Dock 숨김·첫 실행 힌트)와
**비트레이트 전환 재연결 루프**까지 잡았다.
남은 핵심 게이트는 설계 문서의 하드 제약인 **단독 빌드(PyInstaller + mpv 번들)** 와
**단일 인스턴스**, 테스트/CI, MVP 이후 기능이다.

---

## 1. v0.1 이슈 해소 현황

| ID | 내용 | v0.2 상태 | 비고 |
|----|------|-----------|------|
| H-1 | 콘솔 숨김이 사용자 터미널까지 숨김 | ✅ 해결 | `GetConsoleProcessList` + 소유 PID 확인 (`platform_win.py`) |
| H-2 | Windows named pipe read 무한 블로킹 | ✅ 해결 | `PeekNamedPipe` 폴링 + IPC reader 스레드 |
| H-3 | 스트림 사망·오프라인 상태 불일치 | ✅ 해결 | `end-file` 구독, 오프라인 시 `stop`, 지수 백오프 재연결 |
| M-1 | UI 스레드에서 블로킹 IPC | ✅ 해결 | `PlayerWorker` + `QThread` 시그널 큐 |
| M-2 | 더블클릭 중복 토글 | ✅ 해결 | `DoubleClick` 무시, `Trigger`만 토글 |
| M-3 | 일시정지 중 비트레이트 변경 후 이전 URL resume | ✅ 해결 | paused도 새 URL `play`; pending 경로 정리 |
| M-4 | 볼륨 드래그 중 매 틱 config 저장 | ✅ 해결 | IPC는 `valueChanged`, 저장은 `sliderReleased` |
| L-1 | `field` import 미사용 | ⚠️ 잔존 | `config.py`에 여전히 unused import |
| L-3 | `USER_AGENT` / `__version__` 이중 관리 | ⚠️ 잔존 | 둘 다 `0.1.0` 하드코딩 |
| L-4 | `RadioPlayer` 상태 API 부족 | ⚠️ 부분 | `is_playing`/`is_paused`는 구현체에 있음. Protocol에 `is_paused` 미반영 |
| L-5 | 첫 메타데이터 수신 시 자동 재생 | ✅ 유지(의도) | 제품 동작으로 채택된 상태로 봄 |
| L-7 | 팝업이 커서 기준 | ✅ 해결 | 트레이 `geometry` 앵커 + 10px gap |
| L-8 | 단일 인스턴스 | ❌ 미착수 | |

추가 회귀(v0.1 이후 발견 → v0.2에서 수정):

| 이슈 | 상태 | 커밋 |
|------|------|------|
| Windows: `TrayController`가 `QObject`가 아니어 `QTimer(self)` TypeError로 기동 실패 | ✅ | `85c0865` |
| 비트레이트 전환 시 `end-file reason=stop` → 재연결 무한 루프 | ✅ | `85c0865` |
| 선형 볼륨이 체감보다 작게 들림 | ✅ (완화) | `85c0865` — `ui^0.75` 곡선 |
| macOS Unix socket reader가 idle timeout으로 죽음 | ✅ | `431585d` |

---

## 2. 설계 문서 대비 적합성 (재평가)

### 2.1 닫힌 결정

| 결정 사항 | 상태 | 비고 |
|-----------|------|------|
| 좌클릭 = Play/Pause | ✅ | Win/mac 검증 |
| 우클릭 = 커스텀 비모달 팝업 | ✅ | 아이콘 geometry 앵커 |
| Qt(PySide6), pystray 배제 | ✅ | |
| mpv + JSON IPC | ✅ | Win named pipe / Unix socket |
| URL 하드코딩 금지 (마운트는 API) | ✅ | API 호스트만 상수 |
| 단독 빌드 배포 | ❌ | **여전히 미착수 — 릴리스 게이트** |
| Linux best-effort | ⚠️ | 코드 경로 있음, DE 런타임 미검증 |
| macOS Dock 숨김 | ✅ | `NSApplicationActivationPolicyAccessory` + pyobjc extra |

### 2.2 아키텍처

문서 §5 분리(App / Tray·Popup / Metadata / Player) 유지.
v0.1에서 깨져 있던 “Qt 슬롯에서 블로킹 금지”는 `PlayerWorker`로 충족.

현재 패키지 구조:

```text
coderadio_tray/
  app.py, config.py, platform_win.py, __main__.py
  metadata/client.py
  player/{base,mpv_player,worker}.py
  ui/{tray,popup,icons}.py
```

개발 런처: `dev_start.bat` / `dev_start.ps1` / `dev_start.command` (macOS는 `.[macos]`).

---

## 3. v0.1 이후 구현된 주요 변경 (테마별)

### 3.1 안정성·재생

- IPC reader + non-blocking Win pipe (`PeekNamedPipe`)
- 의도적 `end-file`(stop/quit/redirect)과 실제 끊김(eof/error) 구분 → 비트레이트 전환 루프 제거
- 오프라인 시 정지, 예상치 못한 종료 시 지수 백오프 재연결
- 재생 시작 시 pending 재연결 타이머 취소

### 3.2 UX·비주얼

- 팝업·트레이 아이콘 라이트/다크 추종
- 모노크롬 아이콘: macOS 템플릿, Windows는 **작업표시줄** 테마(`SystemUsesLightTheme`) 기준 잉크
- 에러 상태 `!` 표시
- 볼륨 노브: 다크=흰 / 라이트=검정
- 체감 볼륨: UI% → mpv 진폭에 `^0.75` 매핑 (UI 50 → ~60)
- 팝업을 트레이 아이콘 중앙 하단 고정, 메뉴바/작업표시줄과 10px 간격
- 트레이 “아이콘 찾으세요” 힌트는 **최초 1회만** (`first_run_hint_shown`)

### 3.3 플랫폼

- macOS: Dock/앱 메뉴 없이 메뉴바 전용 (Accessory policy)
- macOS 의존: `pyobjc-core` / `pyobjc-framework-Cocoa` (`macos` optional extra)
- Windows 기동: `TrayController(QObject)`로 PySide6 QTimer parent 타입 오류 해소

---

## 4. 진척도 (마일스톤 재평가)

| # | 마일스톤 | v0.1 | v0.2 | 내용 |
|---|----------|------|------|------|
| 1 | Spike | 100% | **100%** | 완료 |
| 2 | Core | 90% | **98%** | PlayerWorker·IPC·볼륨 곡선까지 안정 |
| 3 | Tray MVP | 95% | **100%** | 앵커·테마·힌트·Dock 숨김 포함 |
| 4 | Robustness | 10% | **75%** | 재연결·오프라인·비트레이트 전환 OK. **단일 인스턴스·절전/네트워크 전환 검증** 남음 |
| 5 | Polish | 60% | **85%** | 아이콘/테마/bitrate/팝업 완료. README·Linux 고지·버전 bump·독자 아이콘 디자인 남음 |
| 6 | Standalone release | 0% | **0%** | PyInstaller + mpv 번들 **미착수** |
| 7 | Optional | 0% | **0%** | 핫키, SMTC/MPRIS, 앨범아트, 로그인 자동시작 등 |

기능 단위:

| 영역 | 상태 |
|------|------|
| 스트림 재생 (128/64) + 전환 | ✅ (루프 버그 수정됨) |
| 곡 정보 폴링 | ✅ |
| 트레이 아이콘 idle/playing/error + OS 테마 | ✅ |
| 좌클릭 토글 / 우클릭 팝업 | ✅ |
| 볼륨(체감 곡선) / 설정 저장 | ✅ |
| 재연결·오프라인 | ✅ |
| macOS 메뉴바 전용(Dock 숨김) | ✅ |
| 개발용 one-click 런처 | ✅ |
| 단일 인스턴스 | ❌ |
| 단독 빌드 (exe/app + mpv) | ❌ |
| 단위·CI 테스트 | ❌ |
| Linux GUI 검증 | ❌ (best-effort) |
| MVP 이후(아트·핫키·미디어키·autostart) | ❌ |

---

## 5. 현재 잔존 리스크 / 관찰 사항

| 등급 | 내용 | 위치 |
|------|------|------|
| Medium | 절전 복귀·Wi‑Fi 전환 후 장시간 안정성은 수동 스모크만 있음. 재연결은 구현됐으나 매트릭스 검증 부족 | `app.py` reconnect |
| Medium | `RadioPlayer` Protocol에 `is_paused` 없음 — 구현체와 인터페이스 어긋남 | `player/base.py` |
| Low | `config.field` unused import | `config.py` |
| Low | 버전 문자열 삼중(`pyproject` / `__init__` / `USER_AGENT`) | 전역 |
| Low | 볼륨 곡선(`0.75`)은 주관적 — 추후 조정·설정화 여지 | `mpv_player.ui_volume_to_mpv` |
| Low | macOS에서 `tray.geometry()`가 DE/Qt 버전에 따라 비어 있으면 커서 폴백 — 드물게 위치 흔들림 가능 | `ui/tray.py` |
| Info | 자동 시작(첫 메타데이터)은 설정 토글 없음 | `app.py` |

안전성 유지 확인:

- 메타데이터 스레드는 Qt Signal로 마샬링
- config 로드 실패 폴백·키 필터·clamp 유지
- mpv terminate→kill, Unix socket 정리 유지
- 의도적 end-file은 재연결하지 않음 (실측: bitrate switch → `reason=stop`)

---

## 6. 미해결 과제 리스트 (우선순위)

실행 순서 한줄 요약:

**Windows 단독 빌드 → 단일 인스턴스 → macOS .app** → (이어서) 테스트·버전·README 정리 후 v0.2.0 태그 검토.

기능 확장(P3)은 단독 빌드가 나온 뒤에 연다.

> **v0.2.0 구현 반영 (2026-07-26):** Windows onedir 빌드 스크립트·번들 mpv·`QLockFile` 단일 인스턴스·
> macOS 빌드 스크립트(`.app` + `LSUIElement`)·pytest 스모크·버전 `0.2.0`·README 갱신 완료.
> 실기기에서 macOS `.app` 클린 스모크와 서명/릴리스 zip은 남아 있음.

### P0 — 릴리스 게이트 (하드 제약)

1. **PyInstaller onedir 빌드** (windowed) — ✅ Windows 스크립트/`packaging/coderadio_tray.spec` (슬림 Qt, ~240MB with mpv)
   - Windows: `CodeRadioTray.exe` + 동봉 `mpv/mpv.exe`
   - macOS: `scripts/build_macos.sh` → `.app` + 동봉 mpv + `LSUIElement` (맥에서 빌드·스모크 필요)
   - 리소스·mpv 경로: `paths.iter_mpv_candidates` (exe 옆 / frozen / `.tools`)
2. **Python·mpv 없는 클린 환경 스모크** — ⚠️ Windows 개발 PC에서 해제 바이너리 기동·단일 인스턴스 확인. 완전 클린 PC/Mac은 남음
3. **단일 인스턴스 가드** — ✅ `QLockFile` (`%APPDATA%/…/instance.lock`)
4. 릴리스/서명 안내 README 반영 — ✅ (unsigned / SmartScreen·Gatekeeper)

### P1 — Robustness·품질 마감

5. 절전/네트워크 전환 수동 매트릭스 (Win + mac) 문서화 또는 체크리스트 — ❌ 남음
6. `RadioPlayer` Protocol에 `is_paused` 등 상태 API 정렬 — ✅ (`toggle_pause`는 Protocol에서 제거)
7. 버전 단일화 (`__version__` → USER_AGENT / pyproject 동기) — ✅ `0.2.0`
8. `config.py` unused `field` import 제거 — ✅
9. 단위 테스트: metadata URL 선택, config clamp, `ui_volume_to_mpv`, end-file reason 필터 — ✅ `tests/test_core.py`
10. (선택) CI: lint + 단위 테스트 매트릭스 (3.11/3.12); GUI는 제외 — ❌ 남음

### P2 — Polish / 문서

11. README를 현재 UX에 맞게 갱신 — ✅
12. Linux best-effort 고지를 README에 명시 — ✅
13. 독자 트레이 아이콘 디자인(현재 프로그래매틱 도형) — ❌ 남음
14. 패키지/검토 버전 bump 정책 정리 — ✅ 앱·문서 `0.2.0` / review-v0.2 동기

### P3 — MVP 이후 (considerations §1.2)

15. 앨범 아트 / 다음 곡 / 청취자 수
16. 로그인 시 자동 시작
17. 전역 핫키 (Play/Pause, 볼륨)
18. OS 미디어 연동 (Windows SMTC, Linux MPRIS, macOS Now Playing)
19. 릴레이(리전) 선택
20. WebSocket nowplaying (폴링 대체 최적화)
21. 자동 업데이트 (없어도 Releases 링크로 MVP 가능)

---

## 7. 권장 다음 스프린트 (제안)

권장 순서: **Windows 단독 빌드 → 단일 인스턴스 → macOS .app**

1. **Standalone Windows onedir + mpv 번들** → 클린 PC 스모크
2. **단일 인스턴스**
3. **macOS .app 동일 파이프라인**
4. 테스트·버전·README 정리 후 **v0.2.0 태그** 검토

기능 확장은 단독 빌드가 나온 뒤에 여는 편이 설계 문서의 하드 제약과 맞다.

---

## 8. 총평

v0.2 시점의 앱은 **일상 개발용 트레이 플레이어로서 Windows·macOS에서 쓸 수 있는 수준**이다.
v0.1의 장애 경로(IPC 블로킹, 상태 불일치, 콘솔 부작용)와 v0.2에서 새로 잡힌
비트레이트 재연결 루프·기동 크래시까지 해소되어, 마일스톤 1–3은 사실상 닫혔고
Robustness/Polish도 상당 부분 채워졌다.

다만 제품 정의상 **“압축 풀고 실행”** 이 아직 불가능하다.
다음 검토(v0.3 예정)의 성공 기준은 PyInstaller 산출물 + 번들 mpv + 단일 인스턴스가
Python 없는 환경에서 재생까지 통과하는 것으로 두면 된다.

---

*작성일: 2026-07-26. 기준 트리: `e928611`.*
