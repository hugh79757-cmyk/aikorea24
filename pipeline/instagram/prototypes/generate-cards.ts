#!/usr/bin/env node
/**
 * Instagram Carousel Card Generator - 사용 예시
 * 
 * 실행: npx tsx generate-cards.ts
 * 또는: node --loader ts-node/esm generate-cards.ts
 * 
 * 결과: ./output/ 폴더에 HTML 파일들 생성
 */

import { writeFileSync, mkdirSync, existsSync } from 'fs';
import { join } from 'path';

// 빌더와 카드 클래스 import
import { 
  BRAND_TOKENS,
  MinimalistCard,
  BoldTypographyCard, 
  GradientEditorialCard,
  CarouselBuilder 
} from './src/auto_poster/components/carousel-cards';

const OUTPUT_DIR = join(process.cwd(), 'output', 'instagram-carousels');

// 출력 디렉토리 생성
if (!existsSync(OUTPUT_DIR)) {
  mkdirSync(OUTPUT_DIR, { recursive: true });
}

function saveCard(filename: string, html: string) {
  writeFileSync(join(OUTPUT_DIR, filename), html);
  console.log(`✅ 생성: ${filename}`);
}

// ============================================
// 1. Format D (펀치 브리핑) - Minimalist 스타일
// ============================================
console.log('\n📋 Format D (펀치 브리핑) 5장 생성 중...');

const formatDData = [
  { 
    type: 'hook',
    hookLine1: '틱톡이 감원한다던',
    hookNumber: '667명',
    hookLine2: '의 정체',
    subtext: '"약 300명"이라던 공식 발표\n내부 문서엔 <span class="font-bold text-gray-900">2배 넘는 667명</span>'
  },
  { 
    type: 'conflict',
    topic: '자살 챌린지 영상',
    teamName: '검수팀',
    stats: '더블린 전체 직원의 40%\nADSO(AI 데이터 서비스·운영)팀 전원'
  },
  { 
    type: 'twist',
    quote: '"애들한테 자살 챌린지 올리는 놈들은\n알고리즘 피하는 데 <span class="text-purple-600 font-bold">도가 텄다</span>"',
    source: '익명의 틱톡 검수 직원 내부 게시판 글'
  },
  { 
    type: 'expansion',
    items: [
      { icon: 'check', title: '노조의 지적', desc: '"AI는 핑계일 뿐, 싼 나라로 아웃소싱 가속화"', color: 'primary' },
      { icon: 'shield', title: '정부 경고', desc: '"AI가 만드는 파괴적 영향, 불확실성 그대로 보여줘"', color: 'secondary' },
      { icon: 'sparkles', title: '핵심 포인트', desc: 'AI가 제일 먼저 먹는 일자리 = 창의직이 아닌 \'안전\' 직군', color: 'accent' }
    ]
  },
  { 
    type: 'cta',
    title: '최악을 막아주던 사람이 사라진 자리에\n그걸 자꾸 놓치는 AI가 들어올 때,',
    subtitle: '당신 피드는 더 안전해지는 걸까\n아니면 그 반대일까.',
    ctaText: '전체 기사 읽으러 가기',
    link: 'https://aikorea24.kr'
  }
];

formatDData.forEach((data, i) => {
  const card = new MinimalistCard(data, {
    cardNumber: i + 1,
    totalCards: 5,
    style: 'minimalist'
  });
  saveCard(`format-d-minimalist-${i + 1}.html`, card.render());
});

// ============================================
// 2. AI 툴 추천 - Bold Typography 스타일
// ============================================
console.log('\n🔧 AI 툴 추천 (커버 + 3툴 + CTA) 5장 생성 중...');

