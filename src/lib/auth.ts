// 세션에서 유저 정보 추출
export function getSessionUser(cookies: any): { email: string; name: string } | null {
  const session = cookies.get('session')?.value;
  if (!session) return null;
  try {
    return JSON.parse(atob(session.split('.')[1] || session));
  } catch {
    return null;
  }
}

// DB에서 유저 멤버십 조회
export async function getUserMembership(db: any, email: string) {
  const user = await db.prepare(
    'SELECT membership, membership_expires, purchased_posts FROM users WHERE email = ?'
  ).bind(email).first();

  if (!user) return { level: 'free', purchased: [] };

  // 구독 만료 체크
  let level = user.membership || 'free';
  if (level !== 'free' && user.membership_expires) {
    const expires = new Date(user.membership_expires);
    if (expires < new Date()) {
      // 만료됨 → free로 다운그레이드
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

// 콘텐츠 접근 가능 여부 체크
export function canAccess(
  userLevel: string,
  purchasedPosts: number[],
  postAccessLevel: string,
  postId: number
): boolean {
  // free 콘텐츠는 누구나
  if (postAccessLevel === 'free') return true;

  // 건별 구매한 글
  if (purchasedPosts.includes(postId)) return true;

  // 멤버십 등급 체크
  const hierarchy: Record<string, number> = {
    free: 0,
    basic: 1,
    premium: 2,
  };

  return (hierarchy[userLevel] || 0) >= (hierarchy[postAccessLevel] || 0);
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
