/**
 * Instagram Carousel Card Generator
 * aikorea24.kr 브랜드에 맞춘 캐러셀 카드 자동 생성
 * 
 * 사용법:
 *   import { CarouselCard, CarouselBuilder } from './carousel-cards';
 *   
 *   const card = CarouselCard.formatD(1, { hook: "...", number: "40%" });
 *   const html = card.render();
 */

// ============================================
// 브랜드 토큰 (design-system 스킬 연동)
// ============================================
export const BRAND_TOKENS = {
  colors: {
    primary: {
      50: '#eff6ff',
      100: '#dbeafe',
      200: '#bfdbfe',
      300: '#93c5fd',
      400: '#60a5fa',
      500: '#3b82f6',
      600: '#2563eb',  // Electric Blue - 메인
      700: '#1d4ed8',
      800: '#1e40af',
      900: '#1e3a8a',
    },
    secondary: {
      50: '#f5f3ff',
      100: '#ede9fe',
      200: '#ddd6fe',
      300: '#c4b5fd',
      400: '#a78bfa',
      500: '#8b5cf6',
      600: '#7c3aed',  // Violet - 서브
      700: '#6d28d9',
      800: '#5b21b6',
      900: '#4c1d95',
    },
    accent: {
      50: '#f0fdfa',
      100: '#ccfbf1',
      200: '#99f6e4',
      300: '#5eead4',
      400: '#2dd4bf',
      500: '#14b8a6',  // Teal - 액센트
      600: '#0d9488',
      700: '#0f766e',
      800: '#115e59',
      900: '#134e4a',
    },
    gray: {
      50: '#f9fafb',
      100: '#f3f4f6',
      200: '#e5e7eb',
      300: '#d1d5db',
      400: '#9ca3af',
      500: '#6b7280',
      600: '#4b5563',
      700: '#374151',
      800: '#1f2937',
      900: '#111827',
    },
    semantic: {
      success: '#10b981',
      warning: '#f59e0b',
      danger: '#ef4444',
      info: '#3b82f6',
    }
  },
  fonts: {
    korean: '"Pretendard", -apple-system, BlinkMacSystemFont, "Noto Sans KR", sans-serif',
    latin: '"Inter", -apple-system, BlinkMacSystemFont, sans-serif',
  },
  spacing: {
    card: { width: 1080, height: 1350 },
    safeZone: { width: 864, height: 1080 }, // 80%
    gutter: 48,
  },
  borderRadius: {
    sm: '8px',
    md: '12px',
    lg: '16px',
    xl: '24px',
    full: '9999px',
  },
  shadows: {
    card: '0 4px 24px rgba(0,0,0,0.08)',
    cardHover: '0 8px 40px rgba(0,0,0,0.12)',
    glow: '0 0 40px rgba(37,99,235,0.3)',
  }
} as const;

// ============================================
// 기본 카드 클래스
// ============================================
export abstract class BaseCarouselCard {
  protected data: Record<string, any>;
  protected cardNumber: number;
  protected totalCards: number;
  protected style: 'minimalist' | 'bold' | 'gradient';

  constructor(data: Record<string, any>, options: { 
    cardNumber: number; 
    totalCards: number; 
    style: 'minimalist' | 'bold' | 'gradient';
  }) {
    this.data = data;
    this.cardNumber = options.cardNumber;
    this.totalCards = options.totalCards;
    this.style = options.style;
  }

  // 공통: 상단 인디케이터
  protected renderIndicator(): string {
    const { primary, gray } = BRAND_TOKENS.colors;
    return `
      <div class="flex items-center justify-center pt-12 px-8">
        <div class="flex items-center gap-3">
          <span class="px-4 py-1.5 rounded-full bg-gradient-to-r from-[${primary[600]}] to-[${primary[700]}] text-white text-sm font-semibold">
            펀치 브리핑
          </span>
          <span class="w-12 h-px bg-gradient-to-r from-[${primary[600]}] to-[${primary[700]}]"></span>
          <span class="text-[${gray[400]}] text-sm">${this.cardNumber}/${this.totalCards}</span>
        </div>
      </div>
    `;
  }

