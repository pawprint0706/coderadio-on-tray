# v0.3 구현 검토 보고서

- 검토 기준: `docs/considerations.md`, `docs/review-v0.1.md`, `docs/review-v0.2.md`
- 기준 커밋: `60a2d39` (2026-07-26)
- 패키지 버전: `0.2.0` (`pyproject.toml` / `__version__`)
- 실행/빌드 확인: Windows(v0.2) + **macOS 단독 빌드 + DMG 클린 스모크**(본 리비전)

---

## 0. v0.2 → v0.3 한줄 요약

v0.2에서 남았던 **하드 제약 두 개(단독 빌드, 단일 인스턴스) 중 macOS 단독 빌드를 닫고**
릴리스 산출물(DMG)까지 만들었다. Windows onedir 스크립트/단일 인스턴스는 v0.2 말미에
이미 들어왔고, v0.3은 **환경 의존성을 번들에 묶어 Python/Homebrew가 없는 Mac에서 동작**
하도록 만든 것이 핵심이다. 이제 설계 문서 §8의 “단독 빌드 배포”는 Windows·macOS 양쪽
에서 기술적 게이트를 통과했고, 남은 것은 **클린 머신 실검증·서명·CI·Linux**와 **MVP 이후**
확장이다.

---

## 1. v0.2 이슈 · 게이트 해소 현황

| 항목 | v0.2 | v0.3 | 비고 |
|------|------|------|------|
| 단일 인스턴스 (L-8) | ❌ | ✅ | `QLockFile` (`config_dir/instance.lock`, stale 30s). 2번째 실행 “already running”, mpv 미증식 확인 |
| macOS 단독 빌드 (하드 제약) | ❌ | ✅ | `.app` + 번들 mpv + **dylibbundler로 Homebrew dylib 47개 번들 + rpath 중복 제거 + ad-hoc 서명** |
| macOS 릴리스 산출물 | — | ✅ | `dist/CodeRadioTray-0.2.0-macos.dmg` (65MB UDZO + `/Applications` symlink) |
| 클린 Mac 동작 검증 | ❌ | ✅ | 번들 Mach‑O 159개 파일 중 `/opt/homebrew` 참조 **0**, dmg 마운트→직접 실행→재생 확인 |

### v0.2에서 잡고 v0.3에서 재확인된 회귀/버그

| 이슈 | 상태 | 커밋 |
|------|------|------|
| Windows: `TrayController(QObject)`로 QTimer parent 타입 오류 | ✅ | `85c0865` |
| 비트레이트 전환 `end-file reason=stop` → 재연결 무한 루프 | ✅ | `85c0865` |
| 체감 볼륨 너무 작음 (`ui^0.75` 매핑) | ✅ | `85c0865` |
| macOS Unix socket reader idle timeout으로 사망 | ✅ | `431585d` |
| 팝업 다크 하드코딩 → 시스템 테마 | ✅ | `f529355` |
| 트레이 아이콘 컬러 → 앱 colorScheme 의존(작업표시줄과 불일치) | ✅ | `cd8cd42` (macOS template / Win `SystemUsesLightTheme`) |
| 팝업이 우클릭 지점 기준 (mac) → 아이콘 geometry 고정 | ✅ | `ba4706d`, `3f200c5` |
| macOS Dock 아이콘 표시 | ✅ | `8ada5e7` (NSApplication Accessory) |
| 트레이 힌트 매 실행마다 표시 | ✅ | `e928611` (최초 1회, config 플래그) |

---

## 2. 설계 문서 대비 적합성 (재평가)

### 2.1 닫힌 결정

| 결정 사항 | 상태 | 비고 |
|-----------|------|------|
| 좌클릭 = Play/Pause | ✅ | Win/macOS 검증 |
| 우클릭 = 커스텀 비모달 팝업 | ✅ | 아이콘 geometry 앵커 + 10px gap, 중심 정렬 |
| Qt(PySide6), pystray 배제 | ✅ | |
| mpv + JSON IPC | ✅ | Win named pipe / Unix socket |
| URL 하드코딩 금지 (마운트는 API) | ✅ | |
| **단독 빌드 배포** | ✅(기술 게이트) | Win onedir + mpv.exe; **mac .app + 번들 mpv/dylib + DMG** |
| 단일 인스턴스 | ✅ | `QLockFile` |
| Linux best-effort | ⚠️ | 코드 경로·`paths.iter_mpv_candidates` 있음. DE 런타임 미검증 |
| macOS Dock 숨김 | ✅ | `LSUIElement`(빌드) + `NSApplicationActivationPolicyAccessory`(소스 런) |

> “하드 제약 = 단독 빌드”는 설계 문서 §8의 릴리스 전제조건이다. v0.3에서 macOS가
> 이 게이트를 기술적으로 통과했다(클린 머신 실검증은 아래 §6 과제).

### 2.2 배포 산출물

