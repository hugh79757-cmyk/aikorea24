---
title: "웹사이트를 0원에 배포하는 방법: Cloudflare Pages 가이드"
description: "GitHub와 Cloudflare Pages를 사용해서 내 웹사이트를 완전 무료로 전 세계에 배포하는 방법을 단계별로 안내합니다."
date: 2026-02-10
category: "AI입문"
tags: ["Cloudflare", "배포", "무료", "GitHub", "웹사이트"]
---

## 왜 Cloudflare Pages인가?

웹사이트를 만들었으면 인터넷에 올려야 다른 사람들이 볼 수 있습니다. 이것을 '배포'라고 합니다. Cloudflare Pages는 배포 서비스 중 무료 플랜이 가장 넉넉합니다.

대역폭(사람들이 사이트에 접속할 때 사용되는 데이터) 무제한, 월 500회 빌드, 한국을 포함한 전 세계 CDN을 무료로 제공합니다.

## 준비물

필요한 것은 두 가지뿐입니다. GitHub 계정과 Cloudflare 계정이며, 둘 다 무료로 만들 수 있습니다.

## 단계별 가이드

**1단계: GitHub에 코드 올리기**

GitHub에 가입하고 새 저장소(Repository)를 만듭니다. 웹사이트 파일을 이 저장소에 업로드합니다.

**2단계: Cloudflare Pages 연결**

Cloudflare 대시보드에서 Workers & Pages를 선택하고, Create를 누른 뒤 GitHub 저장소를 연결합니다.

**3단계: 빌드 설정**

프레임워크에 맞는 빌드 명령어를 입력합니다. Astro의 경우 빌드 명령어는 `npm run build`, 출력 디렉터리는 `dist`입니다.

**4단계: 배포 완료**

Save and Deploy를 누르면 1-2분 내에 `프로젝트명.pages.dev` 주소로 사이트가 공개됩니다.

이후 코드를 수정하고 GitHub에 푸시하면 자동으로 재배포됩니다. 완전 자동화입니다.