  // 공통: 하단 브랜딩
  protected renderBranding(): string {
    const { primary, gray } = BRAND_TOKENS.colors;
    return `
      <div class="absolute bottom-16 left-1/2 -translate-x-1/2 flex items-center gap-3">
        <span class="w-8 h-8 rounded-full bg-gradient-to-r from-[${primary[600]}] to-[${primary[700]}] flex items-center justify-center text-white font-bold text-xs">AI</span>
        <span class="text-[${gray[400]}] text-sm font-medium">aikorea24.kr</span>
      </div>
    `;
  }

  // 공통: 스와이프 힌트 (첫 카드만)
  protected renderSwipeHint(isFirst: boolean): string {
    if (!isFirst) return '';
    const { gray } = BRAND_TOKENS.colors;
    return `
      <div class="absolute bottom-8 left-1/2 -translate-x-1/2 flex items-center gap-2 text-[${gray[300]}] text-sm animate-bounce">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
        <span>왼쪽으로 넘겨보기</span>
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
      </div>
    `;
  }

  abstract renderContent(): string;

  render(): string {
    const isFirst = this.cardNumber === 1;
    return `
      <!DOCTYPE html>
      <html lang="ko">
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=1080, height=1350">
        <title>aikorea24 - Card ${this.cardNumber}</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
        <style>
          * { font-family: 'Pretendard', sans-serif; }
          .carousel-card { width: 1080px; height: 1350px; }
        </style>
      </head>
      <body>
        <div class="carousel-card relative overflow-hidden bg-white flex flex-col">
          ${this.renderIndicator()}
          <div class="flex-1 flex flex-col">
            ${this.renderContent()}
          </div>
          ${this.renderBranding()}
          ${this.renderSwipeHint(isFirst)}
        </div>
      </body>
      </html>
    `;
  }
}