| 산출물 | 경로 | 크기 | 비고 |
|-------|------|------|------|
| macOS DMG | `dist/CodeRadioTray-0.2.0-macos.dmg` | 65M | **배포용**. UDZO 압축, `/Applications` symlink |
| macOS .app | `dist/CodeRadioTray.app` | 165M | 개발/참고. `Contents/MacOS/mpv/{mpv,libs/}` |
| Windows onedir | `dist/CodeRadioTray/` | ~240M | `.exe` + `_internal/` + `mpv/mpv.exe` (v0.2) |

---

## 3. v0.3 구현 주요 변경

### 3.1 패키징 (macOS 자급식화)

- `scripts/build_macos.sh`:
  - Homebrew → `.tools/mpv/extract/mpv` 자동 복사
  - `dylibbundler` 부재 시 `brew install dylibbundler` (빌드 타임 도구만)
  - PyInstaller(`packaging/coderadio_tray.spec`, 슬림 Qt excludes) 후
    `dylibbundler -x mpv -d .../mpv/libs -p @executable_path/libs/ -i /usr/lib -i /System/Library`
  - **중복 `LC_RPATH @executable_path/libs/` 제거** — dyld가 중복 rpath에서 abort하는 치명 버그 수정
  - `install_name_tool` 후 무효화된 서명 ad-hoc 재서명(mpv 단건 + .app deep)
- 산출물 검증:
  - `otool -L` 상 `/opt/homebrew` 참조 **0**
  - 번들 내 Mach-O 159개 파일 스캔 → Homebrew 절대경로 **0**
  - DMG 마운트 → `/Applications` 링크 표시 → 앱 직접 실행 → 번들 mpv 경로로 재생 확인
- `build_macos.command` 더블클릭 런처(Finder) 추가 — Windows `.bat`과 동일 경험

### 3.2 단일 인스턴스 (v0.2 말미 도입, v0.3 재확인)

- `single_instance.try_acquire()` → `QLockFile` (config_dir/instance.lock, stale 30s)
- 2번째 실행: 로그 “another instance is already running”, mpv 추가 spawn 없음(실측 mpv 1개 유지)

### 3.3 UX/플랫폼 (v0.2~v0.3 연속)

- 팝업: 시스템 라이트/다크 테마, 아이콘 중심 정렬, 메뉴바/작업표시줄과 10px 간격
- 아이콘: 모노크롬. macOS는 `QIcon.setIsMask` template(시스템이 메뉴바 색에 맞춰 재착색),
  Windows는 `SystemUsesLightTheme`(작업표시줄 모드) 기준 잉크 + 2초 폴링, Linux는 `colorScheme`
- macOS 소스 런: `NSApplication.sharedApplication().setActivationPolicy_(Accessory)` (QApplication 생성 **직후**)
- 첫 실행 힌트 1회(`first_run_hint_shown` in config)

---

## 4. 진척도 (마일스톤 재평가)

| # | 마일스톤 | v0.2 | v0.3 | 내용 |
|---|----------|------|------|------|
| 1 | Spike | 100% | 100% | |
| 2 | Core | 98% | 98% | |
| 3 | Tray MVP | 100% | 100% | |
| 4 | Robustness | 75% | 85% | 단일 인스턴스 추가. 절전/네트워크 매트릭스 still 남음 |
| 5 | Polish | 85% | 88% | 빌드 런처, DMG. 독자 아이콘·Linux 고지 정비 남음 |
| 6 | **Standalone release** | 0% | **80%** | **Win onedir + macOS .app/DMG + 번들 mpv**. 클린 머신/서명/CI 남음 |
| 7 | Optional | 0% | 0% | |

기능 단위:

| 영역 | 상태 |
|------|------|
| 스트림 재생 (128/64) + 전환 | ✅ |
| 곡 정보 폴링 | ✅ |
| 트레이 아이콘 idle/playing/error + OS 테마 | ✅ |
| 좌클릭 토글 / 우클릭 팝업 | ✅ |
| 볼륨(체감 곡선) / 설정 저장 | ✅ |
| 재연결·오프라인 | ✅ |
| 단일 인스턴스 | ✅ |
| macOS 메뉴바 전용(Dock 숨김) | ✅ |
| 개발용 one-click 런처 | ✅ (Win `dev_start.bat/ps1`, mac `dev_start.command`, 빌드 mac `build_macos.command`) |
| **단독 빌드 (Win onedir + mac .app/DMG)** | ✅ (기술 게이트) |
| **클린 환경(Python/mpv/Homebrew 없음) 스모크** | ✅ macOS(이 빌드 머신 한정 Homebrew 검증 방식). **완전 클린 Mac/PC 실검증** 남음 |
| 단위·CI 테스트 | ⚠️ 단위(`tests/test_core.py`) 있음. **CI 매트릭스** 남음 |
| Linux GUI 검증 | ❌ (best-effort) |
| 코드 서명(Gatekeeper/SmartScreen) | ❌ unsigned ad-hoc |
| MVP 이후(아트·핫키·미디어키·autostart) | ❌ |

---

## 5. 잔존 리스크 / 관찰

