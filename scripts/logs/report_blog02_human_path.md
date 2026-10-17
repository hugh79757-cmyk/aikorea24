## 2026-10-17 21:17 — AIK24-BLOG-02 (사람이 쓰는 경로로 재작성 — 발행 글 8건 + 규칙·도구)

### 한 일

- 대표님 지적: 발행 글의 사용법이 실사용자가 아니라 에이전트 기준으로 쓰였다(명령줄 `opencode run -m ...` 중심). 실제 사용자는 대화형 화면의 모델 선택 창에서 모델을 고른다.
- TUI 사실관계 실측 — 로컬 설치본 `~/.opencode/bin/opencode`(v2.0.32) 바이너리 문자열:
  - `model_list: <leader>m` (leader 기본값 `ctrl+x`), `model_favorite_toggle: ctrl+f`, `model_cycle_recent: f2`, `model_cycle_recent_reverse: shift+f2`
  - 슬래시 명령 `models` (제목 "Switch model", 구현 `model.list` → 대화상자 제목 "Select model")
  - 대화상자 하단 `ctrl+a`(Connect an integration) / `ctrl+f`(Favorite), `esc` 로 닫기
  - 모델 줄 오른쪽 열에 `Free` 라벨(대표님 화면 캡처와 일치), 무료 모델 우선 정렬 비교식 확인
  - `opencode auth list`: Kilo 는 `KILO_API_KEY` 필요(통합 목록에 존재), OpenCode(Zen) 제공자는 자격 항목 없음 — 키 없이 목록에 뜬다.
- 규칙 반영: `scripts/blog_writing_rules.md` §C 에 2줄 추가(① 설치·연결·모델 선택은 사람이 화면에서 하는 경로가 본문 1순위, 명령줄 호출은 재현용 측정 섹션에서만 ② 선택 창 경로 절차), `.claude/skills/aik24-blog-writing/SKILL.md` 동일 반영.
- 발행 글 편집 8건 — 블록 구간만 교체(전체 재작성 없음):
  - `free-model-nvidia-nemotron-3-5-lightning` / `-ultra` / `free-model-liquid-lfm-2-5` / `free-model-dots-3-note-preview` / `free-model-cohere-north-mini-code` 5건: "무료로 사용하는 방법" 본문 재작성. CLI 호출 예시(`opencode run -m ...`) 제거 → `/models`(또는 `ctrl+x` 뒤 `m`) → Search `Free` → 오른쪽 `Free` 라벨 확인 → Enter, Kilo 키 연결 `ctrl+a`, 즐겨찾기 `ctrl+f`, 최근 모델 `f2`/`shift+f2`. 기존 사실은 보존 — `:free` 접미사 주의(ultra 유료판 입력 $0.50/100만 토큰, cohere 유료 항목), liquid 최대 출력 8,192 토큰, 2026-10-15 실측 문장.
  - `ll-alpha-free-12-question-eval`: ① 추론 강도 구간 코드블록(`opencode run -m opencode/ll-alpha-free#low ...`) → 선택 창 + `ctrl+t` 순환 + `#low` 표기 서술 ② "기본 모델로 지정"(설정 파일 먼저) → "자주 쓰는 모델로 고정하기"(`ctrl+f` 즐겨찾기 먼저, 설정 파일은 보조 1줄) ③ 마무리 "오늘 30분 안에 끝내는 3단계" → "LL Alpha Free 를 어디에 쓰면 좋은가"(쓰기 좋은 자리 4 · 넣지 말 자리 4 · 미검증 3).
  - `opencode-cli-guide`: §3 모델 선택 — `/model`(오기) → `/models`, Free 라벨·`ctrl+f`·`ctrl+a` 보강.
  - `free-models`(목록 페이지): 첫 화면에 선택 창 경로 1문장 삽입 + 생성기 `scripts/free_models_page.py` 에도 같은 문장 추가(다음 발행분에도 유지).
- 도구 신규: `scripts/emdash_section_replace.py` — 발행 글의 블록 구간만 마크다운으로 교체. `--section`(제목 기준)/`--anchor`/`--index` 범위 지정, 삽입 블록만 `_key` 재발급(기존 키 충돌 방지), 기본 dry-run, 백업 JSON → PUT + publish → 재조회 검증.

### 결과 (검증 근거)