// 스타일별 구현체
import { MinimalistCard, BoldTypographyCard, GradientEditorialCard } from './card-styles';

  private renderHook(): string {
    const { primary, gray } = BRAND_TOKENS.colors;
    return `
      <div class="flex flex-col items-center justify-center px-16 py-20 relative">
        <div class="absolute top-0 left-1/2 -translate-x-1/2 w-3/4 h-1 bg-gradient-to-r from-[${BRAND_TOKENS.colors.primary[600]}] via-[${BRAND_TOKENS.colors.secondary[600]}] to-[${BRAND_TOKENS.colors.accent[500]}]"></div>
        <div class="absolute top-16 left-16 text-[${BRAND_TOKENS.colors.primary[600]}] font-bold text-4xl">${this.cardNumber}</div>
        
        <div class="text-center z-10">
          <p class="text-5xl font-extrabold text-gray-900 leading-tight mb-8 tracking-tight">
            ${this.data.hookLine1 || '틱톡이 감원한다던'}<br>
            <span class="text-[${BRAND_TOKENS.colors.primary[600]}]">${this.data.hookNumber || '667명'}</span> ${this.data.hookLine2 || '의 정체'}
          </p>
          
          <div class="w-24 h-1 bg-gradient-to-r from-[${BRAND_TOKENS.colors.primary[600]}] to-[${BRAND_TOKENS.colors.secondary[600]}] mx-auto mb-8"></div>
          
          <p class="text-xl text-gray-600 font-medium leading-relaxed max-w-2xl mx-auto">
            ${this.data.subtext || '"약 300명"이라던 공식 발표<br>내부 문서엔 <span class="font-bold text-gray-900">2배 넘는 667명</span>'}
          </p>
        </div>
      </div>
    `;
  }

  private renderConflict(): string {
    return `
      <div class="flex flex-col items-center justify-center px-16 py-20 relative">
        <div class="absolute top-0 left-1/2 -translate-x-1/2 w-3/4 h-1 bg-gradient-to-r from-[${BRAND_TOKENS.colors.primary[600]}] via-[${BRAND_TOKENS.colors.secondary[600]}] to-[${BRAND_TOKENS.colors.accent[500]}]"></div>
        <div class="absolute top-16 left-16 text-[${BRAND_TOKENS.colors.primary[600]}] font-bold text-4xl">${this.cardNumber}</div>
        
        <div class="text-center z-10">
          <p class="text-2xl font-semibold text-gray-500 mb-6">충돌 A면: 무엇이 문제인가</p>
          
          <div class="bg-gray-50 rounded-2xl p-10 mb-8 max-w-3xl mx-auto border border-gray-100">
            <p class="text-3xl font-bold text-gray-900 leading-tight mb-6">
              잘리는 팀 = <span class="text-[${BRAND_TOKENS.colors.semantic.danger]}">${this.data.topic || '자살 챌린지 영상'}</span>을<br>
              사람 눈으로 걸러내던 <span class="text-gray-900">${this.data.teamName || '검수팀'}</span>
            </p>
            <div class="w-20 h-0.5 bg-[${BRAND_TOKENS.colors.semantic.danger}] mx-auto mb-6"></div>
            <p class="text-lg text-gray-600 leading-relaxed">
              ${this.data.stats || '더블린 전체 직원의 40%<br>ADSO(AI 데이터 서비스·운영)팀 전원'}
            </p>
          </div>
          
          <div class="flex items-center justify-center gap-4 text-sm text-gray-500">
            <span class="flex items-center gap-1"><svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z"></path></svg> 사람 눈 필요</span>
            <span class="flex items-center gap-1"><svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM10 18a3 3 0 01-3-3h6a3 3 0 01-3 3z"></path></svg> 알고리즘 우회</span>
          </div>
        </div>
      </div>
    `;
  }

  private renderTwist(): string {
    return `
      <div class="flex flex-col items-center justify-center px-16 py-20 relative">
        <div class="absolute top-0 left-1/2 -translate-x-1/2 w-3/4 h-1 bg-gradient-to-r from-[${BRAND_TOKENS.colors.primary[600]}] via-[${BRAND_TOKENS.colors.secondary[600]}] to-[${BRAND_TOKENS.colors.accent[500]}]"></div>
        <div class="absolute top-16 left-16 text-[${BRAND_TOKENS.colors.primary[600]}] font-bold text-4xl">${this.cardNumber}</div>
        
        <div class="text-center z-10">
          <p class="text-2xl font-semibold text-gray-500 mb-6">반전: AI가 놓치는 것</p>
          
          <div class="bg-gradient-to-br from-[${BRAND_TOKENS.colors.secondary[50]}] to-[${BRAND_TOKENS.colors.primary[50]}] rounded-2xl p-10 mb-8 max-w-3xl mx-auto border border-[${BRAND_TOKENS.colors.secondary[100]}] relative">
            <svg class="absolute top-6 left-6 w-12 h-12 text-[${BRAND_TOKENS.colors.secondary[200]}]" fill="currentColor" viewBox="0 0 24 24"><path d="M14.017 21v-7.391c0-5.704 3.731-9.57 8.983-10.609l.995 2.151c-2.431.917-3.995 3.638-3.995 5.849h4v10h-9.983zm-14.017 0v-7.391c0-5.704 3.748-9.57 9-10.609l.996 2.151c-2.431.917-3.995 3.638-3.995 5.849h3.983v10h-9.983z"/></svg>
            
            <p class="text-2xl font-medium text-gray-800 leading-tight mb-6 relative z-10">
              ${this.data.quote || '"애들한테 자살 챌린지 올리는 놈들은<br>알고리즘 피하는 데 <span class="text-[${BRAND_TOKENS.colors.secondary[600]}] font-bold">도가 텄다</span>"'}
            </p>
            
            <div class="w-20 h-0.5 bg-[${BRAND_TOKENS.colors.secondary[500]}] mx-auto mb-6"></div>
            
            <p class="text-lg text-gray-700 leading-relaxed relative z-10">
              유해 콘텐츠는 계속 변한다<br>
              <span class="font-bold text-gray-900">AI도 사람이 계속 업데이트해줘야 한다</span>
            </p>
          </div>
          
          <p class="text-sm text-gray-500">— ${this.data.source || '익명의 틱톡 검수 직원 내부 게시판 글'}</p>
        </div>
      </div>
    `;
  }

  private renderExpansion(): string {
    const items = this.data.items || [
      { icon: 'check', title: '노조의 지적', desc: '"AI는 핑계일 뿐, 싼 나라로 아웃소싱 가속화"', color: 'primary' },
      { icon: 'shield', title: '정부 경고', desc: '"AI가 만드는 파괴적 영향, 불확실성 그대로 보여줘"', color: 'secondary' },
      { icon: 'sparkles', title: '핵심 포인트', desc: 'AI가 제일 먼저 먹는 일자리 = 창의직이 아닌 \'안전\' 직군', color: 'accent' },
    ];

    const cards = items.map((item, i) => {
      const colorMap = {
        primary: { bg: 'bg-blue-100', iconBg: 'bg-blue-100', iconColor: 'text-blue-600', border: 'border-blue-200' },
        secondary: { bg: 'bg-purple-100', iconBg: 'bg-purple-100', iconColor: 'text-purple-600', border: 'border-purple-200' },
        accent: { bg: 'bg-teal-100', iconBg: 'bg-teal-100', iconColor: 'text-teal-600', border: 'border-teal-200' },
      }[item.color] || { bg: 'bg-gray-100', iconBg: 'bg-gray-100', iconColor: 'text-gray-600', border: 'border-gray-200' };

      const icons = {
        check: '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
        shield: '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/></svg>',
        sparkles: '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/></svg>',
      };

      return `
        <div class="${itemMap.bg} rounded-2xl p-8 border ${itemMap.border} text-left">
          <div class="flex items-center gap-4 mb-4">
            <div class="w-12 h-12 rounded-xl ${itemMap.iconBg} flex items-center justify-center">
              ${icons[item.icon as keyof typeof icons] || icons.check}
            </div>
            <p class="text-xl font-bold text-gray-900">${item.title}</p>
          </div>
          <p class="text-gray-600 leading-relaxed">${item.desc}</p>
        </div>
      `;
    }).join('');

    return `
      <div class="flex flex-col items-center justify-center px-16 py-20 relative">
        <div class="absolute top-0 left-1/2 -translate-x-1/2 w-3/4 h-1 bg-gradient-to-r from-[${BRAND_TOKENS.colors.primary[600]}] via-[${BRAND_TOKENS.colors.secondary[600]}] to-[${BRAND_TOKENS.colors.accent[500]}]"></div>
        <div class="absolute top-16 left-16 text-[${BRAND_TOKENS.colors.primary[600]}] font-bold text-4xl">${this.cardNumber}</div>
        
        <div class="text-center z-10">
          <p class="text-2xl font-semibold text-gray-500 mb-6">확장: 이게 왜 중요할까</p>
          
          <div class="space-y-6 max-w-3xl mx-auto">
            ${cards}
          </div>
        </div>
      </div>
    `;
  }

  private renderCTA(): string {
    const { primary, secondary } = BRAND_TOKENS.colors;
    return `
      <div class="flex flex-col items-center justify-center px-16 py-20 relative text-center">
        <div class="absolute top-0 left-1/2 -translate-x-1/2 w-3/4 h-1 bg-gradient-to-r from-[${primary[600]}] via-[${secondary[600]}] to-[${BRAND_TOKENS.colors.accent[500]}]"></div>
        <div class="absolute top-16 left-16 text-[${primary[600]}] font-bold text-4xl">${this.cardNumber}</div>
        
        <div class="z-10 max-w-2xl">
          <p class="text-3xl font-extrabold text-gray-900 leading-tight mb-6">
            ${this.data.title || '최악을 막아주던 사람이 사라진 자리에<br>그걸 자꾸 놓치는 AI가 들어올 때,'}
          </p>
          <p class="text-xl text-gray-600 leading-relaxed mb-10">
            ${this.data.subtitle || '당신 피드는 더 안전해지는 걸까<br>아니면 그 반대일까.'}
          </p>
          
          <a href="${this.data.link || 'https://aikorea24.kr'}" class="inline-flex items-center gap-3 px-8 py-4 rounded-2xl bg-gradient-to-r from-[${primary[600]}] to-[${secondary[600]}] text-white font-bold text-lg shadow-lg hover:from-[${primary[500]}] hover:to-[${secondary[500]}] transition-all">
            ${this.data.ctaText || '전체 기사 읽으러 가기'}
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3"/></svg>
          </a>
        </div>
      </div>
    `;
  }

  private renderGeneric(): string {
    return `
      <div class="flex flex-col items-center justify-center px-16 py-20 text-center">
        <p class="text-3xl font-bold text-gray-900 mb-4">${this.data.title || '카드 제목'}</p>
        <p class="text-gray-600 leading-relaxed">${this.data.content || '카드 내용'}</p>
      </div>
    `;
  }
}

