---
title: "GitHub Cloudflare Pages 무료로 세상에 공개하는 최고의 조합"
description: "GitHub과 Cloudflare Pages를 연동해서 웹사이트를 무료로 배포하는 방법을 안내합니다. 호스팅 비용 없이 전문적인 웹사이트를 운영할 수 있습니다."
date: 2026-02-12T22:39:55+09:00
category: "개발배포"
tags:
  - "CloudflarePages"
  - "GitHub"
  - "무료호스팅"
  - "웹배포"
  - "정적사이트"
  - "바이브코딩"
  - "무료웹사이트"
draft: false
image: "https://img.aikorea24.kr/images/github-cloudflare-pages-muryoro/thumbnail.webp"
---

- [Cloudflare Pages 공식 사이트](https://pages.cloudflare.com/)
- [Cloudflare 가입](https://dash.cloudflare.com/sign-up)
- [GitHub Pages 가이드](https://pages.github.com/)

---

코드를 GitHub에 올렸습니다. 하지만 이 상태로는 다른 사람이 여러분의 웹사이트를 볼 수 없습니다. 웹사이트를 인터넷에 공개하려면 "호스팅"이 필요합니다. 호스팅은 보통 월 몇 천 원에서 몇 만 원의 비용이 드는데, 정적 사이트라면 완전 무료로 호스팅할 수 있습니다.

GitHub Pages와 Cloudflare Pages가 대표적인 무료 호스팅 서비스입니다. 둘 다 GitHub 레포지토리와 연동해서 자동으로 웹사이트를 배포합니다. 코드를 푸시하면 몇 초 후에 변경 사항이 반영됩니다. 이번 강에서는 Cloudflare Pages를 사용해서 웹사이트를 세상에 공개하는 방법을 알아보겠습니다.

---

## Cloudflare Pages 선택 이유

GitHub Pages도 훌륭하지만 Cloudflare Pages를 추천하는 이유가 있습니다. 첫째, 빌드 속도가 빠릅니다. Hugo, Astro 같은 정적 사이트 생성기를 자동으로 빌드해 줍니다. 둘째, 전 세계 CDN(콘텐츠 전송 네트워크)을 통해 어디서든 빠르게 접속됩니다. 셋째, 무료 SSL 인증서가 자동으로 적용되어 https로 안전하게 접속할 수 있습니다.

또한 비공개 레포지토리에서도 무료로 배포할 수 있습니다. GitHub Pages는 무료 플랜에서 공개 레포지토리만 지원하지만, Cloudflare Pages는 비공개 레포지토리도 연결할 수 있습니다. 월 요청 횟수 제한도 일반 개인 블로그 수준에서는 신경 쓸 필요가 없을 만큼 넉넉합니다.

[클플페-클라우드 플레어 페이지를 이용한 웹사이트](https://informationhot.kr)

위의 사이트를 방문해서 속도가 얼마나 빠른지 한번 시험해보세요. 티스토리나 워드프레스 사이트와 같이 애드센스 광고도 노출이 됩니다.  

---

## Cloudflare 계정 만들기

Cloudflare 공식 사이트(cloudflare.com)에 접속해서 Sign up 버튼을 클릭합니다. 이메일과 비밀번호를 입력하면 계정이 생성됩니다. 이메일 인증을 완료한 후 대시보드에 접속합니다.

왼쪽 메뉴에서 "Workers & Pages"를 클릭합니다. 여기서 Pages 프로젝트를 생성할 수 있습니다. "Create application" 또는 "Create a project" 버튼을 클릭하고 "Pages" 탭을 선택합니다. "Connect to Git" 버튼을 클릭해서 GitHub 계정과 연결합니다.

---

## GitHub 레포지토리 연결하기

GitHub 연결을 처음 하면 권한 승인 화면이 나타납니다. Cloudflare가 여러분의 GitHub 레포지토리에 접근할 수 있도록 허용합니다. 모든 레포지토리에 접근을 허용하거나, 특정 레포지토리만 선택할 수 있습니다.

연결이 완료되면 배포할 레포지토리를 선택합니다. 레포지토리를 선택하고 "Begin setup" 버튼을 클릭합니다. Project name은 자동으로 입력되며, 이 이름이 여러분의 사이트 주소가 됩니다. 예를 들어 project-name.pages.dev 형태의 무료 도메인이 제공됩니다.

---

## 빌드 설정 및 배포하기

빌드 설정 화면에서는 프레임워크를 선택합니다. 순수 HTML/CSS만 사용한다면 "None"을 선택하면 됩니다. Hugo를 사용한다면 "Hugo"를, Astro를 사용한다면 "Astro"를 선택합니다. Cloudflare가 자동으로 빌드 명령어와 출력 디렉토리를 설정해 줍니다.

"Save and Deploy" 버튼을 클릭하면 배포가 시작됩니다. 처음에는 1~2분 정도 소요될 수 있습니다. 배포가 완료되면 "Visit site" 버튼이 나타나고, 클릭하면 여러분의 웹사이트가 브라우저에 열립니다. 축하합니다. 여러분의 웹사이트가 전 세계에 공개되었습니다.

![qbxglzXA.webp](https://img.aikorea24.kr/images/github-cloudflare-pages-muryoro/987ddf9287e291453ab5fb11b5a7e845366dad5f.webp)

---

## 자동 배포의 마법

Cloudflare Pages의 가장 좋은 점은 자동 배포입니다. 이제 GitHub에 코드를 푸시할 때마다 Cloudflare가 자동으로 감지해서 새 버전을 배포합니다. 별도의 작업 없이 VSCode에서 코드를 수정하고 푸시하기만 하면 몇 초 후에 웹사이트에 반영됩니다.

작업 흐름을 정리하면 다음과 같습니다. AI에게 코드를 요청합니다. VSCode에서 파일을 수정합니다. 커밋하고 푸시합니다. Cloudflare가 자동으로 배포합니다. 웹사이트에서 변경 사항을 확인합니다. 이것이 바이브코딩의 완전한 워크플로우입니다.

---

## 결론

GitHub과 Cloudflare Pages 조합은 무료로 웹사이트를 운영할 수 있는 최고의 선택입니다. 호스팅 비용 없이, 빠르고 안전한 웹사이트를 전 세계에 공개할 수 있습니다. 바이브코딩 환경설정 편을 모두 완료했습니다. 이제 여러분은 AI에게 코드를 요청하고, VSCode에서 편집하고, GitHub에 저장하고, Cloudflare Pages로 배포하는 전체 과정을 할 수 있게 되었습니다.

---

#CloudflarePages #GitHub #무료호스팅 #웹배포 #정적사이트 #바이브코딩 #무료웹사이트 #CDN #자동배포 #웹사이트공개