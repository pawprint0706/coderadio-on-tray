# v0.3 구현 검토 보고서

- 검토 기준: `docs/considerations.md`, `docs/review-v0.1.md`, `docs/review-v0.2.md`
- 기준 커밋: `master` @ 릴리스 `v0.3.0` (2026-07-26)
- 패키지 버전: **`0.3.0`** (`src/coderadio_tray/__init__.py` → hatch dynamic)
- 실행/빌드 확인:
  - **Windows:** Inno Setup per-user 설치 마법사 빌드 → 설치 → 실행 이상 없음 (실측)
  - **macOS:** 자급식 `.app` + DMG 파이프라인 + 클린 스모크 (v0.3 맥 작업)
  - **CI:** ruff check + pytest 매트릭스 (py3.11/3.12 × win/mac/linux) success

---

## 0. 한줄 요약

설계 문서의 **단독 빌드 하드 제약**을 Windows·macOS 양쪽에서 닫고 **GitHub Release `v0.3.0`** 으로
배포한다. Windows는 `%LOCALAPPDATA%\Programs\CodeRadioTray` 유저 경로 설치 마법사,
macOS는 DMG(드래그 설치)가 배포 산출물이다. P2(Polish)·P3(기능 확장)는 **보류**.

---

## 1. 게이트·이슈 해소 현황 (릴리스 시점)

| 항목 | 상태 | 비고 |
|------|------|------|
| 단일 인스턴스 | ✅ | `QLockFile` (`instance.lock`) |
| Windows 단독 빌드 | ✅ | PyInstaller onedir + 번들 `mpv/` |
| Windows 배포 산출물 | ✅ | **`CodeRadioTray-0.3.0-win64-setup.exe`** (Inno, per-user, ~69MB) |
| Windows 설치·실행 검증 | ✅ | 설치 마법사 → 유저 경로 설치 → 실행 확인 (2026-07-26) |
| macOS 단독 빌드 | ✅ | `.app` + dylibbundler + rpath 정리 + ad-hoc 서명 |
| macOS 배포 산출물 | ✅ | `CodeRadioTray-*-macos.dmg` (UDZO + `/Applications` symlink) |
| CI | ✅ | `.github/workflows/ci.yml` |
| 버전 single-source | ✅ | hatch `dynamic = ["version"]` ← `__init__.__version__` |
| 단위 테스트 | ✅ | paths / single_instance / popup / icons / core 등 |
| P2 Polish · P3 MVP 이후 | ⏸ | 다음 지시까지 보류 |

---

## 2. 배포 산출물

| 산출물 | 경로 / 자산명 | 설치 위치 | 비고 |
|--------|----------------|-----------|------|
| Windows Setup | `CodeRadioTray-0.3.0-win64-setup.exe` | `%LOCALAPPDATA%\Programs\CodeRadioTray` | **배포용**. 관리자/Program Files 불필요 |
| Windows onedir | `dist/CodeRadioTray/` | (포터블) | 개발·디버그용 |
| macOS DMG | `CodeRadioTray-0.3.0-macos.dmg` | `/Applications` (권장) | **배포용**. Gatekeeper unsigned 안내 |

빌드:

```text
Windows:  build_windows.bat   → setup.exe
macOS:    build_macos.command / scripts/build_macos.sh → .dmg
```

---

## 3. v0.2 이후 주요 변경 (누적)

### 3.1 패키징

- Windows: Inno Setup 스크립트 `packaging/windows/CodeRadioTray.iss`, 빌드 스크립트에 ISCC 연동
- macOS: dylibbundler로 Homebrew dylib 번들, 중복 `LC_RPATH` 제거, DMG 생성, `build_macos.command`
- 공통: 슬림 Qt PyInstaller spec (`packaging/coderadio_tray.spec`)

### 3.2 품질

- CI 매트릭스, ruff lint(+ format 적용), hatch 버전, Protocol `is_paused`, 테스트 보강

### 3.3 UX (기존 유지)

- 테마·트레이 아이콘·팝업 앵커·Dock 숨김·첫 실행 힌트·비트레이트 전환 루프 수정·체감 볼륨 곡선

---

## 4. 진척도 (마일스톤)

| # | 마일스톤 | v0.3.0 |
|---|----------|--------|
| 1–3 | Spike / Core / Tray MVP | **100%** |
| 4 | Robustness | **~85%** (절전/네트워크 매트릭스 문서화 남음) |
| 5 | Polish | **~90%** (독자 아이콘·Linux 고지 보류) |
| 6 | Standalone release | **~95%** (Win/mac 산출물+검증. 서명·완전 클린 타인 PC 재검증은 선택) |
| 7 | Optional | **0%** (P3 보류) |

---

## 5. 잔존 리스크

| 등급 | 내용 |
|------|------|
| Medium | 절전/Wi‑Fi 전환 장시간 매트릭스 미문서화 |
| Info | 코드 서명 포기 — SmartScreen/Gatekeeper 경고 가능. **SHA256으로 무결성 확인** (`v0.3.0` Release / `SHA256SUMS`) |
| Low | 볼륨 곡선(`^0.75`) 주관적 |
| Info | 자동 재생·autostart 설정 토글 없음 |

---

## 6. 미해결 과제 (보류 포함)

실행 순서 (보류 전 남은 선택 항목):

**절전/네트워크 매트릭스 문서화 → P2/P3는 지시 대기**

(코드 서명은 포기. 릴리스 SHA256 + CI `ruff format --check`로 대체.)

### 진행함 / 닫음
- Windows 클린 설치·실행 검증 (Inno) ✅  
- CI ✅  
- Protocol / 버전 / lint·format / 단위 테스트 보강 ✅  

### P2 — Polish (⏸ 보류)
- 독자 트레이 아이콘  
- Linux best-effort 고지·Ubuntu 스모크  
- README macOS Gatekeeper 안내 보강  

### P3 — MVP 이후 (⏸ 보류)
- 앨범 아트, 로그인 자동시작, 핫키, SMTC/MPRIS, 릴레이, WebSocket, 자동업데이트  

---

## 7. 릴리스 노트 요지 (`v0.3.0`)

- 브라우저 없이 트레이/메뉴바에서 Code Radio 재생
- Windows: per-user 설치 마법사 / macOS: DMG
- 128/64 kbps, 볼륨, 테마 연동 아이콘, 단일 인스턴스, 재연결
- Python·시스템 mpv 설치 불필요 (번들)
- Unofficial — freeCodeCamp 비제휴

---

## 8. 총평

v0.3.0은 **“압축/설치 후 실행”** 목표를 Win·mac에서 충족한 첫 공개 릴리스다.
이후 작업은 서명·장시간 안정성 문서와, 보류된 P2/P3 제품 확장이다.

---

*작성일: 2026-07-26. 릴리스 태그: `v0.3.0`.*