// --- Bold Typography Style ---
export class BoldTypographyCard extends BaseCarouselCard {
  renderContent(): string {
    // Bold style: 큰 한글 타이포그래피가 주인공
    const { primary, secondary, gray, semantic } = BRAND_TOKENS.colors;
    
    return `
      <div class="w-[1080px] h-[1350px] relative flex flex-col" style="background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #1e3a8a 100%);">
        <div class="absolute -top-40 -right-40 w-80 h-80 rounded-full bg-purple-600/20 blur-3xl"></div>
        <div class="absolute -bottom-40 -left-40 w-80 h-80 rounded-full bg-blue-600/20 blur-3xl"></div>
        
        <div class="flex-1 flex flex-col items-center justify-center px-12 relative z-10">
          ${this.data.category ? `
            <div class="mb-6">
              <span class="inline-flex items-center gap-2 px-5 py-2 rounded-full bg-white/10 backdrop-blur-sm border border-white/20 text-white/80 text-sm font-semibold">
                <span class="w-2 h-2 rounded-full bg-green-400"></span>
                ${this.data.category}
              </span>
            </div>
          ` : ''}
          
          <div class="text-center mb-6">
            <h1 class="text-6xl md:text-7xl font-extrabold text-white leading-none tracking-tight mb-4">
              ${this.data.titleLines?.map((line: string, i: number) => 
                `<span class="block ${i === 1 ? 'bg-gradient-to-r from-yellow-300 to-orange-400 bg-clip-text text-transparent' : ''}">${line}</span>`
              ).join('') || this.data.title || '도구명'}
            </h1>
            <p class="text-xl font-medium text-white/60">${this.data.subtitle || '한줄 설명'}</p>
          </div>
          
          <div class="grid grid-cols-2 gap-4 w-full max-w-4xl mb-10">
            <div class="bg-white/10 backdrop-blur-sm rounded-2xl p-6 border border-white/20 text-center">
              <div class="text-3xl font-extrabold text-white mb-1">${this.data.price || '무료'}</div>
              <div class="text-white/60 text-sm">시작 가능</div>
            </div>
            <div class="bg-white/10 backdrop-blur-sm rounded-2xl p-6 border border-white/20 text-center">
              <div class="text-3xl font-extrabold text-white mb-1">${this.data.lang || '한국어'}</div>
              <div class="text-white/60 text-sm">완벽 지원</div>
            </div>
          </div>
          
          <div class="w-full max-w-4xl">
            <p class="text-white/70 text-lg font-medium mb-4 text-center">이런 분께 추천</p>
            <div class="flex flex-wrap justify-center gap-3">
              ${(this.data.tags || ['블로그 글쓰기', '마케팅 카피', '이메일 초안', '아이디어 발상']).map(tag => 
                `<span class="px-4 py-2 rounded-full bg-white/10 border border-white/20 text-white/90 text-base font-medium">${tag}</span>`
              ).join('')}
            </div>
          </div>
        </div>
        
        <div class="absolute bottom-16 left-1/2 -translate-x-1/2 flex items-center gap-4">
          <div class="flex gap-2">
            <div class="w-2.5 h-2.5 rounded-full bg-white/30"></div>
            <div class="w-2.5 h-2.5 rounded-full bg-white"></div>
            <div class="w-2.5 h-2.5 rounded-full bg-white/30"></div>
          </div>
        </div>
        
        <div class="absolute bottom-8 left-1/2 -translate-x-1/2 flex items-center gap-3">
          <span class="w-8 h-8 rounded-full bg-white/10 backdrop-blur-sm flex items-center justify-center text-white font-bold text-xs border border-white/20">AI</span>
          <span class="text-white/70 text-sm font-medium">aikorea24.kr</span>
        </div>
      </div>
    `;
  }
}

