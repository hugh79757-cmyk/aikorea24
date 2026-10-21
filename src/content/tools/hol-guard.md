---
name: "HOL Guard"
description: "Claude Code·Codex·Cursor 같은 AI 코딩 에이전트가 셸 명령, 시크릿 읽기, MCP 도구 호출, 패키지 설치를 실행하기 전에 내 컴퓨터에서 허용/차단을 묻는 로컬 오픈소스 CLI"
category: "코딩·개발"
price: "Freemium"
koreanSupport: false
difficulty: "고급"
url: "https://hol.org/guard"
useCases: ["AI 코딩 에이전트 실행 전 승인", "시크릿 보호", "패키지 설치 확인"]
tags: ["AI 보안", "코딩 에이전트", "Claude Code", "Codex", "Cursor", "MCP", "오픈소스"]
tasks: []
order: -1
featured: false
updated: "2026-10-21"
priceModel: "Freemium"
---

HOL Guard는 Claude Code, Codex, Cursor 등 AI 코딩 에이전트 옆에서 내 컴퓨터에 로컬로 동작합니다. 셸 명령, 시크릿·인증 정보 읽기, MCP 도구 호출, 패키지 설치를 실행 전에 잠시 멈추고, 사람이 판단해야 할 단계는 허용/차단을 묻습니다. 모든 선택은 로컬 결정 로그에 남아 나중에 에이전트가 무엇을 시도했는지 확인할 수 있습니다. 핵심은 Apache-2.0 오픈소스 Python CLI(macOS, Linux)이며 팀용 선택형 유료 Guard Cloud가 있습니다(프리미엄). 게이트웨이나 네트워크 방화벽이 아니며 프롬프트 인젝션을 완전히 막지 않고, 스캔 결과는 안전을 보장하지 않습니다. 인터페이스는 영어입니다. 설치: pipx install hol-guard && hol-guard init
