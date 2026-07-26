# Code Radio Tray Player — 고려사항

Python 기반 크로스 플랫폼 트레이(메뉴바) 상주 플레이어를 만들기 전에 정리한 설계·구현 고려사항이다.

- 대상 서비스: [Code Radio](https://coderadio.freecodecamp.org/) (freeCodeCamp, AzuraCast)
- 목표: 브라우저 없이 트레이에서 재생/정지·볼륨·곡 정보를 다루는 가벼운 데스크톱 앱
- 대상 OS: Windows, macOS, Linux (트레이/메뉴바 환경)

### 하드 제약

| 제약 | 의미 |
|------|------|
| **단독 빌드 배포** | 최종 사용자는 **Python을 설치하지 않고** 실행 가능해야 한다 |
| 형태 | OS별 실행 파일/앱 번들(예: `.exe` / `.app` / AppImage·바이너리 디렉터리)로 배포 |
| 개발 환경 | 소스 실행·디버깅에는 Python 사용 가능. **배포 산출물**만 런타임 Python 비의존 |
| 부가 런타임 | Python 외 의존(mpv 등)도 가능하면 **번들**해, “압축 풀고 실행” 또는 설치 한 번으로 끝나게 한다 |

이 제약은 패키징·오디오 백엔드·의존성 선택에 우선한다. “시스템 Python + pip install”만 지원하는 배포는 허용하지 않는다.

---

## 1. 제품 범위

### 1.1 MVP에 넣을 것

| 기능 | 이유 |
|------|------|
| 트레이 아이콘 상주 | 핵심 UX. 창을 띄우지 않고 상시 접근 |
| Play / Pause | 최소 조작 |
| **좌클릭 = Play/Pause 토글** | 한 번의 클릭으로 재생 제어 (필수) |
| **우클릭 = 메뉴/팝업 호출** | 볼륨·곡 정보·종료 등 |
| 볼륨 조절 | 코딩 중 자주 바꿈 |
| 현재 곡 표시 (아티스트 / 타이틀) | 공식 사이트와 동등한 정보 |
| 앱 종료 | 트레이에서 완전 종료 |

### 1.2 MVP 이후(선택)

- 앨범 아트, 다음 곡, 청취자 수
- 비트레이트 전환 (128 / 64 kbps)
- 릴레이(리전) 자동·수동 선택
- 전역 단축키 (Play/Pause, 볼륨)
- OS 미디어 키 / Now Playing 연동 (SMTC, MPRIS, macOS Now Playing)
- 자동 시작(로그인 시)
- 다크/라이트 아이콘, 재생 중 아이콘 상태

### 1.3 하지 않을 것(초기)

- 로컬 라이브러리·플레이리스트 관리
- 계정·요청곡·채팅
- 웹뷰로 공식 사이트 임베드 (무거움, 트레이 앱 목적과 어긋남)
- 오프라인 캐시 재생 (라이브 스트림 특성상 불필요)
- **사용자 PC에 Python 설치를 요구하는 배포** (venv / `pip install` only)

---

## 2. Code Radio 스트림·메타데이터

### 2.1 인프라 현황 (2026-07 기준)

공식 사이트는 React SPA이고, 백엔드는 **AzuraCast**다.  
과거 `coderadio-admin.freecodecamp.org` 호스트는 DNS/가용성이 불안정하거나 이전된 흔적이 있다.  
현재 확인된 엔드포인트는 **v2**다.

| 용도 | URL |
|------|-----|
| 웹 플레이어 | `https://coderadio.freecodecamp.org/` |
| Now Playing API | `https://coderadio-admin-v2.freecodecamp.org/api/nowplaying/coderadio` |
| 128 kbps MP3 | `https://coderadio-admin-v2.freecodecamp.org/listen/coderadio/radio.mp3` |
| 64 kbps MP3 | `https://coderadio-admin-v2.freecodecamp.org/listen/coderadio/low.mp3` |

참고: 커뮤니티·과거 문서에는 구 URL (`.../radio/8010/radio.mp3`, 릴레이 `coderadio-relay-*.freecodecamp.org`)이 남아 있다. **하드코딩 금지**, API에서 `listen_url` / `mounts` / `remotes`를 읽어 쓰는 편이 안전하다.

### 2.2 Now Playing API에서 쓸 필드

AzuraCast `nowplaying` JSON의 주요 필드:

- `is_online` — 방송 가능 여부
- `now_playing.song.title` / `artist` / `album` / `art`
- `now_playing.elapsed` / `remaining` / `duration` — 진행 표시(선택)
- `playing_next.song.*` — 다음 곡(선택)
- `listeners.current` — 청취자 수(선택)
- `station.listen_url`, `station.mounts[]`, `station.remotes[]` — 실제 재생 URL

실시간 갱신 방식 후보:

1. **HTTP 폴링** (간단, 구현 쉬움) — 예: 10~30초 간격
2. **WebSocket** — 과거 사이트는 `wss://.../api/live/nowplaying/coderadio` 형태를 사용. 트래픽·지연은 유리하나 재연결·프로토콜 버전을 관리해야 함

권장: MVP는 HTTP 폴링 + URL은 API에서 동적 해석. WebSocket은 이후 최적화.

### 2.3 스트림 특성

- 포맷: Icecast 스타일 **연속 MP3 HTTP 스트림**
- 비트레이트: 128 / 64 kbps
- 버퍼·재연결: 네트워크 끊김 시 자동 재시도 필요
- User-Agent: 일부 CDN/프록시가 빈 UA를 거부할 수 있음 → 앱 식별 UA 권장
- HTTPS만 사용

### 2.4 법적·정책

- 음악 저작권·라이선스는 freeCodeCamp / Code Radio 측 정책에 따름
- **비공식 클라이언트**이므로 과도한 요청(초단위 폴링, 다중 동시 스트림) 지양
- README에 출처 명시, 공식 사이트 링크, “unofficial” 표기
- 스트림 URL을 재배포용으로 미러링하지 말 것 (클라이언트에서만 연결)

---

## 3. 크로스 플랫폼 트레이(메뉴바)

OS마다 “트레이” 의미가 다르다.

| OS | UI 위치 | 주의점 |
|----|---------|--------|
| Windows | 시스템 트레이 (알림 영역) | 아이콘 숨김, 고DPI, 다크 모드 아이콘; 좌/우클릭 구분 용이 |
| macOS | 메뉴바 | 라이트/다크용 **템플릿 이미지**; 기본은 클릭=메뉴라 **좌클릭 토글**을 커스텀으로 구현해야 함 |
| Linux | StatusNotifier / AppIndicator / 레거시 XEmbed | 데스크톱(GNOME/KDE/etc.)마다 동작 차이; 클릭 동작·커스텀 팝업 위치 편차 |

### 3.1 Linux 지원 수준과 테스트 현실

**완전히 불가능하지는 않지만, Win/mac와 100% 동일한 UX를 모든 배포판에서 보장하기는 어렵다.**

| 측면 | Windows / macOS | Linux |
|------|-----------------|-------|
| 트레이 API | 비교적 일관 | StatusNotifier vs AppIndicator vs 레거시, DE마다 다름 |
| GNOME | — | 기본 셸은 트레이를 약하게 취급; Extension 필요할 수 있음 |
| KDE / XFCE / Cinnamon | — | 대체로 트레이·커스텀 팝업이 잘 동작 |
| 좌클릭 / 우클릭 | Qt로 대체로 제어 가능 | 일부 indicator 경로는 클릭 구분이 제한적 |
| 단독 빌드 | exe / .app | AppImage·onedir; 트레이 관련 시스템 라이브러리 이슈 가능 |

#### 이 프로젝트의 Linux 현실 (합의)

메인 개발자가 Linux를 일상 사용하지 않으므로:

| 항목 | 방침 |
|------|------|
| 개발 | 코드 경로·빌드 스크립트·조건부 분기는 **시도·유지**한다 |
| 런타임 테스트 | **제한적** — 여러 DE를 직접 설치·검증하는 것은 기대하지 않음 |
| 지원 등급 | Windows / macOS = 주력 검증, Linux = **best-effort (커뮤니티·CI 보조)** |
| DE 매트릭스 | GNOME/KDE/XFCE/… 전부 QA 약속하지 않음. 이슈 제보 시 수정 우선순위만 둠 |
| 문서 | README + [`docs/linux-best-effort.md`](linux-best-effort.md) (Ubuntu 스모크 절차 포함) |

실무적 완화:

- CI에서 Linux **헤드리스/최소** 빌드·단위 테스트는 가능해도, 트레이 GUI 클릭은 CI로 대체 불가에 가깝다
- 가능하면 단일 VM 한 종류(예: Ubuntu 기본)만 스모크하는 선택지는 열어 두되, **필수 게이트는 아님**
- **재생·메타데이터·단독 실행** 코드는 OS 공유, **트레이/팝업 폴리시**는 플랫폼별 분기 + 알려진 제한 문서화

즉 Linux를 버리지는 않되, **‘전 DE 동등 QA’는 범위 밖**으로 둔다.

### 3.2 왜 pystray가 아니라 Qt인가 (트레이 근처 비모달 팝업)

핵심은 “메뉴를 꾸미느냐”가 아니라 **누가 창을 그리는가**다.

```text
[원하는 UX]
  좌클릭  → Play/Pause (메뉴 없이 즉시)
  우클릭  → 트레이 아이콘 근처에 작은 패널
            (곡명, 볼륨 슬라이더, Quit…)
            바깥 클릭 시 닫힘 = 비모달 팝업
```

#### pystray가 하는 일

- OS에 **트레이 아이콘**을 올리고, 대부분 **네이티브 컨텍스트 메뉴**(`QMenu`가 아닌 OS 메뉴)를 붙인다.
- 메뉴 항목은 “텍스트 / 체크 / 서브메뉴 / 클릭 콜백” 정도만 가능한다.
- **볼륨 슬라이더, 임의 레이아웃, 앨범 아트, 커스텀 패딩** 같은 위젯을 메뉴 안에 넣을 API가 없다.
- 좌클릭 동작도 백엔드(Win/mac/Linux)마다 다르고, “좌클릭=토글, 우클릭=우리가 그린 창”을 일관되게 만들기 어렵다.
- 별도 Tk/Qt 창을 **억지로** 띄울 수는 있으나:
  - 트레이 아이콘 좌표를 pystray가 안정적으로 안 주는 경우가 많음
  - 이벤트 루프가 두 개(pystray 스레드 + GUI 프레임워크)로 쪼개져 충돌·종료 이슈가 잦음
  - “가벼운 pystray” 이점이 사라지고, **반쯤 직접 만든 트레이 앱**이 됨

정리: pystray = **아이콘 + OS 메뉴 헬퍼**.  
“트레이 근처 커스텀 비모달 패널”은 제품 목표가 라이브러리 목표와 어긋난다.

#### Qt(`QSystemTrayIcon` + `QWidget`)가 하는 일

- 같은 프로세스·같은 이벤트 루프에서:
  - 트레이 아이콘 (`QSystemTrayIcon`)
  - **일반 창/위젯** (슬라이더, 라벨, 버튼)
  - 클릭 시그널 (`activated`: Trigger / Context / DoubleClick …)
- 우클릭 시 `QMenu` 대신 **작은 `QWidget`을 `show()`** 하면 그게 곧 커스텀 팝업이다.
- 창 플래그로 트레이 UX에 맞춘다:
  - `Qt.Popup` 또는 유사한 플래그 → 포커스 잃으면 닫히는 **비모달** 동작
  - `FramelessWindowHint` → 테두리 없는 패널 느낌
  - `geometry` / 커서 위치 / (가능하면) 트레이 rect 기준으로 **아이콘 근처에 배치**
- 좌클릭은 `Trigger`에서 재생 토글만 하고 창을 안 띄우면 된다.
- 단독 빌드 시 Qt 라이브러리를 같이 묶어야 해서 **용량은 pystray보다 큼** — 그 대가로 UI 요구를 정석으로 충족.

```text
pystray 경로 (비권장 for this UX)
  Tray icon ──► OS context menu (텍스트 항목만)
                 └─ 커스텀 패널? → 다른 GUI + 좌표/루프 해킹

Qt 경로 (권장)
  QSystemTrayIcon.activated
       ├─ left  → player.toggle()
       └─ right → PopupWidget.move(near_tray).show()
                    └─ QSlider / QLabel / QPushButton …
```

#### “모달”이 아닌 이유 (용어)

사용자가 말한 커스텀 팝업은 보통 다음을 뜻한다.

| 용어 | 의미 | 이 앱에 맞는가 |
|------|------|----------------|
| OS 컨텍스트 메뉴 | 우클릭 시스템 메뉴 | 슬라이더 불가 → 부족 |
| **비모달 팝업** | 작은 창, 다른 앱 작업 가능, 바깥 클릭 시 닫힘 | **목표** |
| 모달 다이얼로그 | `exec()`로 앱/입력을 막을 수 있음 | 트레이 유틸에 부적합 |

Qt로 간다는 말은 Electron으로 가자는 뜻이 아니라, **이미 필요한 ‘창’을 그릴 수 있는 GUI 툴킷 하나로 트레이까지 통일**하자는 뜻이다.

| 라이브러리 | 한 줄 평가 |
|------------|------------|
| **pystray** | 가볍지만 메뉴형 UI용. 본 요구와 불일치 |
| **PySide6 / PyQt6** | 좌·우클릭 + 커스텀 비모달 팝업에 적합. 번들↑ |
| **wxPython** | 비슷하게 가능. 생태계·예시는 Qt 쪽이 더 흔함 |

**좌클릭=토글 + 우클릭=트레이 근처 커스텀 팝업**이면 **Qt 트레이**가 맞고, pystray는 MVP 후보에서 제외한다.

### 3.3 커스텀 팝업 구현 난이도

**가능하고, 난이도는 중(中) — 컨텍스트 메뉴보다 한 단계, 프로젝트 전체를 뒤집지는 않음.**

| 방식 | 난이도 | 내용 |
|------|--------|------|
| OS 컨텍스트 메뉴만 | 낮음 | 항목·체크만; 슬라이더·아트 제한 |
| **커스텀 팝업 창** (`QWidget` frameless, 트레이 근처 배치) | **중** | 볼륨 슬라이더, 곡명, 버튼 자유 배치 |
| 진짜 앱 모달 다이얼로그 | 중~높음(UX상 비권장) | 코딩 흐름을 막음 |

구현 포인트:

- `QSystemTrayIcon.activated` → `Trigger`에서 play/pause, `Context`에서 팝업 `show`
- `Qt.Popup` / `FramelessWindowHint` + 아이콘·커서 근처 좌표
- macOS 메뉴바 클릭 관례와 충돌 여부 검증
- 멀티모니터에서 팝업이 화면 밖으로 나가지 않게 clamp
- 난이도 증가분: 레이아웃·위치·포커스. 오디오/스트림·패키징보다 보통 작음

권장: **우클릭 → 작은 비모달 팝업**(곡 정보 + 볼륨 슬라이더 + Quit). 좌클릭은 토글만.

### 3.4 프로세스·수명

- 메인 윈도우 없이 트레이만 두는 “background app” 형태
- macOS: Dock 아이콘 숨김 여부 (`LSUIElement` / info.plist) 결정
- Windows: 작업 표시줄에 안 뜨게 (트레이만)
- 단일 인스턴스(이미 실행 중이면 포커스/무시) 권장
- 종료 시 오디오 스레드·네트워크·아이콘 정리 (좀비 프로세스 방지)

---

## 4. 오디오 재생 백엔드

Python에서 Icecast MP3 스트림을 안정적으로 재생하는 것이 핵심 난제다.

### 4.1 후보 비교

| 방식 | 예 | 장점 | 단점 |
|------|----|------|------|
| 외부 플레이어 제어 | **mpv** (`python-mpv` 또는 subprocess) | 스트림·재연결·볼륨 검증됨, CLI로도 검증 가능 | 런타임에 mpv 바이너리 필요(또는 번들) |
| VLC 바인딩 | **python-vlc** | 스트리밍 강함 | VLC 설치/번들 필요, 라이선스 고지 |
| 순수 Python + 디코더 | `miniaudio`, `pyaudio` + `pymad` 등 | 외부 플레이어 없음 | 구현·버퍼·재연결·코덱을 직접 책임 |
| GStreamer | `gi` / gst-python | Linux에 자연스러움 | Windows/macOS 패키징 복잡 |
| sounddevice + 직접 decode | — | 세밀 제어 | 난이도·유지비 높음 |

### 4.2 권장

**1순위: mpv를 백엔드로 사용**

- 커뮤니티에서 Code Radio를 `mpv <stream-url>`로 재생하는 사례가 많음
- 볼륨·mute·pause IPC가 명확 (`--input-ipc-server` 또는 libmpv)
- 배포 시 (단독 빌드 제약):
  - **개발**: 시스템 mpv로 스파이크·디버깅 가능
  - **배포**: mpv(또는 libmpv)를 **앱 산출물에 동봉** — 사용자에게 별도 mpv 설치를 요구하지 않음
  - 동봉이 어려운 OS만 예외적으로 문서화하되, 목표는 “추가 런타임 없이 실행”

대안: python-vlc — VLC 전체를 번들하면 용량이 커져 단독 배포 부담이 큼. 가능하면 mpv 쪽이 유리.

### 4.3 재생기 추상화

플랫폼·백엔드 교체를 위해 인터페이스를 두는 것이 좋다.

```text
RadioPlayer
  play(url) / pause() / resume() / stop()
  set_volume(0..100) / get_volume()
  is_playing() / on_error(callback)
```

구현체: `MpvPlayer`, (나중) `VlcPlayer` 등.

### 4.4 스레딩

- UI(트레이) 스레드와 오디오/네트워크 스레드 분리
- Qt 슬롯/시그널에서 블로킹 HTTP·디코드를 하지 말 것
- 상태(재생 중, 곡명, 볼륨)는 단일 소스(앱 상태 객체)에서 갱신 후 팝업·아이콘 갱신

---

## 5. 아키텍처 스케치

```text
┌─────────────────────────────────────────┐
│                 App Core                │
│  state: playing, volume, track, url     │
├─────────────┬─────────────┬─────────────┤
│ Tray / Popup│  Metadata   │   Player    │
│  (PySide6)  │  (HTTP poll │  (mpv/…)    │
│             │   / WS)     │             │
└─────────────┴─────────────┴─────────────┘
         │            │            │
         ▼            ▼            ▼
   OS tray API   AzuraCast API   Icecast MP3
```

권장 패키지 구조(초안):

```text
coderadio_tray/
  __init__.py
  __main__.py          # python -m coderadio_tray
  app.py               # 수명주기·DI
  config.py            # 설정 경로·기본값
  metadata/
    client.py          # nowplaying API
  player/
    base.py
    mpv_player.py
  ui/
    tray.py            # QSystemTrayIcon, 좌/우클릭
    popup.py           # 커스텀 팝업 위젯
  resources/
    icons/             # tray icons
```

설정 저장 위치:

- Windows: `%APPDATA%\coderadio-on-tray\`
- macOS: `~/Library/Application Support/coderadio-on-tray/`
- Linux: `~/.config/coderadio-on-tray/`

저장 항목 예: volume, bitrate, last stream mount, autostart, poll interval.

---

## 6. UX 디테일

### 6.1 입력 매핑 (필수)

| 입력 | 동작 |
|------|------|
| 트레이 **좌클릭** | Play / Pause 토글 |
| 트레이 **우클릭** | 커스텀 팝업 표시 |
| 팝업 바깥 클릭 / Esc | 팝업 닫기 (재생 상태는 유지) |

macOS 메뉴바는 플랫폼 관례가 “클릭=메뉴”이므로, 좌클릭 토글을 넣을 때 우클릭(또는 Option+클릭) 팝업과의 역할을 문서·툴팁으로 명확히 한다. 필요 시 macOS만 “클릭=팝업, 팝업 내 Play/Pause”로 완화하는 옵션을 검토한다.

### 6.2 커스텀 팝업 초안

```text
┌─────────────────────────────┐
│  Artist — Title             │
│  ▶/❚❚   [═══════●──] vol    │
│  128k ▾   Open site…  Quit  │
└─────────────────────────────┘
```

강제 모달(`exec`)보다 **트레이 앵커 팝업**이 적합하다. 긴 곡명은 truncate + 툴팁.

### 6.3 아이콘 상태

- idle / playing / error(오프라인·네트워크) 구분
- macOS 템플릿 아이콘 vs 컬러 아이콘 전략 분리
- freeCodeCamp 브랜드 로고 무단 사용 주의 → 독자 아이콘 또는 허가된 자산

### 6.4 오류 UX

- 스트림 실패: 팝업에 “Reconnect…” / 자동 재시도(지수 백오프)
- 메타데이터 실패: 재생은 유지, 곡명만 “Unknown” 또는 마지막 값 유지
- `is_online == false`: 재생 중단 + 안내

### 6.5 접근성·입력

- 전역 핫키는 OS별 권한(macOS Accessibility 등) 이슈 → MVP 이후
- 미디어 키 연동도 OS별로 API가 다름 → 별도 마일스톤

---

## 6A. FAQ — 언어·플랫폼·UI

### Q1. Python이 이 프로젝트에 부적합한가?

**아니요. 적합하다.** 다만 “최적의 유일한 선택”은 아니다.

| 관점 | 평가 |
|------|------|
| 트레이 + 작은 UI + HTTP + 서브프로세스(mpv) | Python·Qt로 충분히 일반적 |
| 단독 빌드 | PyInstaller 등으로 가능. 용량·시작시간·백신 오탐은 감수 |
| 배터리·메모리 | 브라우저보다 훨씬 가볍고, Go/Rust 네이티브보다는 무거울 수 있음 |
| 대안 | Tauri/Electron(웹 UI), Go+systray, Swift/C# 네이티브 — 각각 트레이·번들 이슈는 비슷 |

부적합 신호에 가까운 경우: 극단적 용량(<15MB)·초저지연 UI·OS별 완벽 네이티브 메뉴바 API가 최우선일 때.  
현재 요구(스트리밍 유틸 + 단독 배포 + 커스텀 팝업)에서는 **Python 유지가 합리적**이다.

### Q2. Linux에서 타 OS와 동등한 경험이 어려운가?

**픽셀·DE 단위 동등은 어렵고, 기능 코드 공유는 가능하다.**  
메인 개발자가 Linux를 상시 쓰지 않고 DE 매트릭스 QA도 하지 않으므로, Linux는 **best-effort**로 둔다(§3.1). 빌드·플랫폼 분기는 유지하되 런타임 보증은 Win/mac 우선.

### Q3. 좌클릭 재생/정지, 우클릭 메뉴?

**필수 요구로 채택.** §6.1. 구현은 Qt `QSystemTrayIcon.activated`가 정석.

### Q4. 커스텀 팝업이 가능한가? 난이도가 많이 올라가나? 왜 Qt인가?

**가능. 난이도 중.** pystray는 OS 메뉴용이라 슬라이더형 비모달 패널과 안 맞고, Qt는 같은 루프에서 트레이+위젯 창을 연다. 상세 비교는 **§3.2**.

---

## 7. 의존성·런타임

### 7.1 Python 버전

- **3.11+** 권장 (타입 힌트·패키징·윈도우 호환)
- 3.14 등 최신만 타겟하지 말고, CI에서 3.11/3.12 검증

### 7.2 패키지 관리

후보: `uv` / `poetry` / `hatch` + `pyproject.toml`  
권장: `pyproject.toml` 표준 + lockfile.

필수에 가깝게 둘 것:

- 트레이: PySide6 (또는 PyQt6)
- HTTP: `httpx` 또는 `urllib` (표준만으로도 가능)
- 설정: `tomllib` / JSON
- 플레이어: mpv 바인딩 또는 subprocess 래퍼

네이티브 확장·바이너리(mpv)는 **배포 산출물에 번들**하는 것을 기본으로 한다. 시스템 전역 설치에만 의존하는 배포는 하드 제약에 맞지 않는다.

### 7.3 가상환경·개발

```text
uv sync / pip install -e .
python -m coderadio_tray
```

Windows에서 콘솔 창 없이 실행: `pythonw` 또는 패키저 `windowed`/`noconsole`.  
개발용 소스 실행과 **릴리스용 단독 빌드**는 CI/스크립트로 분리한다.

---

## 8. 패키징·배포

**필수:** 사용자는 Python(및 pip/venv) 없이 배포물을 실행할 수 있어야 한다.  
개발자는 소스에서 Python으로 돌리고, CI 또는 릴리스 스크립트가 OS별 단독 산출물을 만든다.

| 도구 | 비고 |
|------|------|
| **PyInstaller** | 우선 후보. Python 인터프리터·의존성 동봉. onedir 권장(시작 속도·안티바이러스 오탐) |
| Briefcase (BeeWare) | 네이티브 앱 번들 지향 |
| cx_Freeze / Nuitka | 대안. Nuitka는 바이너리화에 유리할 수 있으나 빌드 복잡 |
| OS 패키지 | winget / Homebrew cask / Flatpak — 후순위(여전히 내부는 단독 바이너리 권장) |

고려점:

- 산출물 형태 예:
  - Windows: `CodeRadioTray/` 폴더 + `CodeRadioTray.exe` (zip) 또는 설치 프로그램
  - macOS: `Code Radio Tray.app` (dmg/zip)
  - Linux: AppImage 또는 압축된 onedir
- **onefile** vs **onedir**: onefile은 배포 파일 하나는 편하지만 임시 폴더 풀이·시작 지연·백신 오탐이 잦음 → MVP는 **onedir** 우선
- mpv/libmpv·필요 DLL/dylib/so를 **같은 번들 안**에 포함. `sys._MEIPASS` 등 패키저 리소스 경로로 로드
- “시스템에 mpv만 설치하면 됨” 같은 안내만으로는 **제약 미충족**
- 용량: Python 런타임 + Qt + mpv 동봉 시 수십 MB 이상은 감수. 목표 용량을 문서에 적어 두면 좋음(예: Windows onedir < 100MB)
- 코드 서명: macOS Gatekeeper, Windows SmartScreen — 개인 프로젝트면 초기에 unsigned + 안내
- 자동 업데이트: 없으면 GitHub Releases 링크만으로도 MVP 충분
- CI: OS별 매트릭스로 빌드 아티팩트 업로드 (Python은 빌드 머신에만 존재)

---

## 9. 테스트·품질

- 단위: 메타데이터 JSON 파싱, 볼륨 clamp, URL 선택 로직
- 통합: API live 호출은 네트워크 flaky → 픽스처 JSON으로 기본, 선택적 live 테스트
- 수동: **Windows / macOS**에서 트레이·팝업·절전 복귀·재연결 중심 검증
- Linux: 빌드·단위 테스트 위주; GUI 런타임은 best-effort(DE 전부 설치·검증은 범위 밖)
- **단독 빌드 검증**: Python·mpv가 PATH에 없는 환경에서 릴리스 산출물만으로 확인 (주력 OS)
- 리소스: 브라우저 대비 CPU/RAM이 확실히 낮은지 스모크 확인 (프로젝트 존재 이유)

---

## 10. 보안·프라이버시

- 외부 연결: AzuraCast API + 선택한 스트림 호스트만
- 텔레메트리 없음(기본)
- 설정 파일에 비밀정보 불필요
- HTTPS 인증서 검증 유지
- 의존성 pin / 공급망: lockfile + 최소 의존

---

## 11. 리스크·오픈 이슈

| 리스크 | 영향 | 완화 |
|--------|------|------|
| API/호스트 URL 변경 (admin → v2 사례) | 재생·메타 전부 | URL 하드코딩 최소화, API 우선 |
| 릴레이 목록 비어 있음 | 지연 최적화 불가 | 기본 listen_url만으로도 MVP 가능 |
| Linux 트레이·DE 편차 | 아이콘/클릭 이상 | best-effort, README 고지, 이슈 기반 수정 |
| 번들 mpv 누락·경로 오류 | 단독 빌드에서만 재생 실패 | 패키저 datas/binaries 검증, 스모크 테스트 |
| PyInstaller 오탐·서명 없음 | 실행 차단 | onedir, 릴리스 해시 공개, 서명(여유 시) |
| 절전·네트워크 전환 | 무음·멈춤 | 재연결·헬스체크 |
| 비공식 클라이언트 정책 변화 | 사용 중단 가능 | 공식 고지 준수, 정중한 User-Agent |
| 상표·아이콘 | 브랜딩 이슈 | 자체 아이콘, “unofficial” |

결정이 필요한 질문:

1. 단독 빌드 형태는 **zip/onedir** 인가, **설치 프로그램(.msi / .dmg)** 인가?
2. 메타데이터는 **폴링**만으로 충분한가?
3. 1차 타겟 OS 우선순위는? (예: Windows 우선 → macOS)
4. macOS에서 좌클릭=토글을 **그대로** 강제할지, 플랫폼 관례에 맞춰 완화할지?

이미 닫힌 결정:

- 배포는 **Python 미설치 단독 빌드**가 필수다.
- 오디오 백엔드(mpv 등)도 **번들**이 기본이다.
- **좌클릭 = Play/Pause**, **우클릭 = UI 호출**.
- UI는 OS 컨텍스트 메뉴가 아니라 **트레이 근처 비모달 커스텀 팝업** → **Qt(PySide6)**, pystray 제외.
- **Linux**는 개발·빌드는 시도하되, 런타임/DE 매트릭스 QA는 **best-effort**(메인 개발자 일상 미사용).

---

## 12. 제안 기술 스택 (초안)

합의가 없으면 아래를 기본안으로 둔다.

| 영역 | 선택 |
|------|------|
| 언어 | Python 3.11+ |
| UI / 트레이 | **PySide6** `QSystemTrayIcon` + 커스텀 팝업 `QWidget` |
| 재생 | mpv (subprocess IPC 또는 python-mpv), **번들** |
| HTTP | httpx |
| 설정 | JSON in OS config dir |
| 패키징 | PyInstaller **onedir** (Python·Qt·mpv 동봉, windowed/noconsole) |
| 문서 | 이 `docs/` + README |

좌클릭 토글·커스텀 팝업 요구를 만족하면서도 스트림 재생·단독 배포가 가능한 조합이다.  
번들 용량은 pystray만 쓸 때보다 커진다(Qt 비용). 사용자에게는 여전히 **압축 해제 후 실행**이면 된다.

---

## 13. 구현 마일스톤 (참고)

1. **Spike**: mpv로 v2 스트림 재생 + nowplaying JSON 파싱 스크립트
2. **Core**: `RadioPlayer` + metadata client + 설정
3. **Tray MVP**: 좌클릭 토글, 우클릭 커스텀 팝업(볼륨·곡명·Quit)
4. **Robustness**: 재연결, 오프라인, 단일 인스턴스, 멀티모니터 팝업 위치
5. **Polish**: 아이콘 상태, bitrate, Linux DE 제한 문서화, README
6. **Standalone release**: OS별 PyInstaller(onedir) + Qt·mpv 번들, Python 없는 PC 스모크
7. **Optional**: 핫키, OS 미디어 연동

---

## 참고 링크

- Code Radio: https://coderadio.freecodecamp.org/
- Now Playing API (v2): https://coderadio-admin-v2.freecodecamp.org/api/nowplaying/coderadio
- Stream 128k: https://coderadio-admin-v2.freecodecamp.org/listen/coderadio/radio.mp3
- freeCodeCamp — VLC로 듣기: https://www.freecodecamp.org/news/play-code-radio-on-vlc/
- AzuraCast Now Playing API 개념: https://www.azuracast.com/docs/developers/now-playing-data/

---

*문서 작성일: 2026-07-24. API 호스트는 변경될 수 있으므로 구현 전 엔드포인트를 재확인한다.*
