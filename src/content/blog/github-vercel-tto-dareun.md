---
title: "GitHub Vercel 또 다른 선택지 뭐가 다를까"
description: "Vercel과 Cloudflare Pages의 차이점을 비교합니다. Next.js 프로젝트에 최적화된 Vercel의 특징과 무료 플랜 제한, 선택 기준을 안내합니다."
date: 2026-02-12T22:44:27+09:00
category: "바이브코딩"
tags:
  - "Vercel"
  - "GitHub"
  - "Nextjs"
  - "무료호스팅"
  - "웹배포"
  - "CloudflarePages"
  - "바이브코딩"
draft: false
image: "https://img.aikorea24.kr/images/github-vercel-tto-dareun/thumbnail.webp"
---

- [Vercel 공식 사이트](https://vercel.com/)
- [Vercel 가격 정책](https://vercel.com/pricing)
- [Vercel과 Cloudflare 비교](https://lapidix.dev/posts/vercel-and-aws)

---

지난 강에서 Cloudflare Pages를 사용해 웹사이트를 배포하는 방법을 배웠습니다. 그런데 인터넷을 검색하다 보면 Vercel이라는 서비스도 자주 보입니다. 특히 Next.js를 사용하는 프로젝트에서 Vercel을 많이 추천하는데, 도대체 뭐가 다른 걸까요?

결론부터 말씀드리면, 둘 다 훌륭한 무료 호스팅 서비스입니다. 정적 사이트만 배포한다면 Cloudflare Pages가 더 관대한 무료 플랜을 제공합니다. 하지만 Next.js처럼 서버 기능이 필요한 프로젝트라면 Vercel이 더 편리합니다. 각자의 특징을 알아보고 상황에 맞는 선택을 해보겠습니다.

---

## Vercel은 무엇인가

Vercel은 Next.js를 만든 회사에서 운영하는 프론트엔드 배포 플랫폼입니다. GitHub 레포지토리와 연동하면 코드를 푸시할 때마다 자동으로 빌드하고 배포합니다. Cloudflare Pages와 기본 개념은 같지만, 서버리스 함수(Serverless Functions) 지원이 강력하다는 점이 다릅니다.

가장 큰 장점은 Next.js와의 궁합입니다. Next.js의 모든 기능(SSR, ISR, API Routes 등)을 추가 설정 없이 바로 사용할 수 있습니다. 배포 과정도 매우 간단해서 Git 푸시만 하면 몇 분 안에 전 세계 CDN에 배포됩니다. 미리보기 배포(Preview Deployment) 기능으로 브랜치별로 별도 URL을 제공해 테스트하기도 편리합니다.

![4HFZUY07.webp](https://img.aikorea24.kr/images/github-vercel-tto-dareun/66e47b6d75a4042b7b4e223c282890d1a2e3f376.webp)

---

## Vercel 무료 플랜의 제한

Vercel 무료 플랜(Hobby)은 개인 프로젝트에 충분한 수준입니다. 대역폭 100GB, 서버리스 함수 실행 시간 100시간, 빌드 시간 6,000분이 제공됩니다. 프로젝트 수 제한도 없고, 커스텀 도메인도 연결할 수 있습니다.

다만 주의할 점이 있습니다. 상업적 용도로는 무료 플랜을 사용할 수 없습니다. 회사 프로젝트나 수익이 발생하는 사이트는 Pro 플랜(월 20달러)을 사용해야 합니다. 또한 팀 기능을 사용하려면 유료 플랜이 필요합니다. 개인 학습이나 포트폴리오 용도로는 무료로 충분하지만, 비즈니스 용도라면 비용을 고려해야 합니다.

---

## Cloudflare Pages와 비교

Cloudflare Pages는 대역폭이 무제한이고 상업적 사용 제한이 없습니다. 정적 사이트를 호스팅한다면 Cloudflare가 더 관대합니다. 반면 빌드 횟수가 월 500회로 제한되어 있어 자주 배포하는 프로젝트에서는 주의가 필요합니다.

Vercel은 빌드 시간 6,000분이 제공되어 빌드 횟수보다는 빌드 시간으로 제한됩니다. 복잡한 프로젝트를 자주 배포해도 여유가 있습니다. 하지만 대역폭 100GB를 초과하면 추가 비용이 발생합니다. 트래픽이 많은 사이트라면 Cloudflare가 유리합니다.

---

## 어떤 것을 선택해야 할까

Hugo, Astro 같은 정적 사이트 생성기를 사용한다면 Cloudflare Pages를 추천합니다. 대역폭 무제한, 상업적 사용 가능, 빠른 CDN이 장점입니다. 월 500회 빌드 제한도 개인 블로그 수준에서는 충분합니다.

Next.js를 사용하거나 서버 기능이 필요하다면 Vercel이 편리합니다. 설정 없이 바로 모든 기능을 사용할 수 있고, 개발 경험이 뛰어납니다. 둘 다 무료 플랜이 있으니 직접 사용해 보고 결정하는 것도 좋은 방법입니다.

---

## Vercel 배포하기

Vercel 사용법은 Cloudflare Pages와 거의 동일합니다. vercel.com에서 GitHub 계정으로 가입하고, Import Project를 클릭해서 레포지토리를 선택합니다. 프레임워크를 자동으로 감지해서 빌드 설정을 제안해 주며, Deploy 버튼을 클릭하면 배포가 시작됩니다.

배포가 완료되면 프로젝트이름.vercel.app 형태의 무료 도메인이 제공됩니다. 이후에는 코드를 푸시할 때마다 자동으로 재배포됩니다. Cloudflare Pages를 사용해 본 분이라면 거의 동일한 경험이라 금방 익숙해지실 겁니다.

---

## 결론

Vercel과 Cloudflare Pages 모두 훌륭한 무료 호스팅 서비스입니다. 정적 사이트는 Cloudflare Pages, Next.js 프로젝트는 Vercel이 더 적합합니다. 둘 다 GitHub과 연동되어 자동 배포가 가능하고, 무료 플랜만으로도 개인 프로젝트에는 충분합니다. 다음 강에서는 가장 단순한 선택지인 GitHub Pages에 대해 알아보겠습니다.

---

#Vercel #GitHub #Nextjs #무료호스팅 #웹배포 #CloudflarePages #바이브코딩 #프론트엔드배포 #서버리스 #자동배포