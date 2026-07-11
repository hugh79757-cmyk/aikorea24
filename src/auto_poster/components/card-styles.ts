/**
 * Bold Typography Style Cards
 * 인스타그램용 Bold Typography 스타일 카드들
 */

import { BaseCarouselCard, BRAND_TOKENS } from './carousel-cards';

export class BoldTypographyCard extends BaseCarouselCard {
  renderContent(): string {
    const { primary, secondary, accent, gray, semantic } = BRAND_TOKENS.colors;
    const { cardNumber, totalCards } = this;
    
    switch (this.data.type) {
      case 'ai-tool':
        return this.renderAIToolCard();
      case 'cover':
        return this.renderCover();
      case 'cta':
        return this.renderCTA();
      default:
        return this.renderGeneric();
    }
  }

  private renderCover(): string {
    return `
      <div class="w-[1080px] h-[1350px] relative overflow-hidden" style="background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #1e3a8a 100%);">
        <div class="absolute -top-40 -right-40 w-80 h-80 rounded-full bg-purple-600/20 blur-3xl"></div>
        <div class="absolute -bottom-40 -left-40 w-80 h-80 rounded-full bg-blue-600/20 blur-3xl"></div>
        
        <div class="relative z-10 flex flex-col items-center justify-center h-full px-12">
          <div class="mb-10 inline-flex items-center gap-3 px-6 py-3 rounded-full bg-gradient-to-r from-blue-600 to-purple-600 text-white font-semibold text-base shadow-lg">
            <span class="w-2.5 h-2.5 rounded-full bg-teal-400 animate-pulse"></span>
            이주의 AI 툴 3가지
          </div>
          
          <h1 class="text-6xl md:text-7xl font-extrabold text-white leading-none mb-6 text-center tracking-tight">
            이번 주<br>
            <span class="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-purple-400 to-teal-400">놓치면 손해</span><br>
            AI 툴 <span class="text-7xl">3가지</span>
          </h1>
          
          <div class="w-32 h-1.5 bg-gradient-to-r from-blue-400 to-purple-500 mx-auto mb-8"></div>
          
          <p class="text-xl text-white/60 font-medium text-center max-w-2xl mb-12 leading-relaxed">
            무료로 시작 가능 • 한국어 지원 • 실무 바로 적용
          </p>
          
          <div class="flex items-center justify-center gap-4 mb-12">
            <div class="w-24 h-32 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-end p-4 shadow-xl">
              <span class="text-white font-bold text-sm">#1 ChatGPT</span>
            </div>
            <div class="w-24 h-32 rounded-2xl bg-gradient-to-br from-purple-500 to-teal-500 flex items-end p-4 shadow-xl">
              <span class="text-white font-bold text-sm">#2 Midjourney</span>
            </div>
            <div class="w-24 h-32 rounded-2xl bg-gradient-to-br from-teal-500 to-blue-600 flex items-end p-4 shadow-xl">
              <span class="text-white font-bold text-sm">#3 Notion AI</span>
            </div>
          </div>
          
          <div class="flex items-center justify-center gap-6 text-white/70 text-sm font-medium">
            <span class="flex items-center gap-2 px-5 py-2 rounded-full bg-white/20 backdrop-blur-sm border border-white/30">무료 체험 가능</span>
            <span class="flex items-center gap-2 px-5 py-2 rounded-full bg-white/20 backdrop-blur-sm border border-white/30">한국어 지원</span>
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
          <span class="w-8 h-8 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center text-white font-bold text-xs border border-white/30">AI</span>
          <span class="text-white/70 text-sm font-medium">aikorea24.kr</span>
        </div>
      </div>
    `;
  }