// --- Gradient Editorial Style ---
export class GradientEditorialCard extends BaseCarouselCard {
  renderContent(): string {
    // Grant guide, multi-step guides
    return `
      <div class="w-[1080px] h-[1350px] relative overflow-hidden">
        <div class="absolute inset-0 bg-gradient-to-br from-indigo-600 via-purple-600 to-pink-500"></div>
        <div class="absolute inset-0 opacity-10" style="background-image: url('data:image/svg+xml,%3Csvg width=\"100\" height=\"100\" viewBox=\"0 0 100 100\" xmlns=\"http://www.w3.org/2000/svg\"%3E%3Cdefs%3E%3Cpattern id=\"grid\" width=\"20\" height=\"20\" patternUnits=\"userSpaceOnUse\"%3E%3Cpath d=\"M 20 0 L 0 0 0 20\" fill=\"none\" stroke=\"white\" stroke-width=\"0.5\"/%3E%3C/pattern%3E%3C/defs%3E%3Crect width=\"100\" height=\"100\" fill=\"url(%23grid)\"/%3E%3C/svg%3E');"></div>
        
        <div class="absolute -top-32 -right-32 w-64 h-64 rounded-full bg-yellow-400/20 blur-3xl"></div>
        <div class="absolute -bottom-32 -left-32 w-64 h-64 rounded-full bg-teal-400/20 blur-3xl"></div>
        
        <div class="relative z-10 h-full flex flex-col">
          <div class="flex items-start justify-between p-10 pt-16">
            <div>
              ${this.data.urgency ? `
                <span class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/15 backdrop-blur-sm border border-white/20 text-white text-sm font-semibold mb-4">
                  <span class="w-2 h-2 rounded-full bg-yellow-300 animate-pulse"></span>
                  ${this.data.urgency}
                </span>
              ` : ''}
              <h1 class="text-5xl font-extrabold text-white leading-tight tracking-tight max-w-3xl">
                ${this.data.titleLines?.map((line: string, i: number) => 
                  `<span class="block ${i === 1 ? 'bg-gradient-to-r from-yellow-300 to-orange-400 bg-clip-text text-transparent' : ''}">${line}</span>`
                ).join('<br>') || this.data.title || '제목'}
              </h1>
            </div>
            <div class="hidden md:block w-48 h-48 rounded-3xl bg-gradient-to-br from-yellow-400/30 to-orange-500/30 border border-white/20 flex items-center justify-center">
              <svg class="w-24 h-24 text-white/80" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            </div>
          </div>
          
          <div class="flex-1 px-10 py-6">
            <div class="space-y-5">
              ${(this.data.steps || []).map((step: any, idx: number) => `
                <div class="flex items-start gap-5 group">
                  <div class="flex-shrink-0 w-14 h-14 rounded-2xl ${step.gradient || 'bg-gradient-to-br from-yellow-400 to-orange-500'} flex items-center justify-center shadow-lg">
                    <span class="text-2xl font-extrabold text-white">${idx + 1}</span>
                  </div>
                  <div class="flex-1 pt-2">
                    <div class="flex items-center gap-3 mb-2">
                      <h3 class="text-xl font-bold text-white">${step.title}</h3>
                      ${step.badge ? `<span class="px-3 py-1 rounded-full ${step.badgeColor || 'bg-green-500/20'} text-green-300 text-xs font-semibold">${step.badge}</span>` : ''}
                    </div>
                    <p class="text-white/70 leading-relaxed">${step.desc}</p>
                  </div>
                </div>
                ${idx < (this.data.steps?.length || 1) - 1 ? `
                  <div class="ml-7 w-0.5 h-10 bg-gradient-to-b from-yellow-400 to-transparent"></div>
                ` : ''}
              `).join('')}
            </div>
          </div>
          
          <div class="p-10 pb-16">
            <a href="${this.data.ctaLink || '#'}" class="block w-full max-w-xl mx-auto py-5 px-8 rounded-2xl bg-gradient-to-r from-yellow-400 to-orange-500 text-white font-bold text-lg text-center shadow-xl hover:from-yellow-300 hover:to-orange-400 transition-all">
              ${this.data.ctaText || '지금 자격 진단하러 가기 →'}
            </a>
            <p class="text-center text-white/60 text-sm mt-4">${this.data.ctaSubtext || '프로필 링크에서 무료 진단 시작'}</p>
          </div>
        </div>
        
        <div class="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-3">
          <span class="w-7 h-7 rounded-full bg-white/15 backdrop-blur-sm flex items-center justify-center text-white font-bold text-xs border border-white/20">AI</span>
          <span class="text-white/70 text-sm font-medium">aikorea24.kr</span>
        </div>
      </div>
    `;
  }
}

