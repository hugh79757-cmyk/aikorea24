# Brevo 이메일 구독·발송 통합 스킬

> Brevo를 이용한 뉴스레터 구독 관리 + 자동 이메일 발송 전체 시스템

---

## 1. 개요

Brevo(구 Sendinblue)를 이용한 두 가지 기능:
1. **구독 관리**: 웹사이트 구독/해지 페이지 + API
2. **자동 발송**: 매일 아침 브리핑 기반 뉴스레터 자동 발송

**관련 파일:**
| 파일 | 역할 |
|------|------|
| `src/pages/api/subscribe.ts` | 구독 API (POST /api/subscribe) |
| `src/pages/api/unsubscribe.ts` | 구독 해지 API (POST /api/unsubscribe) |
| `src/pages/subscribe.astro` | 구독 페이지 (/subscribe/) |
| `src/pages/unsubscribe.astro` | 구독 해지 페이지 (/unsubscribe/) |
| `src/components/home/SubscribeBanner.astro` | 전역 구독 배너 위젯 |
| `scripts/auto_email_sender.py` | 매일 이메일 자동 발송 |

---

## 2. Brevo 계정 설정

### 2.1 계정 생성

1. [Brevo 가입](https://www.brevo.com/) — 무료: 일 300통
2. **Contacts → Lists**에서 구독 리스트 생성 → List ID 기록
3. **Settings → API Keys**에서 API Key 생성 (Full Access 권장)

### 2.2 Sender 도메인 인증

이메일 발송을 위해 필수:

1. Brevo → **Senders & IP → Senders**
2. **Add a sender domain** → 도메인 입력 (예: `aikorea24.kr`)
3. DNS에 TXT/CNAME 레코드 추가 (Brevo가 제공하는 값)
4. 인증 완료까지 최대 48시간 (보통 몇 분 내 완료)

### 2.3 환경변수 설정

`.env` 파일:
```bash
BREVO_API_KEY=xkeysib-xxxxxxxxxxxxxxxxxxxxxxxx
BREVO_LIST_ID=2
SUBSCRIBER_EMAIL=your@email.com
```

`wrangler.toml`:
```toml
[vars]
# 실제 키는 wrangler dashboard 또는 secret으로 설정
# BREVO_API_KEY = ""
# BREVO_LIST_ID = "2"
# SUBSCRIBER_EMAIL = ""
```

프로덕션 환경에서는 wrangler secret 사용 권장:
```bash
wrangler secret put BREVO_API_KEY
wrangler secret put BREVO_LIST_ID
wrangler secret put SUBSCRIBER_EMAIL
```

---

## 3. 구독 관리 시스템

### 3.1 구독 API

`POST /api/subscribe` — 요청 바디: `{ "email": "user@example.com" }`

```typescript
// src/pages/api/subscribe.ts 핵심 로직
const response = await fetch('https://api.brevo.com/v3/contacts', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'api-key': BREVO_API_KEY
  },
  body: JSON.stringify({
    email: email,
    listIds: [Number(BREVO_LIST_ID) || 2],
    updateEnabled: true
  })
});
```

- `updateEnabled: true`로 기존 연락처는 업데이트
- 성공하면 `{ success: true, message: '구독이 완료되었습니다! 🎉' }` 응답

### 3.2 구독 해지 API

`POST /api/unsubscribe` — 요청 바디: `{ "email": "user@example.com" }`

```typescript
// src/pages/api/unsubscribe.ts 핵심 로직
const response = await fetch(
  `https://api.brevo.com/v3/contacts/${encodeURIComponent(email)}`,
  {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'api-key': BREVO_API_KEY
    },
    body: JSON.stringify({
      listIds: [],        // 모든 리스트에서 제거
      updateEnabled: true
    })
  }
);
```

- 연락처는 Brevo에 남지만 리스트에서 제거되어 더 이상 이메일 수신 안 함
- 성공하면 `{ success: true, message: '구독이 해지되었습니다.' }` 응답

### 3.3 구독 페이지

`/subscribe/` — 이메일 입력 폼 + SubscribeBanner 위젯

주요 특징:
- 가운데 정렬 레이아웃
- 구독 완료 시 인라인 메시지 표시
- 하단 특징 소개 그리드 (3개 카드)

### 3.4 구독 해지 페이지

`/unsubscribe/` — 이메일 입력 폼 + 해지 버튼

주요 특징:
- 빨간색 테마 버튼 (해지임을 시각적으로 구분)
- 해지 완료 시 성공 메시지 + 폼 숨김
- 오류 시 에러 메시지 표시
- 하단 메인 페이지 링크

### 3.5 구독 배너 위젯

`SubscribeBanner.astro` — 홈페이지 등에 배치하는 전역 구독 위젯

- 그라데이션 배경 + 이메일 입력 + 구독 버튼
- 제출 시 `/api/subscribe` 호출
- 성공/실패 인라인 메시지

### 3.6 이메일 템플릿 내 구독 해지 링크

이메일 발송 시 푸터에 포함:

```html
<a href="https://aikorea24.kr/unsubscribe" style="color:#9ca3af;text-decoration:underline;">
  구독 해지