  private renderAIToolCard(): string {
    const d = this.data;
    const gradientMap: Record<string, string> = {
      '글쓰기·마케팅': 'from-purple-600 to-pink-500',
      '이미지 생성': 'from-blue-600 to-purple-600',
      '코딩': 'from-green-600 to-teal-500',
      '영상 편집': 'from-orange-500 to-red-500',
      '음악': 'from-yellow-500 to-orange-500',
    };
    const gradient = gradientMap[d.category] || 'from-blue-600 to-purple-600';

    return `
      <div class="w-[1080px] h-[1350px] relative flex flex-col" style="background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #1e3a8a 100%);">
        <div class="absolute -top-40 -right-40 w-80 h-80 rounded-full bg-purple-600/20 blur-3xl"></div>
        <div class="absolute -bottom-40 -left-40 w-80 h-80 rounded-full bg-blue-600/20 blur-3xl"></div>
        
        <div class="flex-1 flex flex-col items-center justify-center px-12 relative z-10">
          <div class="mb-6">
            <span class="inline-flex items-center gap-2 px-5 py-2 rounded-full bg-white/10 backdrop-blur-sm border border-white/20 text-white/80 text-sm font-semibold">
              <span class="w-2 h-2 rounded-full bg-green-400"></span>
              ${d.category}
            </span>
          </div>
          
          <div class="text-center mb-6">
            <h1 class="text-6xl md:text-7xl font-extrabold text-white leading-none tracking-tight mb-4">
              ${d.titleLines.map((line, i) => `<span class="block ${i === 1 ? 'bg-gradient-to-r from-yellow-300 to-orange-400 bg-clip-text text-transparent' : ''}">${line}</span>`).join('')}
            </h1>
            <p class="text-xl font-medium text-white/60">${d.subtitle}</p>
          </div>
          
          <div class="grid grid-cols-2 gap-4 w-full max-w-4xl mb-10">
            <div class="bg-white/10 backdrop-blur-sm rounded-2xl p-6 border border-white/20 text-center">
              <div class="text-3xl font-extrabold text-white mb-1">${d.price}</div>
              <div class="text-white/60 text-sm">시작 가능</div>
            </div>
            <div class="bg-white/10 backdrop-blur-sm rounded-2xl p-6 border border-white/20 text-center">
              <div class="text-3xl font-extrabold text-white mb-1">${d.lang}</div>
              <div class="text-white/60 text-sm">완벽 지원</div>
            </div>
          </div>
          
          <div class="w-full max-w-4xl">
            <p class="text-white/70 text-lg font-medium mb-4 text-center">이런 분께 추천</p>
            <div class="flex flex-wrap justify-center gap-3">
              ${d.tags.map(tag => `<span class="px-4 py-2 rounded-full bg-white/10 border border-white/20 text-white/90 text-base font-medium">${tag}</span>`).join('')}
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

  private renderCTA(): string {
    return `
      <div class="w-[1080px] h-[1350px] relative flex flex-col" style="background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #1e3a8a 100%);">
        <div class="absolute -top-40 -right-40 w-80 h-80 rounded-full bg-purple-600/20 blur-3xl"></div>
        <div class="absolute -bottom-40 -left-40 w-80 h-80 rounded-full bg-blue-600/20 blur-3xl"></div>
        
        <div class="flex-1 flex flex-col items-center justify-center px-16 text-center relative z-10">
          <h1 class="text-4xl font-extrabold text-white leading-tight mb-8 max-w-3xl">
            이 툴들, <span class="bg-gradient-to-r from-yellow-300 to-orange-400 bg-clip-text text-transparent">직접 써보셨나요?</span>
          </h1>
          
          <div class="w-24 h-1.5 bg-gradient-to-r from-yellow-300 to-orange-400 mx-auto mb-10"></div>
          
          <p class="text-xl font-medium text-white/90 leading-relaxed mb-12 max-w-2xl">
            무료로 시작하고, 한국어로 쓰고, 내일 바로 실무에 써먹기
          </p>
          
          <a href="https://aikorea24.kr/tools" class="inline-flex items-center gap-3 px-10 py-4 rounded-full bg-gradient-to-r from-yellow-300 to-orange-400 text-gray-900 font-bold text-lg hover:from-yellow-200 hover:to-orange-300 transition-colors shadow-xl">
            <span>전체 툴 리스트 보기</span>
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3"/></svg>
          </a>
          
          <div class="mt-10 flex items-center justify-center gap-6 text-white/60 text-sm">
            <span class="flex items-center gap-2 px-5 py-2 rounded-full bg-white/20 backdrop-blur-sm border border-white/30">무료 툴만 모음</span>
            <span class="flex items-center gap-2 px-5 py-2 rounded-full bg-white/20 backdrop-blur-sm border border-white/30">한국어 완벽 지원</span>
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

  private renderGeneric(): string {
    return `
      <div class="w-[1080px] h-[1350px] flex items-center justify-center bg-gray-100">
        <div class="text-center">
          <p class="text-gray-500">${this.data.type} 카드 (${this.cardNumber}/${this.totalCards})</p>
        </div>
      </div>
    `;
  }
}

export class GradientEditorialCard extends BaseCarouselCard {
  renderContent(): string {
    const d = this.data;
    
    return `
      <div class="w-[1080px] h-[1350px] relative overflow-hidden">
        <div class="absolute inset-0 bg-gradient-to-br from-indigo-600 via-purple-600 to-pink-500"></div>
        <div class="absolute inset-0 opacity-10" style="background-image: url('data:image/svg+xml,%3Csvg width="100" height="100" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"%3E%3Cdefs%3E%3Cpattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse"%3E%3Cpath d="M 20 0 L 0 0 0 20" fill="none" stroke="white" stroke-width="0.5"/%3E%3C/pattern%3E%3C/defs%3E%3Crect width="100" height="100" fill="url(%23grid)"/%3E%3C/svg%3E');"></div>
        
        <div class="absolute -top-32 -right-32 w-64 h-64 rounded-full bg-yellow-400/20 blur-3xl"></div>
        <div class="absolute -bottom-32 -left-32 w-64 h-64 rounded-full bg-teal-400/20 blur-3xl"></div>
        
        <div class="relative z-10 h-full flex flex-col">
          <div class="flex items-start justify-between p-10 pt-16">
            <div>
              <span class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/15 backdrop-blur-sm border border-white/20 text-white text-sm font-semibold mb-4">
                <span class="w-2 h-2 rounded-full bg-yellow-300 animate-pulse"></span>
                ${d.urgency || '마감 D-3'}
              </span>
              <h1 class="text-5xl font-extrabold text-white leading-tight tracking-tight max-w-3xl">
                ${d.titleLines.map(line => `${line}<br>`).join('')}
              </h1>
            </div>
            <div class="hidden md:block w-48 h-48 rounded-3xl bg-gradient-to-br from-yellow-400/30 to-orange-500/30 border border-white/20 flex items-center justify-center">
              <svg class="w-24 h-24 text-white/80" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            </div>
          </div>
          
          <div class="flex-1 px-10 py-6">
            <div class="space-y-5">
              ${d.steps.map((step, i) => `
                <div class="flex items-start gap-5 group">
                  <div class="flex-shrink-0 w-14 h-14 rounded-2xl bg-gradient-to-br ${step.gradient || 'from-blue-400 to-purple-500'} flex items-center justify-center shadow-lg">
                    <span class="text-2xl font-extrabold text-white">${i + 1}</span>
                  </div>
                  <div class="flex-1 pt-2">
                    <div class="flex items-center gap-3 mb-2">
                      <h3 class="text-xl font-bold text-white">${step.title}</h3>
                      ${step.badge ? `<span class="px-3 py-1 rounded-full ${step.badgeColor || 'bg-purple-500/20'} text-purple-300 text-xs font-semibold">${step.badge}</span>` : ''}
                    </div>
                    <p class="text-white/70 leading-relaxed">${step.desc}</p>
                  </div>
                </div>
                ${i < d.steps.length - 1 ? `<div class="ml-7 w-0.5 h-10 bg-gradient-to-b ${step.gradient?.replace('from-', 'from-').replace('to-', 'to-') || 'from-blue-400 to-transparent'}"></div>` : ''}
              `).join('')}
            </div>
          </div>
          
          <div class="p-10 pb-16">
            <a href="${d.ctaLink}" class="block w-full max-w-xl mx-auto py-5 px-8 rounded-2xl bg-gradient-to-r from-yellow-400 to-orange-500 text-white font-bold text-lg text-center shadow-xl hover:from-yellow-300 hover:to-orange-400 transition-all">
              ${d.ctaText}
            </a>
            <p class="text-center text-white/60 text-sm mt-4">${d.ctaSubtext || '프로필 링크에서 무료 진단 시작'}</p>
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