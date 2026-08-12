# Brevo 이메일 구독 설정 스킬

> 프로젝트 간 재사용 가능한 Brevo 뉴스레터 구독/해지 구현 가이드

---

## 1. 개요

Brevo(구 Sendinblue) 이메일 마케팅 서비스를 이용한 웹사이트 뉴스레터 구독/해지 기능 구현 방법.

**적용 범위:**
- 구독 페이지 (`/subscribe/`)
- 구독 해지 페이지 (`/unsubscribe/`)
- API 엔드포인트 (`/api/subscribe`, `/api/unsubscribe`)
- 이메일 템플릿 내 구독 해지 링크
- Brevo 설정 (API Key, List ID)

---

## 2. 사전 준비

### 2.1 Brevo 계정 생성

1. [Brevo 가입](https://www.brevo.com/) — 무료 플랜: 일 300통 발송 가능
2. 로그인 후 좌측 메뉴: **Contacts → Lists**에서 구독 리스트 생성
3. List ID 기록 (예: `2`)

### 2.2 API Key 생성

1. Brevo 대시보드 → **Settings → API Keys**
2. **Generate new API key** 클릭
3. 이름 지정 (예: `aikorea24-production`)
4. 생성된 API Key 복사 후 안전한 곳에 저장 (다시 볼 수 없음)

### 2.3 Sender 도메인 인증 (권장)

1. Brevo 대시보드 → **Senders & IP → Senders**
2. **Add a sender domain** 클릭
3. 도메인 추가 (예: `aikorea24.kr`)
4. DNS 레코드(TXT, CNAME) 설정으로 인증 완료
5. 인증이 완료되어야 이메일로 발송 가능

---

## 3. 환경변수 설정

### 3.1 `.env` 파일

```bash
# Brevo 설정
BREVO_API_KEY=xkeysib-xxxxxxxxxxxxxxxxxxxxxxxx
BREVO_LIST_ID=2
SUBSCRIBER_EMAIL=your-email@example.com
```

### 3.2 Wrangler 설정 (`wrangler.toml`)

```toml
[vars]
# 실제 키는 .env 파일에 저장하고, 여기선 참고용 주석만 작성
# BREVO_API_KEY = "대시보드에서 설정"
# BREVO_LIST_ID = "2"
# SUBSCRIBER_EMAIL = "your@email.com"
```

> **보안 주의:** API Key는 절대로 코드 저장소(git)에 커밋하지 않는다. `.env` 파일은 `.gitignore`에 포함해야 한다.

---

## 4. API 구현

### 4.1 구독 API (`src/pages/api/subscribe.ts`)

```typescript
import type { APIRoute } from 'astro';

export const POST: APIRoute = async ({ request, locals }) => {
  const runtime = (locals as any).runtime;
  const BREVO_API_KEY = runtime?.env?.BREVO_API_KEY;
  const BREVO_LIST_ID = runtime?.env?.BREVO_LIST_ID;

  if (!BREVO_API_KEY) {
    return new Response(JSON.stringify({ error: 'BREVO_API_KEY not set' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  try {
    const { email } = await request.json();

    if (!email || !email.includes('@')) {
      return new Response(JSON.stringify({ error: '유효한 이메일을 입력해주세요.' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }

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

    if (!response.ok) {
      const errorData = await response.json();
      console.error('Brevo API error:', errorData);
      return new Response(JSON.stringify({ error: '구독 처리 중 오류가 발생했습니다.' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    return new Response(JSON.stringify({ success: true, message: '구독이 완료되었습니다! 🎉' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    console.error('Subscribe error:', error);
    return new Response(JSON.stringify({ error: '서버 오류가 발생했습니다.' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
};
```

**동작 방식:**
- `POST /api/subscribe` 요청 수신
- 이메일 유효성 검사 (`@` 포함 여부)
- Brevo `POST /v3/contacts`로 구독자 추가
- `listIds`에 할당된 리스트로 등록
- `updateEnabled: true`로 기존 연락처면 업데이트

---

### 4.2 구독 해지 API (`src/pages/api/unsubscribe.ts`)

```typescript
import type { APIRoute } from 'astro';

export const POST: APIRoute = async ({ request, locals }) => {
  const runtime = (locals as any).runtime;
  const BREVO_API_KEY = runtime?.env?.BREVO_API_KEY;

  if (!BREVO_API_KEY) {
    return new Response(JSON.stringify({ error: 'BREVO_API_KEY not set' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  try {
    const { email } = await request.json();

    if (!email || !email.includes('@')) {
      return new Response(JSON.stringify({ error: '유효한 이메일을 입력해주세요.' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // Brevo에서 구독자 제거: listIds를 빈 배열로 설정하여 리스트에서 제거
    const response = await fetch(
      `https://api.brevo.com/v3/contacts/${encodeURIComponent(email)}`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'api-key': BREVO_API_KEY
        },
        body: JSON.stringify({
          listIds: [],
          updateEnabled: true
        })
      }
    );

    if (!response.ok) {
      const errorData = await response.json();
      console.error('Brevo unsubscribe API error:', errorData);
      return new Response(JSON.stringify({ error: '구독 해지 처리 중 오류가 발생했습니다.' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    return new Response(JSON.stringify({ success: true, message: '구독이 해지되었습니다.' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    console.error('Unsubscribe error:', error);
    return new Response(JSON.stringify({ error: '서버 오류가 발생했습니다.' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
};
```

**동작 방식:**
- `POST /api/unsubscribe` 요청 수신
- Brevo `PUT /v3/contacts/{email}`로 리스트 연결 해제
- `listIds: []`로 설정하여 모든 리스트에서 제거
- 연락처는 유지되지만 구독 상태만 해제됨

---

## 5. 페이지 구현

### 5.1 구독 페이지 (`src/pages/subscribe.astro`)

구독 폼을 표시하는 페이지. 기존 프로젝트에 SubscribeBanner 컴포넌트를 재사용한다.

```astro
---
import Layout from '../layouts/Layout.astro';
import SubscribeBanner from '../components/home/SubscribeBanner.astro';
---

<Layout
  title="AI 브리핑 구독 - [프로젝트명]"
  description="매일 아침 [콘텐츠 설명]을 이메일로 받아보세요."
>
  <main class="min-h-screen bg-white dark:bg-[#0A0E1A] py-20 px-4">
    <div class="max-w-2xl mx-auto text-center">
      <h1 class="text-3xl md:text-4xl font-bold mb-4">
        📬 [헤더 메시지]
      </h1>
      <p class="text-gray-500 dark:text-gray-400 mb-6 leading-relaxed">
        [설명 텍스트]
      </p>

      <div class="bg-gray-50 dark:bg-white/[0.03] rounded-2xl p-8 border border-gray-200 dark:border-white/[0.08]">
        <SubscribeBanner />
      </div>

      <!-- 특징 소개 그리드 (선택) -->
      <div class="mt-12 grid grid-cols-1 sm:grid-cols-3 gap-6 text-left">
        <div class="p-4 rounded-xl bg-gray-50 dark:bg-white/[0.03] border border-gray-200 dark:border-white/[0.08]">
          <div class="text-lg mb-2">📰</div>
          <h3 class="text-sm font-bold mb-1">특징 1</h3>
          <p class="text-xs text-gray-500 dark:text-gray-400">설명</p>
        </div>
        <div class="p-4 rounded-xl bg-gray-50 dark:bg-white/[0.03] border border-gray-200 dark:border-white/[0.08]">
          <div class="text-lg mb-2">🛠️</div>
          <h3 class="text-sm font-bold mb-1">특징 2</h3>
          <p class="text-xs text-gray-500 dark:text-gray-400">설명</p>
        </div>
        <div class="p-4 rounded-xl bg-gray-50 dark:bg-white/[0.03] border border-gray-200 dark:border-white/[0.08]">
          <div class="text-lg mb-2">🔗</div>
          <h3 class="text-sm font-bold mb-1">특징 3</h3>
          <p class="text-xs text-gray-500 dark:text-gray-400">설명</p>
        </div>
      </div>
    </div>
  </main>
</Layout>
```

### 5.2 구독 해지 페이지 (`src/pages/unsubscribe.astro`)

```astro
---
import Layout from '../layouts/Layout.astro';
---

<Layout
  title="구독 해지 - [프로젝트명]"
  description="[프로젝트명] 뉴스레터 구독을 해지합니다."
>
  <main class="min-h-screen bg-white dark:bg-[#0A0E1A] py-20 px-4">
    <div class="max-w-xl mx-auto">
      <div class="text-center mb-10">
        <div class="text-5xl mb-4">📧</div>
        <h1 class="text-3xl md:text-4xl font-bold text-gray-900 dark:text-white mb-3">
          구독 해지
        </h1>
        <p class="text-gray-500 dark:text-gray-400">
          아래 이메일 주소를 입력하면 뉴스레터 구독이 해지됩니다.
        </p>
      </div>

      <div class="bg-gray-50 dark:bg-white/[0.03] rounded-2xl p-8 border border-gray-200 dark:border-white/[0.08]">
        <!-- 해지 완료 메시지 -->
        <div id="success-msg" class="hidden text-center mb-6 p-4 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-xl">
          <div class="text-3xl mb-2">✅</div>
          <p class="text-emerald-700 dark:text-emerald-300 font-semibold">구독이 해지되었습니다</p>
          <p class="text-sm text-emerald-600 dark:text-emerald-400 mt-1">
            더 이상 뉴스레터를 받지 않습니다.
          </p>
        </div>

        <!-- 해지 실패 메시지 -->
        <div id="error-msg" class="hidden text-center mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl">
          <div class="text-3xl mb-2">❌</div>
          <p id="error-text" class="text-red-700 dark:text-red-300 font-semibold">오류가 발생했습니다</p>
        </div>

        <form id="unsubscribe-form" class="space-y-5">
          <div>
            <label for="unsubscribe-email" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              이메일 주소
            </label>
            <input
              type="email"
              id="unsubscribe-email"
              name="email"
              required
              placeholder="예: your@email.com"
              class="w-full px-4 py-3 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition"
            />
          </div>

          <button
            type="submit"
            id="unsubscribe-btn"
            class="w-full py-3 px-6 bg-red-600 hover:bg-red-700 active:bg-red-800 text-white font-semibold rounded-xl transition-colors duration-200"
          >
            구독 해지하기
          </button>
        </form>

        <p class="mt-4 text-center text-xs text-gray-400 dark:text-gray-500">
          구독 해지는 언제든지 가능합니다.
        </p>
      </div>

      <div class="mt-8 text-center">
        <a href="/" class="inline-flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors">
          ← 메인 페이지로 돌아가기
        </a>
      </div>
    </div>
  </main>

  <script>
    const form = document.getElementById('unsubscribe-form');
    const btn = document.getElementById('unsubscribe-btn');
    const successMsg = document.getElementById('success-msg');
    const errorMsg = document.getElementById('error-msg');
    const errorText = document.getElementById('error-text');

    form?.addEventListener('submit', async (e) => {
      e.preventDefault();

      const email = (document.getElementById('unsubscribe-email') as HTMLInputElement).value.trim();

      btn.disabled = true;
      btn.textContent = '처리 중...';

      try {
        const res = await fetch('/api/unsubscribe', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email })
        });

        const data = await res.json();

        if (res.ok && data.success) {
          form.classList.add('hidden');
          successMsg.classList.remove('hidden');
        } else {
          errorText.textContent = data.error || '알 수 없는 오류가 발생했습니다.';
          errorMsg.classList.remove('hidden');
          btn.disabled = false;
          btn.textContent = '구독 해지하기';
        }
      } catch {
        errorText.textContent = '네트워크 오류가 발생했습니다. 다시 시도해주세요.';
        errorMsg.classList.remove('hidden');
        btn.disabled = false;
        btn.textContent = '구독 해지하기';
      }
    });
  </script>
</Layout>
```

### 5.3 구독 배너 컴포넌트 (`src/components/home/SubscribeBanner.astro`)

전역 구독 위젯으로 사용. 여러 페이지에 배치 가능.

```astro
<section class="py-10 px-4">
  <div class="max-w-2xl mx-auto text-center">
    <div class="bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl p-8 shadow-xl">
      <p class="text-sm text-blue-100 mb-3">📧 매일 아침 [내용] 받아보기</p>
      <form id="top-subscribe" class="flex flex-col sm:flex-row gap-2 max-w-md mx-auto">
        <input type="email" id="top-email" placeholder="이메일 주소" required
          class="flex-1 px-4 py-2.5 rounded-lg bg-white/10 border border-white/20 text-white placeholder:text-blue-200 text-sm focus:ring-2 focus:ring-white/40 focus:border-transparent outline-none" />
        <button type="submit"
          class="px-5 py-2.5 bg-white text-blue-600 font-medium rounded-lg text-sm hover:bg-blue-50 transition-colors whitespace-nowrap">
          구독
        </button>
      </form>
      <p id="top-subscribe-msg" class="text-xs mt-2 text-blue-100 hidden"></p>
    </div>
  </div>
</section>

<script>
document.getElementById('top-subscribe')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const input = document.getElementById('top-email');
  const msg = document.getElementById('top-subscribe-msg');
  const btn = e.target.querySelector('button');
  const email = input.value.trim();

  btn.disabled = true;
  btn.textContent = '처리 중...';
  msg.classList.add('hidden');

  try {
    const res = await fetch('/api/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    const data = await res.json();

    if (res.ok) {
      msg.className = 'text-xs mt-2 text-green-300';
      msg.textContent = '✅ 구독 완료!';
      input.value = '';
    } else {
      msg.className = 'text-xs mt-2 text-red-300';
      msg.textContent = data.error || '오류가 발생했습니다.';
    }
  } catch (err) {
    msg.className = 'text-xs mt-2 text-red-300';
    msg.textContent = '네트워크 오류입니다.';
  } finally {
    btn.disabled = false;
    btn.textContent = '구독';
    msg.classList.remove('hidden');
  }
});
</script>
```

---

## 6. 이메일 템플릿 내 구독 해지 링크

이메일 발송 시 푸터에 구독 해지 링크를 포함해야 한다.

```python
# 이메일 HTML 템플릿 예시 (Python)
def generate_email_html(briefing, items):
    intro = briefing.get('intro', '')
    esc = html_escape

    html = f"""
    <html>
      <body>
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;">
          <!-- 헤더 -->
          <tr>
            <td style="padding:24px;text-align:center;background:#0A0E1A;">
              <h1 style="color:#fff;font-size:20px;margin:0;">[프로젝트명] 뉴스레터</h1>
            </td>
          </tr>
          <!-- 내용 -->
          <tr>
            <td style="padding:20px 24px;background:#fff;border-bottom:1px solid #e5e7eb;">
              <p style="font-size:14px;color:#374151;line-height:1.6;margin:0;">{esc(intro)}</p>
            </td>
          </tr>
          <!-- 아이템 -->
          <tr>
            <td style="padding:0 24px;background:#fff;">
              [아이템 HTML]
            </td>
          </tr>
          <!-- 푸터: 구독 해지 링크 -->
          <tr>
            <td style="padding:24px;text-align:center;color:#9ca3af;font-size:12px;">
              <p style="margin:0;">[프로젝트명] · 매주 [요일] 발송</p>
              <p style="margin:4px 0 0 0;">
                <a href="https://[your-domain].kr/unsubscribe" style="color:#9ca3af;text-decoration:underline;">구독 해지</a>
              </p>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """
    return html
```

**구독 해지 링크 URL:** `https://[your-domain].kr/unsubscribe`

> Astro 프로젝트에서 `trailingSlash: 'always'` 설정 시 `/unsubscribe/`로 리다이렉트된다.

---

## 7. Brevo SMTP 이메일 발송 (Python 스크립트)

자동 이메일 발송을 위한 Brevo SMTP API 호출 예시:

```python
import os
import requests

def load_env():
    """환경변수 로드"""
    from dotenv import load_dotenv
    load_dotenv()

def send_email_via_brevo(briefing, items):
    """Brevo API로 이메일 발송"""
    load_env()

    api_key = os.environ.get("BREVO_API_KEY")
    if not api_key:
        print("❌ BREVO_API_KEY not set")
        return False

    html = generate_email_html(briefing, items)

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json"
    }

    subscriber_email = os.environ.get("SUBSCRIBER_EMAIL", "twinssn@gmail.com")

    payload = {
        "sender": {"name": "[프로젝트명]", "email": "info@[your-domain].kr"},
        "subject": f"[프로젝트명] 뉴스레터 - {briefing.get('date', '')}",
        "htmlContent": html,
        "to": [{"email": subscriber_email}]
    }

    list_id = os.environ.get("BREVO_LIST_ID")
    if list_id:
        list_ids = [int(x.strip()) for x in list_id.split(",")]
        payload["listIds"] = list_ids
        print(f"  → 개별 발송: {subscriber_email} + 목록 발송: listIds={list_ids}")
    else:
        print(f"  → 개별 발송: {subscriber_email}")

    resp = requests.post(url, json=payload, headers=headers)

    if resp.status_code not in [200, 201]:
        print(f"❌ API 오류 ({resp.status_code}): {resp.text}")
        return False

    print(f"  ✅ 발송 성공 (HTTP {resp.status_code})")
    if resp.status_code == 201:
        try:
            msg_id = resp.json().get("messageId", "")
            print(f"  📧 Message ID: {msg_id}")
        except Exception:
            pass
    return True
```

---

## 8. 파일 구조

```
src/
├── pages/
│   ├── subscribe.astro           # 구독 페이지 (/subscribe/)
│   ├── unsubscribe.astro         # 구독 해지 페이지 (/unsubscribe/)
│   └── api/
│       ├── subscribe.ts          # 구독 API (POST /api/subscribe)
│       └── unsubscribe.ts        # 구독 해지 API (POST /api/unsubscribe)
├── components/
│   └── home/
│       └── SubscribeBanner.astro # 전역 구독 배너 위젯
```

---

## 9. API 엔드포인트 요약

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| POST | `/api/subscribe` | 이메일 구독 추가 |
| POST | `/api/unsubscribe` | 이메일 구독 해지 |
| GET | `/subscribe/` | 구독 페이지 |
| GET | `/unsubscribe/` | 구독 해지 페이지 |

---

## 10. Brevo API 참고

### 연락처 추가
```
POST https://api.brevo.com/v3/contacts
Headers: api-key: YOUR_API_KEY
Body: { "email": "user@example.com", "listIds": [2], "updateEnabled": true }
```

### 연락처 제거 (리스트에서 해제)
```
PUT https://api.brevo.com/v3/contacts/user@example.com
Headers: api-key: YOUR_API_KEY
Body: { "listIds": [], "updateEnabled": true }
```

### 연락처 조회
```
GET https://api.brevo.com/v3/contacts?email=user@example.com
Headers: api-key: YOUR_API_KEY
```

### 이메일 발송 (SMTP API)
```
POST https://api.brevo.com/v3/smtp/email
Headers: api-key: YOUR_API_KEY
Body: { "sender": {...}, "subject": "...", "htmlContent": "...", "to": [...] }
```

**문서:** https://developers.brevo.com/docs

---

## 11. 체크리스트

### 초기 설정
- [ ] Brevo 계정 생성
- [ ] 구독 리스트 생성 및 List ID 기록
- [ ] API Key 생성 (Settings → API Keys)
- [ ] Sender 도메인 인증 완료 (권장)
- [ ] `.env`에 `BREVO_API_KEY`, `BREVO_LIST_ID` 설정
- [ ] `.gitignore`에 `.env` 포함 확인

### 코드 구현
- [ ] `src/pages/api/subscribe.ts` 생성
- [ ] `src/pages/api/unsubscribe.ts` 생성
- [ ] `src/pages/subscribe.astro` 생성
- [ ] `src/pages/unsubscribe.astro` 생성
- [ ] `src/components/home/SubscribeBanner.astro` 생성
- [ ] 이메일 템플릿에 `/unsubscribe` 링크 포함

### 테스트
- [ ] 개발 서버(`npm run dev`)에서 구독 테스트
- [ ] 개발 서버에서 구독 해지 테스트
- [ ] Brevo 대시보드에서 연락처 추가/제거 확인
- [ ] 실제 이메일 수신 확인

### 배포
- [ ] wrangler.toml에 env var 설정 (또는 대시보드에서 설정)
- [ ] `npm run build` 후 배포
- [ ] 라이브 환경에서 구독/해지 테스트
- [ ] 이메일 발송 테스트

---

## 12. 트러블슈팅

### "BREVO_API_KEY not set" 오류
- 런타임 환경변수 확인: `wrangler.toml`의 `[vars]` 또는 대시보드 Settings → Variables
- 개발 서버 실행 시 `.env` 파일이 제대로 로드되는지 확인

### 구독이 안 됨
- Brevo 대시보드 → Contacts에서 이메일 확인
- API Key 권한 확인 (Full Access 권장)
- 이메일 형식 유효성 확인

### 이메일 발송 실패
- Sender 도메인 인증 완료 여부 확인
- Brevo 무료 플랜: 일 300통 제한 확인
- API 응답 코드 확인 (4xx/5xx)

### 구독 해지가 안 됨
- unsubscribe API에서 `listIds: []`로 PUT 요청하는지 확인
- Brevo 대시보드에서 해당 이메일이 리스트에 남아 있는지 확인

---

## 13. 보안 고려사항

1. **API Key 보호**: 절대 git에 커밋하지 않는다
2. **.env 파일**: `.gitignore`에 포함
3. **Wrangler Secrets**: 프로덕션 환경에서는 `wrangler secret put BREVO_API_KEY`로 설정 권장
4. **이메일 검증**: 구독 시 이메일 형식 유효성 검사 필수
5. **Rate Limiting**: 구독 API에 rate limiting 추가 고려 (선택사항)

---

*문서 버전: 1.0 | 생성일: 2026-08-07 | 프로젝트: aikorea24*