// ============================================
// 빌더 패턴으로 쉽게 생성
// ============================================
export class CarouselBuilder {
  private cards: BaseCarouselCard[] = [];
  private style: 'minimalist' | 'bold' | 'gradient' = 'minimalist';

  setStyle(style: 'minimalist' | 'bold' | 'gradient'): this {
    this.style = style;
    return this;
  }

  addFormatD(data: {
    hook?: { hookLine1: string; hookLine2: string; hookNumber: string; subtext: string };
    conflict?: { topic: string; teamName: string; stats: string };
    twist?: { quote: string; source: string };
    expansion?: { items: Array<{ icon: string; title: string; desc: string; color: 'primary' | 'secondary' | 'accent' }> };
    cta?: { title: string; subtitle: string; link: string; ctaText: string };
  }): this {
    if (this.style === 'minimalist') {
      if (data.hook) this.cards.push(new MinimalistCard({ type: 'hook', ...data.hook }, { cardNumber: this.cards.length + 1, totalCards: 5, style: 'minimalist' }));
      if (data.conflict) this.cards.push(new MinimalistCard({ type: 'conflict', ...data.conflict }, { cardNumber: this.cards.length + 1, totalCards: 5, style: 'minimalist' }));
      if (data.twist) this.cards.push(new MinimalistCard({ type: 'twist', ...data.twist }, { cardNumber: this.cards.length + 1, totalCards: 5, style: 'minimalist' }));
      if (data.expansion) this.cards.push(new MinimalistCard({ type: 'expansion', items: data.expansion.items }, { cardNumber: this.cards.length + 1, totalCards: 5, style: 'minimalist' }));
      if (data.cta) this.cards.push(new MinimalistCard({ type: 'cta', ...data.cta }, { cardNumber: this.cards.length + 1, totalCards: 5, style: 'minimalist' }));
    }
    return this;
  }

