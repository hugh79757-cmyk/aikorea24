# 2026-09-23 Compass 파이프라인 연결 + 발행 다양성

## 목적
- compass 모드를 실제 발행 경로(main_v3.py)에 연결
- Pass 1 카테고리 분류 tech 쏠림(100%) 해결
- compass 발행 스케줄러 등록

## 결과
| 항목 | 결과 |
|------|------|
| main_v3.py --format compass | ✅ 연결 완료 (e9d1ccf7) |
| Pass 1 카테고리 개선 | ✅ tech 100%→25% (b4d88440) |
| launchd plist | ✅ kr.aikorea24.threads-compass 로드됨 |
| 실제 발행 테스트 | ❌ D1/네트워크 크롤링 차단 (29자 본문) |
| compass_dryrun 배치 | ✅ 8/10 성공 |
| fact_gate dead code | ✅ 제거 (353→272라인) |

## 미해결
- main_v3.py 기사 크롤링 29자 차단 — 네트워크/D1 문제 (compass 모드 발행 불가)
- `*.plist` git 추적 불가 (gitignored)
- D-mode plist CLOUDFLARE_API_TOKEN 하드코딩 (공통 보안 이슈)

## 커밋
- 9e0daa62, e9d1ccf7, b4d88440