- [검증됨] 편집 8건 전부 **라이브 반영** — 재조회(D1 본문 블록 텍스트)와 라이브 fetch(HTML 태그 제거 후 텍스트) 양쪽에서 새 문구 존재·옛 문구 0건.
  - 산출 근거: free-model 5건은 "OpenCode 를 실행한 뒤"·"ctrl+a" 존재, "CLI로 직접 호출할 수도" 0건·"opencode run -m" 0건. ll-alpha 는 "LL Alpha Free 를 어디에 쓰면 좋은가"·"자주 쓰는 모델로 고정하기" 존재, "opencode run -m" 0건·"오늘 30분 안에 끝내는 3단계" 0건. cli-guide 는 "프롬프트에서: /models 입력" 존재, "프롬프트에서: /model 입력" 0건. free-models 는 "Search 칸에 Free 를 입력" 존재.
  - 라이브 http: 7건 200(emdash.aikorea24.kr/posts/<slug>). D1 잔존 패턴 실측: `opencode run -m` 2건(Beam Free 재현용 측정 명령, free-models 검증 방법 서술 — 의도적 유지), `opencode run` 3건(+cli-guide 명령어 표), `--auto` 0건.
- [검증됨] 편집 중 슬러그·발행시각·제목 불변 — 각 적용 출력에서 `slug 불변: True / publishedAt 불변: True / 제목 유지: True`. 블록 수: lightning 41→43, ultra 44→46, liquid 47→49, dots 32→34, cohere 40→42, ll-alpha 56→63(3회 편집 누적), cli-guide 55→56, free-models 43→44.
- [검증됨] Beam Free 글(오늘 앞서 발행) 재작성 — 마무리 "어디에 쓰면 좋은가" + §6 `ai.kr.24 실측 결과`, 제목을 "OpenCode 모델 선택 창에서 Free 로 고르는 법…" 으로 교체, slug·publishedAt 보존, 블록 39→44, 라이브 200.
- [검증됨] 커밋 2건 — `b805fa99`(규칙·스킬·도구·gitignore), `2ef8fcd1`(목록 페이지 생성기). push 완료(pre-push 훅 YAML 검사 통과, `main...origin/main` 동기).
- [부분검증] 글에 남긴 `ctrl+t`(추론 강도 순환)·`#low` 표기·Kilo `:free` 주의는 기존 글의 서술을 옮긴 것 — 이번에 재실측하지 않았다(강도 순환 UI 는 바이너리에서 확인하지 않음).
- [부분검증] 규칙 파일의 프롬프트 주입은 이전 작업에서 실측(주입 True)했으나, 이번 2줄 추가 후 생성 파이프라인 e2e 발행으로는 확인하지 않았다.
- [검증불가] 선택 창에서 고른 모델이 세션을 넘어 유지되는지 — 확인 수단 없어 글에 쓰지 않았다.
- [위반 감지] 구간 교체 도구의 1차 적용(lightning)에서 검증 로직 결함을 발견 — 스팬(조각) 단위 `visible_strings` 로 블록 문구를 찾아 "새 문구 미반영"으로 잘못 판정했다(실제로는 반영됨, 블록 41→43). 블록 단위 `block_text` 비교로 고치고 재검증했다. 같은 결함 때문에 "옛 블록 텍스트 제거" 판정도 그 시점에는 항상 True 로 나오는 무의미한 통과였다.

### 잔존 위험

- 아래 항목들은 **미해결**이다.
  - `자체 하네스` 같은 내부 용어가 8건에 남아 있다(실측: `하네스` LIKE 8건 — ll-alpha, liquid, cohere 등). 사용법이 아니라 측정 방법 서술이라 이번에는 손대지 않았다.
  - `free-models` 의 방법론 문장은 "OpenCode CLI로 실제 호출" 그대로다 — 사용법이 아니라 검증 방법이라 유지.
  - 나머지 발행 글 1,492건(1,500 − 편집 8건)은 `opencode run -m` 패턴 기준으로만 전수 검사했고, 다른 형태의 에이전트식 서술은 별도 검사가 필요하다.
  - 편집 전 백업 JSON 9개 + 원고 9개가 `scripts/logs/` 에 있다(미커밋, `.gitignore` 등록). 복구는 파일명의 글 id 로 찾는다.
  - 규칙에 넣은 "사람 경로" 문장이 생성 글에 실제로 반영되는지는 다음 정기 발행분에서 확인해야 한다(미확인).

### 다음 행동

- 다음 정기 발행분(모델 리뷰·브리핑)에서 ① 선택 창 경로 서술 ② `## 마무리` 형식 ③ `aik24` 0건을 확인하고, 어긋나면 해당 글만 구간 교체 도구로 정정한다.
- 대표님 판단 대기: `free-models` 방법론 문구의 CLI 언급 유지 여부, `자체 하네스` 등 내부 용어 8건 정리 여부, 나머지 글 확대 검사 여부.
