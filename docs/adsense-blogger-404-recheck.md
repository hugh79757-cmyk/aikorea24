# Blogger 404 광고 — 2026-11-16 재점검 (편집 반영 후)

측정: 각 호스트 `/zz-recheck-p9` (Chrome UA) → 404 페이지의 광고 로더 스크립트·슬롯 개수.

| 호스트 | 편집 | 404 로더(전) | 404 로더(후) | 슬롯(후) | 상태 |
|---|---|---|---|---|---|
| 1.rotcha.kr | - | 0 | 0 | 0 | ✅ 광고 없음 |
| 2.techpawz.com | - | 4 | 4 | 0 | ❌ 미적용 |
| 65.informationhot.kr | O | 6 | 5 | 5 | 🔶 부분(1개 제거) |
| cheap-food.informationhot.kr | - | 1 | 1 | 0 | ❌ 미적용 |
| issuetwinkle-tv.informationhot.kr | O | 3 | 3 | 1 | ❌ 편집했으나 변화 없음 |
| issuetwinkle-tv.rotcha.kr | - | 1 | 1 | 0 | ❌ 미적용 |
| k-league.rotcha.kr | - | 0 | 0 | 0 | ✅ 광고 없음 |
| kbo.rotcha.kr | - | 3 | 2 | 1 | 🔶 부분(1개 제거) |
| quiz.informationhot.kr | - | 0 | 0 | 0 | ✅ 광고 없음 |
| simprotection.informationhot.kr | - | 2 | 2 | 0 | ❌ 미적용 |
| sports.rotcha.kr | - | 3 | 2 | 1 | 🔶 부분(1개 제거) |
| travel.rotcha.kr | - | 1 | 1 | 0 | ❌ 미적용 |
| tv-show.informationhot.kr | O | 3 | 2 | 0 | 🔶 부분(1개 제거) |
| ud.informationhot.kr | O | 3 | 2 | 0 | 🔶 부분(1개 제거) |
| weather.informationhot.kr | - | 1 | 1 | 0 | ❌ 미적용 |

## 남은 주입 지점 유형

| 유형 | 호스트 | 테마로 제거 가능? |
|---|---|---|
| `//pagead2…/adsbygoogle.js` (테마 head의 구형 로더) | tv-show, ud, kbo, sports, 2.techpawz | **O — b:if로 감싸면 끝** |
| `<ins class=adsbygoogle>` 슬롯 + 로더 (테마 섹션/위젯) | 65(5개), issuetwinkle-tv.info(1), kbo(1), sports(1) | **O — 해당 div 블록째 감싸기** |
| `&host=ca-host-pub-1556223355139109` (Blogger 수익창출 연동) | tv-show, ud, 2.techpawz, issuetwinkle-tv.info | **X — Blogger가 재주입** |
| 단일 manual 로더만 | cheap-food, simprotection, weather, travel, issuetwinkle-tv.rotcha | O (한 줄) |

## 정상 페이지 회귀

편집한 4개 모두 홈 200 + 광고 로더 유지(tv-show 3, ud 3) → **정상 글 광고는 안 끊겼다**. 404 페이지만 1개 줄었다.