  addAITool(data: {
    category: string;
    titleLines: string[];
    subtitle: string;
    price: string;
    lang: string;
    tags: string[];
  }): this {
    if (this.style === 'bold') {
      this.cards.push(new BoldTypographyCard(
        { type: 'ai-tool', ...data },
        { cardNumber: this.cards.length + 1, totalCards: 4, style: 'bold' }
      ));
    }
    return this;
  }

  addGrantGuide(data: {
    urgency?: string;
    titleLines: string[];
    steps: Array<{ title: string; desc: string; badge?: string; badgeColor?: string; gradient?: string }>;
    ctaLink: string;
    ctaText: string;
    ctaSubtext?: string;
  }): this {
    if (this.style === 'gradient') {
      this.cards.push(new GradientEditorialCard(
        { type: 'grant-guide', ...data },
        { cardNumber: 1, totalCards: 1, style: 'gradient' }
      ));
    }
    return this;
  }

  build(): BaseCarouselCard[] {
    return this.cards;
  }

  renderAll(): string[] {
    return this.cards.map(card => card.render());
  }

  saveAll(dir: string): void {
    const fs = require('fs');
    const path = require('path');
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    
    this.cards.forEach((card, i) => {
      const filename = `${this.style}-card-${i + 1}.html`;
      fs.writeFileSync(path.join(dir, filename), card.render());
    });
  }
}

