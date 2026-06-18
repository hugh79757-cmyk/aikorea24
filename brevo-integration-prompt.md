````markdown
# Brevo 이메일 구독 API 연동

## 프로젝트 개요
- 사이트: aikorea24.kr
- 스택: Astro 5.17 SSR + Cloudflare Pages + Cloudflare Workers
- 목표: /tools 페이지의 뉴스레터 CTA를 Brevo API와 연동하여 실제 구독 저장

## 환경 변수
- wrangler.toml [vars]에 아래 변수 추가 (이미 있으면 확인만):
  BREVO_API_KEY = "xkeysib-xxxx"  
  BREVO_LIST_ID = 2  (또는 Brevo에서 생성한 리스트 ID)

## 변경할 파일 (총 4개)

### 1. src/pages/api/subscribe.ts (신규 생성)
POST /api/subscribe 엔드포인트 생성

```typescript
import type { APIRoute } from 'astro';

export const POST: APIRoute = async ({ request }) => {
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
        'api-key': import.meta.env.BREVO_API_KEY
      },
      body: JSON.stringify({
        email: email,
        listIds: [Number(import.meta.env.BREVO_LIST_ID) || 2],
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
Copy
````

### 2. src/pages/tools/index.astro (뉴스레터 CTA 수정)

기존 뉴스레터 CTA 섹션(alert('준비 중'))을 아래 실제 폼으로 교체:

```astro
Copy<!-- 뉴스레터 구독 CTA -->
<div class="mt-16 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-gray-800 dark:to-gray-750 rounded-2xl p-8 border border-blue-100 dark:border-gray-700">
  <div class="text-center max-w-xl mx-auto">
    <div class="text-3xl mb-3">🚀</div>
    <h3 class="text-xl font-bold text-gray-900 dark:text-white mb-2">AI 트렌드, 매일 아침 요약해드려요</h3>
    <p class="text-gray-600 dark:text-gray-400 text-sm mb-6">
      매일 아침 7시, 국내외 AI 소식을 큐레이션해서 보내드립니다. 무료입니다.
    </p>
    <form id="brevo-subscribe" class="flex flex-col sm:flex-row gap-3 max-w-md mx-auto">
      <input
        type="email"
        id="subscribe-email"
        placeholder="이메일 주소를 입력하세요"
        required
        class="flex-1 px-4 py-3 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none text-sm"
      />
      <button
        type="submit"
        class="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-xl transition-colors text-sm whitespace-nowrap"
      >
        무료 구독하기
      </button>
    </form>
    <p id="subscribe-message" class="mt-3 text-sm hidden"></p>
    <p class="text-xs text-gray-400 mt-2">· 300字 이내로 무료 발송 · 언제든 구독 해지 가능</p>
  </div>
</div>

<script>
document.getElementById('brevo-subscribe')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const email = document.getElementById('subscribe-email').value.trim();
  const btn = e.target.querySelector('button');
  const msg = document.getElementById('subscribe-message');
  
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
      msg.className = 'mt-3 text-sm text-green-600 dark:text-green-400';
      msg.textContent = '✅ 구독 완료! 매일 아침 AI 브리핑을 보내드립니다.';
      e.target.querySelector('input').value = '';
    } else {
      msg.className = 'mt-3 text-sm text-red-600 dark:text-red-400';
      msg.textContent = data.error || '오류가 발생했습니다. 다시 시도해주세요.';
    }
  } catch (err) {
    msg.className = 'mt-3 text-sm text-red-600 dark:text-red-400';
    msg.textContent = '네트워크 오류입니다. 다시 시도해주세요.';
  } finally {
    btn.disabled = false;
    btn.textContent = '무료 구독하기';
    msg.classList.remove('hidden');
  }
});
</script>
```

### 3. src/pages/tools/\[...id].astro (상세 페이지 뉴스레터 CTA 수정)

같은 방식으로 기존 alert('준비 중') CTA 교체 (위 코드와 동일한 폼/스크립트)

### 4. wrangler.toml 확인

\[vars] 섹션에 아래가 있는지 확인. 없으면 추가:

```toml
CopyBREVO_API_KEY = "xkeysib-your-key-here"
BREVO_LIST_ID = "2"
```

## 실행 순서

1. src/pages/api/subscribe.ts 생성 (신규)
2. src/pages/tools/index.astro 뉴스레터 CTA 교체
3. src/pages/tools/\[...id].astro 뉴스레터 CTA 교체
4. wrangler.toml에 BREVO\_API\_KEY / BREVO\_LIST\_ID 추가 확인
5. npm run dev로 테스트

````
Copy
---

## 저장 후 실행

```bash
# 파일 저장
cat > /Users/twinssn/Projects/aikorea24/brevo-integration-prompt.md << 'ENDOFFILE'
(위 내용 전체)
ENDOFFILE

# Reasonix 실행
cd /Users/twinssn/Projects/aikorea24
npx reasonix code
# → /init brevo-integration-prompt.md
````
