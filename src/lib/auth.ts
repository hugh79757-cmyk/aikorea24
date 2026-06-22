const ALGORITHM = { name: 'HMAC', hash: 'SHA-256' };
const EXTRACTABLE = false;
const KEY_USAGES: KeyUsage[] = ['sign', 'verify'];

async function getSessionSecret(secret: string): Promise<CryptoKey> {
  if (!secret) throw new Error('SESSION_SECRET is not configured');
  const encoder = new TextEncoder();
  const keyData = encoder.encode(secret);
  return crypto.subtle.importKey('raw', keyData, ALGORITHM, EXTRACTABLE, KEY_USAGES);
}

export async function signSession(data: Record<string, any>, secret: string): Promise<string> {
  const payload = btoa(JSON.stringify(data));
  const key = await getSessionSecret(secret);
  const encoder = new TextEncoder();
  const signature = await crypto.subtle.sign('HMAC', key, encoder.encode(payload));
  const sigArray = Array.from(new Uint8Array(signature));
  const sigB64 = btoa(String.fromCharCode(...sigArray));
  return `${payload}.${sigB64}`;
}

export async function verifySession(signedSession: string, secret: string): Promise<Record<string, any> | null> {
  const dotIdx = signedSession.lastIndexOf('.');
  if (dotIdx === -1) return null;

  const payload = signedSession.slice(0, dotIdx);
  const sigB64 = signedSession.slice(dotIdx + 1);

  try {
    const key = await getSessionSecret(secret);
    const encoder = new TextEncoder();
    const sigData = Uint8Array.from(atob(sigB64), c => c.charCodeAt(0));
    const valid = await crypto.subtle.verify('HMAC', key, sigData, encoder.encode(payload));
    if (!valid) return null;
    return JSON.parse(atob(payload));
  } catch {
    return null;
  }
}

// 세션에서 유저 정보 추출 (HMAC 검증 포함)
export async function getSessionUser(cookies: any, secret: string): Promise<{ email: string; name: string } | null> {
  const session = cookies.get('session')?.value;
  if (!session) return null;
  const data = await verifySession(session, secret);
  if (!data || !data.email || !data.name) return null;
  return { email: data.email, name: data.name };
}

// DB에서 유저 멤버십 조회
export async function getUserMembership(db: any, email: string) {
  const user = await db.prepare(
    'SELECT membership, membership_expires, purchased_posts FROM users WHERE email = ?'
  ).bind(email).first();

  if (!user) return { level: 'free', purchased: [] };

  let level = user.membership || 'free';
  if (level !== 'free' && user.membership_expires) {
    const expires = new Date(user.membership_expires);
    if (expires < new Date()) {
      await db.prepare(
        "UPDATE users SET membership = 'free' WHERE email = ?"
      ).bind(email).run();
      level = 'free';
    }
  }

  let purchased: number[] = [];
  try {
    purchased = JSON.parse(user.purchased_posts || '[]');
  } catch {}

  return { level, purchased };
}

// 구독 플랜 정보
export const PLANS = {
  basic_monthly: {
    name: 'Basic 월간',
    level: 'basic',
    price: 4900,
    duration: 30,
    description: '로그인 전용 콘텐츠 열람',
  },
  basic_yearly: {
    name: 'Basic 연간',
    level: 'basic',
    price: 39000,
    duration: 365,
    description: '로그인 전용 콘텐츠 열람 (연간 33% 할인)',
  },
  premium_monthly: {
    name: 'Premium 월간',
    level: 'premium',
    price: 9900,
    duration: 30,
    description: '전체 콘텐츠 무제한 열람',
  },
  premium_yearly: {
    name: 'Premium 연간',
    level: 'premium',
    price: 79000,
    duration: 365,
    description: '전체 콘텐츠 무제한 열람 (연간 33% 할인)',
  },
};
