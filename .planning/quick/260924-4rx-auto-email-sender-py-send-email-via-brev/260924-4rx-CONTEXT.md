# Quick Task 260924-4rx: 뉴스레터 발송 정상화 및 재발 방지 - Context

**Gathered:** 2026-09-24
**Status:** Ready for planning

<domain>
## Task Boundary

auto_email_sender.py의 send_email_via_brevo 함수를 수정하여:
1. Brevo list#2 구독자를 동적으로 조회 (get_subscribers_from_brevo)
2. listIds 파라미터 제거, to 필드로 전원 개별 발송
3. test/sample 이메일 자동 필터링
4. SUBSCRIBER_EMAIL 폴백 유지

</domain>

<decisions>
## Implementation Decisions

### User decisions
- Discussion phase: "All clear" — skip, use agent discretion

### the agent's Discretion
- Brevo API pagination: list#2 has 8 contacts (well under 500 limit), no pagination needed
- Error handling: Brevo fetch failure → fallback to SUBSCRIBER_EMAIL; if both empty → return False with log
- Test email filtering: exclude patterns ["sample@", "test-", "verify-test@", "@example."]
- Rate limiting: not needed for 8 subscribers; Brevo transactional API handles this
- No email sending test (per task constraints)

</decisions>

<specifics>
## Specific Ideas

- Use requests library (already imported in auto_email_sender.py)
- get_subscribers_from_brevo() as standalone function for testability
- Keep existing HTML generation logic unchanged
- Keep sender info unchanged: {name: "AI코리아24", email: "info@aikorea24.kr"}

</specifics>

<canonical_refs>
## Canonical References

- scripts/auto_email_sender.py (target file)
- src/pages/api/subscribe.ts (subscription API, already working)
- Brevo API docs: /v3/contacts (GET), /v3/smtp/email (POST)

</canonical_refs>