</a>
```

※ Astro `trailingSlash: 'always'` 설정 시 `/unsubscribe/`로 리다이렉트됨

---

## 4. 자동 이메일 발송

### 4.1 스크립트 개요

`scripts/auto_email_sender.py` — 매일 브리핑 조회 → HTML 이메일 생성 → Brevo SMTP API로 발송

### 4.2 실행

```bash
cd /Users/twinssn/Projects/aikorea24
python3 scripts/auto_email_sender.py
```

### 4.3 동작 흐름

1. D1에서 오늘 발행된 브리핑 조회 (`briefings` 테이블에서 `date LIKE 'YYYY-MM-DD%'`)
2. 브리핑 아이템 조회 (`briefing_items` + `news` 조인)
3. HTML 이메일 템플릿 생성:
   - 헤더 (프로젝트명 + 날짜)
   - intro 문단
   - 뉴스 아이템 목록 (제목 + 코멘트 + 링크)
   - AI 도구 목록 (선택)
   - 푸터 (커뮤니티 링크 + 구독 해지 링크)
4. Brevo SMTP API로 발송:
   - 개별 수신자 (`SUBSCRIBER_EMAIL`)
   - 리스트 전체 발송 (`listIds` 포함)

### 4.4 이메일 HTML 템플릿 구조

```python
# scripts/auto_email_sender.py - generate_email_html()
html = f"""
<html>
  <body>
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;">
      <!-- 헤더 -->
      <tr><td style="padding:24px;text-align:center;background:#0A0E1A;">
        <h1 style="color:#fff;font-size:20px;margin:0;">AI코리아24 뉴스레터</h1>
      </td></tr>
      <!-- intro -->
      <tr><td style="padding:20px 24px;background:#fff;">
        <p style="font-size:14px;color:#374151;line-height:1.6;">{intro}</p>
      </td></tr>
      <!-- 아이템 -->
      <tr><td style="padding:0 24px;background:#fff;">
        <table>{items_html}</table>
      </td></tr>
      <!-- 푸터 -->
      <tr><td style="padding:24px;text-align:center;color:#9ca3af;font-size:12px;">
        <p style="margin:0;">AI코리아24 · 매일 아침 AI 소식을 전해드립니다</p>
        <p style="margin:4px 0 0 0;">
          <a href="https://aikorea24.kr/community/" style="color:#3b82f6;text-decoration:underline;">💬 커뮤니티</a>
        </p>
        <p style="margin:4px 0 0 0;">
          <a href="https://aikorea24.kr/unsubscribe" style="color:#9ca3af;text-decoration:underline;">구독 해지</a>
        </p>
      </td></tr>
    </table>
  </body>
</html>
"""
```

### 4.5 Brevo SMTP 발송 API

```
POST https://api.brevo.com/v3/smtp/email
Headers:
  api-key: YOUR_API_KEY
  Content-Type: application/json
Body:
{
  "sender": {"name": "AI코리아24", "email": "info@aikorea24.kr"},
  "subject": "AI코리아24 뉴스레터 - 2026-08-07",
  "htmlContent": "<html>...</html>",
  "to": [{"email": "user@example.com"}],
  "listIds": [2]           // 선택: 리스트 전체 발송
}
```

응답:
- `200`: 발송 성공 (기존 연락처에 발송)
- `201`: 신규 연락처 생성 후 발송 → `messageId` 포함

---

## 5. Brevo API 빠른 참조

### 연락처 추가 (구독)
```
POST /v3/contacts
Body: { "email": "user@example.com", "listIds": [2], "updateEnabled": true }
```

### 연락처 제거 (구독 해지)
```
PUT /v3/contacts/user@example.com
Body: { "listIds": [], "updateEnabled": true }
```

### 연락처 조회
```
GET /v3/contacts?email=user@example.com
GET /v3/contacts?limit=1000    # 전체 목록
```

### 이메일 발송
```
POST /v3/smtp/email
Body: { "sender": {...}, "subject": "...", "htmlContent": "...", "to": [...], "listIds": [...] }
```

**API 문서:** https://developers.brevo.com/docs

---

## 6. 파일 구조

```
src/
├── pages/
│   ├── subscribe.astro              # 구독 페이지
│   ├── unsubscribe.astro            # 구독 해지 페이지
│   └── api/
│       ├── subscribe.ts             # 구독 API
│       └── unsubscribe.ts           # 구독 해지 API
├── components/
│   └── home/
│       └── SubscribeBanner.astro    # 전역 구독 배너
scripts/
└── auto_email_sender.py             # 자동 이메일 발송
```

---

## 7. 체크리스트

### 초기 설정
- [ ] Brevo 계정 생성
- [ ] 구독 리스트 생성 + List ID 기록
- [ ] API Key 생성
- [ ] Sender 도메인 인증 완료
- [ ] `.env`에 BREVO_API_KEY, BREVO_LIST_ID 설정
- [ ] `wrangler secret put`으로 프로덕션 키 설정 (권장)

### 구독 기능 테스트
- [ ] `/subscribe/` 페이지에서 구독 테스트
- [ ] Brevo 대시보드에서 연락처 추가 확인
- [ ] `/unsubscribe/` 페이지에서 해지 테스트
- [ ] Brevo 대시보드에서 리스트 제거 확인

### 이메일 발송 테스트
- [ ] `python3 scripts/auto_email_sender.py` 실행
- [ ] 이메일 수신 확인 (HTML 렌더링, 링크 작동)
- [ ] 구독 해지 링크 클릭 → `/unsubscribe/` 페이지 정상 표시 확인

### 배포
- [ ] `npm run build` 성공
- [ ] wrangler로 배포
- [ ] 라이브 환경에서 구독/해지/이메일 모두 확인

---

## 8. 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| "BREVO_API_KEY not set" | 환경변수 누락 | `.env` 또는 wrangler secret 확인 |
| 이메일 발송 400 오류 | Sender 미인증 | Brevo Sender 도메인 인증 완료 |
| 구독이 안 됨 | API Key 권한 | Full Access API Key 사용 |
| 해지 후 여전히 수신 | listIds 제거 안 됨 | PUT 요청으로 listIds: [] 확인 |
| 일일 발송 한도 초과 | 무료 플랜 300통 | 유료 플랜 업그레이드 또는 발송 최적화 |

---

*문서 버전: 1.0 | 생성일: 2026-08-07*
