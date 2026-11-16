# Blogger 15개 블로그 404 광고 실태 (2026-11-16 실측)

측정: 각 호스트 `https://<host>/zz-probe-f3k` (Chrome UA) → HTTP 404 확인 후 광고 요소 계수.

## 1. 전수 측정

| 호스트 | 테마군 | 슬롯 | head 로더 | Auto ads | Blogger 연동 | 판정 |
|---|---|---|---|---|---|---|
| 1.rotcha.kr | B | 0 | 0 | - | - | **광고 없음(CSS 문자열만)** |
| 2.techpawz.com | A | 0 | 4 | O | O | **자동광고(Auto ads)만** |
| 65.informationhot.kr | C | 5 | 6 | - | - | **수동 광고 슬롯 있음** |
| cheap-food.informationhot.kr | C | 0 | 1 | - | - | **로더만 있음(자동광고 설정 시 게재)** |
| issuetwinkle-tv.informationhot.kr | C | 1 | 3 | - | O | **수동 광고 슬롯 있음** |
| issuetwinkle-tv.rotcha.kr | A | 0 | 1 | O | - | **자동광고(Auto ads)만** |
| k-league.rotcha.kr | B | 0 | 0 | - | - | **광고 없음(CSS 문자열만)** |
| kbo.rotcha.kr | A | 1 | 3 | O | - | **수동 광고 슬롯 있음** |
| quiz.informationhot.kr | A | 0 | 0 | O | - | **광고 없음(CSS 문자열만)** |
| simprotection.informationhot.kr | B | 0 | 2 | - | - | **로더만 있음(자동광고 설정 시 게재)** |
| sports.rotcha.kr | A | 1 | 3 | O | - | **수동 광고 슬롯 있음** |
| travel.rotcha.kr | A | 0 | 1 | O | - | **자동광고(Auto ads)만** |
| tv-show.informationhot.kr | A | 0 | 3 | O | O | **자동광고(Auto ads)만** |
| ud.informationhot.kr | A | 0 | 3 | O | O | **자동광고(Auto ads)만** |
| weather.informationhot.kr | C | 0 | 1 | - | - | **로더만 있음(자동광고 설정 시 게재)** |

**요약**: 광고 없음(CSS 문자열만) 3개 / 자동광고(Auto ads)만 5개 / 수동 광고 슬롯 있음 4개 / 로더만 있음(자동광고 설정 시 게재) 3개

## 2. 테마 동일성

| 군 | 마커 | 호스트 |
|---|---|---|
| A | `errorWrap` `--button-bg` `slide-menu` `no-posts` | 2.techpawz.com, issuetwinkle-tv.rotcha.kr, kbo.rotcha.kr, quiz.informationhot.kr, sports.rotcha.kr, travel.rotcha.kr, tv-show.informationhot.kr, ud.informationhot.kr |
| B | `no-posts` (errorWrap 없음) | 1.rotcha.kr, k-league.rotcha.kr, simprotection.informationhot.kr |
| C | 마커 없음(개별 테마) | 65.informationhot.kr, cheap-food.informationhot.kr, weather.informationhot.kr, issuetwinkle-tv.informationhot.kr |

## 3. 호스트별 수정 지점

| 호스트 | 고칠 지점 |
|---|---|
| 1.rotcha.kr | 없음 |
| 2.techpawz.com | head 로더 4개 + Blogger 연동 1 + Auto ads |
| 65.informationhot.kr | 광고 슬롯 5개 + head 로더 6개 |
| cheap-food.informationhot.kr | head 로더 1개 |
| issuetwinkle-tv.informationhot.kr | 광고 슬롯 1개 + head 로더 3개 + Blogger 연동 1 |
| issuetwinkle-tv.rotcha.kr | head 로더 1개 + Auto ads |
| k-league.rotcha.kr | 없음 |
| kbo.rotcha.kr | 광고 슬롯 1개 + head 로더 3개 + Auto ads |
| quiz.informationhot.kr | Auto ads |
| simprotection.informationhot.kr | head 로더 2개 |
| sports.rotcha.kr | 광고 슬롯 1개 + head 로더 3개 + Auto ads |
| travel.rotcha.kr | head 로더 1개 + Auto ads |
| tv-show.informationhot.kr | head 로더 3개 + Blogger 연동 1 + Auto ads |
| ud.informationhot.kr | head 로더 3개 + Blogger 연동 1 + Auto ads |
| weather.informationhot.kr | head 로더 1개 |

## 4. 테마 편집 원칙

- 광고 코드 **삭제 금지**(정상 글 광고가 사라져 수익 0). `error_page` 일 때만 미노출:
```xml
<b:if cond='data:blog.pageType != &quot;error_page&quot;'>
  <script async='async' crossorigin='anonymous' src='https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-…'></script>
</b:if>
```
- Blogger 연동(`host=ca-host-pub-…`)은 테마에서 지워도 재주입 → Blogger 대시보드 설정 영역.
- Auto ads 는 404 URL 패턴 제외가 실효 없음 → 앵커 광고 OFF 권장.