| 등급 | 내용 | 위치 |
|------|------|------|
| Medium | 절전/Wi‑Fi 전환 후 장시간 안정성 수동 스모크만. 재연결 구현됐으나 매트릭스 부족 | `app.py` reconnect |
| Medium | `RadioPlayer` Protocol에 `is_paused` 미반영 — 구현체와 어긋남(v0.2 잔존) | `player/base.py` |
| Medium | macOS 빌드 머신이 Homebrew 환경이라 “dylib 재배치 후 동작”은 검증했으나, **Homebrew가 아예 없는 Mac**에서의 `dylibbundler` 실행·dylib 해석은 별도 머신 확인 필요 | 빌드 파이프라인 |
| Low | 버전 문자열 삼중(`pyproject` / `__init__` / `USER_AGENT`) — v0.2에서 `0.2.0` 동기는 됐으나 single-source는 아님 | 전역 |
| Low | 볼륨 곡선(`0.75`)은 주관적 — 조정/설정화 여지 | `mpv_player.ui_volume_to_mpv` |
| Low | macOS `tray.geometry()`가 비어 있으면 커서 폴백 — 드물게 위치 흔들림 | `ui/tray.py` |
| Low | 잔존 unused import가 v0.2에서 정리됐는지 재확인 필요(`config.field` 등) | `config.py` |
| Info | 자동 시작(첫 메타데이터)은 설정 토글 없음 | `app.py` |

---

## 6. 미해결 과제 리스트 (우선순위)

실행 순서 한줄 요약:

**Windows 클린 PC 실검증 → (병행) CI 매트릭스 → 절전/네트워크 매트릭스 문서화 →
Linux 스모크(1종) → 독자 아이콘 → MVP 이후**.

릴리스 자체는 이미 산출물(dmg/onedir)이 있으므로, 다음 게이트는
**“Python/mpv/Homebrew가 없는 머신에서의 실사용 보증”**과 **서명/CI**로 이동.

### P0 — 릴리스 보증 마감

1. **완전 클린 머신 실검증** — Windows(PC) + macOS(Mac, Homebrew 없는 환경 또는 VM)에서
   - DMG/onedir 해제 → 실행 → 재생 → 좌클릭/우클릭/비트레이트 전환 → 단일 인스턴스 → 종료
   - 현재 v0.3 macOS 검증은 “Homebrew 있는 머신에서 dylib 재배치 후 동작”까지만 (o-tool 홈경로 0 확인)
2. **절전/네트워크 전환 매트릭스** (Win + mac) — 체크리스트/문서화
3. (선택) 코드 서명 — 개인 인증서 또는 notarization 안내. 현재 unsigned ad-hoc이라
   Gatekeeper/SmartScreen 경고 발생 가능 → README/배포 안내에 명시

### P1 — 품질·CI

4. `RadioPlayer` Protocol에 `is_paused` 정렬 (v0.2 잔존)
5. 버전 single-source (`__version__` → `USER_AGENT` 동기화 자동화)
6. unused import 재점검 (`config.field` 등)
7. **CI 매트릭스**: lint + `tests/test_core.py` on Python 3.11/3.12 (Win/mac/Linux). GUI 제외
8. 단위 테스트 보강: `single_instance` 경로, `paths.iter_mpv_candidates` frozen 분기, 테마/앵커 로직

### P2 — Polish / 문서

9. 독자 트레이 아이콘 디자인(현재 프로그래매틱 도형)
10. Linux best-effort 고지 README 정비 + 1종(Ubuntu) 스모크 시도
11. README에 macOS DMG 설치 흐름 + Gatekeeper 우회 안내(최초 실행) 추가

### P3 — MVP 이후 (considerations §1.2)

12. 앨범 아트 / 다음 곡 / 청취자 수
13. 로그인 시 자동 시작
14. 전역 핫키 (Play/Pause, 볼륨)
15. OS 미디어 연동 (Windows SMTC, Linux MPRIS, macOS Now Playing)
16. 릴레이(리전) 선택
17. WebSocket nowplaying (폴링 대체 최적화)
18. 자동 업데이트 (없어도 Releases 링크로 가능)

---

## 7. 권장 다음 스프린트

1. **완전 클린 머신 실검증(Windows + macOS)** — 하드 제약의 실사용 보증
2. **CI 매트릭스**(lint + 단위) 도입 — 회귀 사전 차단
3. **절전/네트워크 매트릭스** 문서화 — Robustness 마일스톤 마감
4. 독자 아이콘 + Linux 1종 스모크 → v0.3.0 태그 검토

---

## 8. 총평

v0.3에서는 v0.2가 남긴 **하드 제약(단독 빌드)**의 macOS 측을 닫았다. 핵심은 “mpv 바이너리만
복사하면 안 된다”는 것을 실빌드에서 확인하고, Homebrew dylib 47개를 `dylibbundler`로 번들에
묶고 중복 rpath 제거·재서명까지 넣어 **`/opt/homebrew` 참조 0**인 자급식 `.app`/DMG를 만든 점.
다음 검토(v0.4)의 성공 기준은 **“Python/mpv/Homebrew가 없는 머신에서 DMG 한 번 열면
재생까지 통과”**와 **CI + 절전 매트릭스**로 두면 된다.

---

*작성일: 2026-07-26. 기준 트리: `60a2d39`.*