const toolCards = [
  // 커버
  {
    category: '글쓰기·마케팅',
    titleLines: ['이번 주\n', '놓치면 손해\n', 'AI 툴 <span class="text-7xl">3가지</span>'],
    subtitle: '무료로 시작 가능 • 한국어 지원 • 실무 바로 적용'
  },
  // 툴 1
  {
    titleLines: ['ChatGPT\n['ChatGPT', '<span class="bg-gradient-to-r from-yellow-300 to-orange-400 bg-clip-text text-transparent">Plus</span>'],
    subtitle: '가장 대중적인 AI 글쓰기 파트너',
    price: '무료',
    lang: '한국어',
    tags: ['블로그 글쓰기', '마케팅 카피', '이메일 초안', '아이디어 발상']
  },
  // 툴 2
  {
    titleLines: ['Midjourney', '<span class="bg-gradient-to-r from-purple-300 to-pink-400 bg-clip-text text-transparent">v6</span>'],
    subtitle: '상상한 그대로 이미지 생성',
    price: '체험 후 월 $10',
    lang: '영어(프롬프트)',
    tags: ['블로그 썸네일', 'SNS 이미지', '프레젠테이션', '콘텐츠 비주얼']
  },
  // 툴 3
  {
    titleLines: ['Notion AI', '<span class="bg-gradient-to-r from-teal-300 to-blue-400 bg-clip-text text-transparent">통합</span>'],
    subtitle: '문서·위키·프로젝트 한 번에',
    price: '무료 플랜',
    lang: '한국어 완벽',
    tags: ['회의록 요약', '글쓰기 보조', '번역·교정', '브레인스토밍']
  },
  // CTA
  {
    titleLines: ['무료로 시작하고', '한국어로 쓰고', '내일 바로 실무에'],
    subtitle: '무료로 시작하고, 한국어로 쓰고, 내일 바로 실무에 써먹기'
  }
];

toolCards.forEach((data, i) => {
  const card = new BoldTypographyCard(data, {
    cardNumber: i + 1,
    totalCards: 5,
    style: 'bold'
  });
  saveCard(`ai-tools-bold-${i + 1}.html`, card.render());
});

// ============================================
// 3. 지원사업 가이드 - Gradient Editorial 스타일
// ============================================
console.log('\n💰 지원사업 가이드 (커버 + 3단계 + CTA) 5장 생성 중...');

const grantCard = new GradientEditorialCard({
  urgency: '마감 D-3',
  titleLines: [
    'AI 바우처',
    '<span class="bg-gradient-to-r from-yellow-300 to-orange-400 bg-clip-text text-transparent">3천만원</span>',
    '받는 법'
  ],
  steps: [
    { 
      title: '자격 확인', 
      desc: '중소기업·소상공인·예비창업자 대상\nAI 도입 필요성만 있으면 신청 가능',
      badge: '자동 진단',
      badgeColor: 'bg-green-500/20 text-green-300',
      gradient: 'from-yellow-400 to-orange-500'
    },
    { 
      title: '사업계획서 작성', 
      desc: 'AI가 대신 써주는 사업계획서 초안\n우리 사이트 \'AI 강좌\'에서 무료 템플릿 다운로드',
      badge: '템플릿 제공',
      badgeColor: 'bg-purple-500/20 text-purple-300',
      gradient: 'from-blue-400 to-purple-500'
    },
    { 
      title: '온라인 신청', 
      desc: '중소벤처기업부 홈페이지서 접수\nD-day 알림 신청하면 카톡으로 알려드림',
      badge: '마감 임박',
      badgeColor: 'bg-red-500/20 text-red-300',
      gradient: 'from-pink-400 to-red-500'
    }
  ],
  ctaText: '지금 자격 진단하러 가기 →',
  ctaLink: 'https://aikorea24.kr/grants',
  ctaSubtext: '프로필 링크에서 무료 진단 시작'
}, {
  cardNumber: 1,
  totalCards: 5,
  style: 'gradient'
});

saveCard('grant-guide-gradient-1.html', grantCard.render());

// 나머지 4장도 생성 (스텝별 + CTA)
['step1', 'step2', 'step3', 'cta'].forEach((type, i) => {
  const card = new GradientEditorialCard({
    ...grantCard.data,
    // 각 카드별로 다른 내용 렌더링하려면 data 수정 필요
  }, {
    cardNumber: i + 2,
    totalCards: 5,
    style: 'gradient'
  });
  saveCard(`grant-guide-gradient-${i + 2}.html`, card.render());
});

console.log('\n✨ 모든 카드 생성 완료!');
console.log(`📁 위치: ${OUTPUT_DIR}`);
console.log('\n💡 다음 단계:');
console.log('  1. 브라우저로 HTML 열어서 확인');
console.log('  2. 스크린샷 찍기 (Chrome DevTools: 1080x1350)');
console.log('  3. 또는 Puppeteer/Playwright로 자동 캡처');