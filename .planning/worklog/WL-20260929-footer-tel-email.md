# Worklog: WL-20260929-footer-tel-email

## Operation
1) 공통 푸터 전화 라벨/번호 표기 변경 (Meta 비즈니스 인식용)
2) Cloudflare Email Obfuscation 해제 → 이메일 일반텍스트 크롤 노출

## Pre-Count
- 푸터 전화 표기 대상: src/layouts/Layout.astro 1건 (전 레이아웃 파일 1개, 푸터 1곳)
- CF zone email_obfuscation: on (zone a6d9e75032c8cefe316b06d46a90a431)

## Backup
- .backup_footer_20260929_163354/src/layouts/Layout.astro
- CF 설정 롤백값: {"value": "on"} (PATCH로 복원 가능)

## Execution
1. Layout.astro 푸터 라인: "연락처: 010-7416-5705" → "전화(Tel): +82 10-7416-5705"
   - 병기형(+(국내 010-...)) 1차 적용 → 375px 폭에서 "010-/7416-5705)" 2줄 분해 확인 → 기본형으로 재적용
2. CF API PATCH zones/.../settings/email_obfuscation {"value":"off"} (사전 on 기록)
3. bash scripts/deploy.sh → 배포 완료

## Post-Verification
- 라이브 raw HTML(curl): "전화(Tel): +82 10-7416-5705" 1건, "연락처: 010" 0건
- 보호대상 무변경 4종 전부 true: 상호/대표/사업자등록번호/주소 (raw grep 확인)
- data-cfemail / __cf_email__ / cdn-cgi/l/email-protection 잔존 0, plaintext info@aikorea24.kr 2건
- 375px 폭 DOM 라인 분석: 2줄, 전화번호 줄 분해 없음
  - line1: "경기도 의정부시 호암로 256, 107-1804 (우 11638) | "
  - line2: "info@aikorea24.kr | 전화(Tel): +82 10-7416-5705"

## 제외 (지시 범위 밖 유지)
- src/pages/terms.astro / privacy.astro / contact.astro의 "연락처: 010-7416-5705" 표기 — 지시가 '공통 푸터' 대상만 지정

## Logs
- logs/destructive_2026-09-29.log
