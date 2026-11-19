## 2026-11-19 17:05 — AIK24-TOOLDEDUP-01 완료 — /tools 중복 5건 삭제 + ChatPDFGPT 게재 해제

### 한 일
1. `/tools` 목록 소스(md 567건 + D1 `tool_submissions` published 39건 − md 중복 슬러그)를 전수 대조해 **같은 제품이 2번 등록된 5쌍**을 확정하고, 대표님 선택("내용이 정확한 쪽 유지")에 따라 각 쌍의 1건씩을 삭제했다.
   - 삭제(5): `omlx-ai` · `freebeat-ai` · `edgee-claude-code-compressor-v2` · `ifttt-ai` · `make0-brain-oss`
   - 유지(5): `omlx` · `freebeat-ai-app` · `edgee-mod-for-claude-code` · `new-ai-tools-by-ifttt` · `make0-brain`
2. 삭제 도구 신규 작성 `scripts/delete_tool_entry.py` — dry-run 기본, 백업 JSON 선작성, 4중 거부조건(published/pending submission 존재 · `/tools/<slug>` 참조 존재 · 슬러그 형식 · 파일 부재), apply 후 재조회 검증, `--restore` 지원.
3. ChatPDFGPT(D1 `tool_submissions` id 75)를 하드 삭제 대신 `status='retired'` + `rejection_reason` 기록으로 게재 해제(대표님 선택).
4. 배포 후 라이브 검증까지 수행.

### 결과 (검증 근거)
- [검증됨] **로컬 자산 감소**: md 567 → 562, D1 `tools` 661 → 656. 근거 — 도구가 apply 후 재조회로 출력한 `after: md=562 tools=656 submissions={'published': 38, 'retired': 33}`, 그리고 `git status --porcelain src/content/tools/` 에서 5건 `D` 표시.
- [검증됨] **삭제 대상 잔존 0 / 재생성 0**: md 파일 5개 및 `chatpdfgpt.md` 부재 확인(`test -f` → absent), `tools` 테이블 재조회 결과 0행(도구 내 verify 단계 `검증: OK`). 배포 스크립트가 도는 `sync_submissions_to_md.mjs` 실행 후에도 재생성되지 않음.
- [검증됨] **라이브 목록**: `https://aikorea24.kr/tools/` 카드 수 570 → **564**. 산출 근거 — 이전 570 = md 567 + D1 전용 카드 3(makeasong·youtranscripts·chatpdfgpt), 이후 564 = md 563(562 + 배포 sync가 만든 makeasong.md) + D1 전용 1(youtranscripts). `data-name` 카드 564개·고유 564개로 중복 0.
- [검증됨] **이름 단위 확인**: 라이브 HTML에서 `Omlx AI`·`freebeat AI`·`Edgee Claude Code Compressor V2`·`IFTTT.ai`·`Make0 Brain OSS`·`ChatPDFGPT` 각 0회, `oMLX`·`Freebeat.ai App`·`Edgee Mod for Claude Code`·`New AI tools by IFTTT`·`Make0 Brain` 각 1회.
- [검증됨] **URL 상태**: 유지 5건은 200(`/tools/omlx/`, `/tools/freebeat-ai-app/`, `/tools/edgee-mod-for-claude-code/`, `/tools/new-ai-tools-by-ifttt/`, `/tools/make0-brain/`), 삭제 5건 + `chatpdfgpt` 는 404.
- [검증됨] **배포**: `bash scripts/deploy.sh` 성공(Version ID `2ea8d567-d66b-4c8b-8e11-f2572a15cb43`), sitemap ping google/naver true.
- [검증됨] **기존 테스트 회귀 없음**: `.venv/bin/python3 -m pytest tests/test_pipe09_tools_collector_guard.py -q` → 28 passed. (28 = 해당 파일 전체 테스트 수)
- [부분검증] **백업/복원**: 백업은 `scripts/logs/backup_tool_delete_20261119_170157.json`(58,035 bytes, md 전문 + `tools` 행 원본 + retire 이전 status + before 카운트)로 실재 확인. 제한 사유 — `--restore` 경로는 코드 리뷰까지만 했고 실제 복원 실행으로 검증하지 않았다(D1에 다시 쓰는 왕복 시험이 필요해 이번엔 미실행).

### 관측 (본 작업과 무관)
- 세션 중 D1 `tool_submissions` 상태가 `published 39 / retired 30 / pending 2` → `published 39 / retired 32 / pending 0` 으로 바뀐 것을 확인했다. 본 작업은 id 75만 수정했고 dry-run 단계에서도 쓰기가 없었으므로, 다른 주체(관리자 처리 또는 스케줄 작업)의 변경으로 보이나 **원인은 미확인**.

### 잔존 위험
1. **중복 재발 경로가 그대로다.** `scripts/tools_collector.py` 의 중복 검사는 md 파일의 슬러그·이름 **정확 일치**만 본다(`get_existing_tool_names()` 1100–1121, 배치 판정 1678–1685). 이번에 지운 이름(oMLX·freebeat AI·IFTTT.ai·Make0 Brain OSS 등)을 수집기가 다른 표기로 다시 만나면 재등록된다.
2. 삭제한 5개 URL 이 404 다. 검색 색인에 남아 있으면 외부 유입이 끊긴다. 301 리다이렉트 매핑은 넣지 않았다.
3. D1 변경(`tools` 5행 DELETE, submission 1행 retire)은 git 이력에 남지 않는다. 복구는 위 백업 JSON 의 `--restore` 뿐이고, 그 경로도 실측 검증 전이다.
4. `tools` 테이블과 md 는 별도 사본인데, 두 곳을 동기화하는 주체가 저장소 코드에 없다(`INSERT INTO tools` 쓰기 코드 0건). 다음에 md 만 고치거나 `tools` 만 고치면 불일치가 재발한다.
5. 배포마다 `sync_submissions_to_md.mjs` 가 published submission → md 를 자동 생성한다. 즉 앞으로 특정 도구를 목록에서 빼려면 **md 삭제만으로는 부족**하고 submission 을 retire 해야 한다(이번 ChatPDFGPT 가 그 사례).
6. 근거 부족으로 **보류한 후보 3건**: `github-copilot` vs `github-copilot-fusion`(URL 없음·별칭), `temp-mail` vs `tempmail-bot`(서로 다른 도메인), legacy `tools` #107 `claude-code-tool` vs md `claude-code`(동일 이름·동일 URL이지만 `/tools` 그리드에는 legacy 테이블이 쓰이지 않아 목록 중복은 아님).
7. `huggingface.co/papers` 류 논문 항목 다수가 **같은 안내문 본문**을 공유한다(서로 다른 논문이라 중복 등록은 아님). 목록 품질 문제로 남는다.

### 다음 행동
1. `tools_collector.py` 중복 판정에 브랜드 정규화(공백·`AI`/`.ai`/`App` 접미 제거 후 비교) 추가 — 이번 5쌍은 모두 정확 일치 검사로는 걸리지 않는 변형이었다.
2. 삭제 URL → 유지 URL 301 매핑을 `src/pages/tools/[id].astro` 에 추가할지 결정.
3. 보류 3건 판정, legacy `tools` #107 정리 여부 결정.
4. `makeasong.md`(배포 sync 산출물, 448 bytes·본문 없음) 커밋 여부 정리.