// ============================================
// 편의 함수들
// ============================================
export function createFormatDCarousel(data: Parameters<CarouselBuilder['addFormatD']>[0], style: 'minimalist' = 'minimalist') {
  return new CarouselBuilder()
    .setStyle(style)
    .addFormatD(data)
    .build();
}

export function createAIToolCarousel(tools: Parameters<CarouselBuilder['addAITool']>[0][], style: 'bold' = 'bold') {
  const builder = new CarouselBuilder().setStyle(style);
  tools.forEach(tool => builder.addAITool(tool));
  return builder.build();
}

export function createGrantGuideCarousel(data: Parameters<CarouselBuilder['addGrantGuide']>[0], style: 'gradient' = 'gradient') {
  return new CarouselBuilder()
    .setStyle(style)
    .addGrantGuide(data)
    .build();
}

// ============================================
// 사용 예시 (직접 실행 가능)
// ============================================
if (require.main === module) {
  // Format D 예시
  const formatD = createFormatDCarousel({
    hook: {
      hookLine1: '틱톡이 감원한다던',
      hookLine2: '의 정체',
      hookNumber: '667명',
      subtext: '"약 300명"이라던 공식 발표\n내부 문서엔 <span class="font-bold text-gray-900">2배 넘는 667명</span>'
    },
    conflict: {
      topic: '자살 챌린지 영상',
      teamName: '검수팀',
      stats: '더블린 전체 직원의 40%\nADSO(AI 데이터 서비스·운영)팀 전원'
    },
    twist: {
      quote: '"애들한테 자살 챌린지 올리는 놈들은\n알고리즘 피하는 데 <span class="text-purple-600 font-bold">도가 텄다</span>"',
      source: '익명의 틱톡 검수 직원 내부 게시판 글'
    },
    expansion: {
      items: [
        { icon: 'check', title: '노조의 지적', desc: '"AI는 핑계일 뿐, 싼 나라로 아웃소싱 가속화"', color: 'primary' },
        { icon: 'shield', title: '정부 경고', desc: '"AI가 만드는 파괴적 영향, 불확실성 그대로 보여줘"', color: 'secondary' },
        { icon: 'sparkles', title: '핵심 포인트', desc: 'AI가 제일 먼저 먹는 일자리 = 창의직이 아닌 \'안전\' 직군', color: 'accent' },
      ]
    },
    cta: {
      title: '최악을 막아주던 사람이 사라진 자리에\n그걸 자꾸 놓치는 AI가 들어올 때,',
      subtitle: '당신 피드는 더 안전해지는 걸까\n아니면 그 반대일까.',
      link: 'https://aikorea24.kr',
      ctaText: '전체 기사 읽으러 가기'
    }
  });

  formatD.forEach((card, i) => {
    require('fs').writeFileSync(`/Users/twinssn/Desktop/메모 Hugh-v2/프로젝트/aikorea24/instagram-carousel-templates/generated/format-d-card-${i+1}.html`, card.render());
  });
  console.log('✅ Format D 캐러셀 5장 생성 완료');
}