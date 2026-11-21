# 'Listed on AI Korea 24' 배지 자산 — 단일 공급원 (2026-11-21)

## 정본 (single source of truth)

| 항목 | 값 |
|---|---|
| 파일 | `public/badges/listed-on-aikorea24.webp` (이 저장소) |
| 공개 URL | `https://aikorea24.kr/badges/listed-on-aikorea24.webp` |
| 크기 | 621 × 207 (3.0014 : 1), 20,078 B |
| md5 | `f5351dce0bc9ef0421fc2ab697725d96` |
| 배경 | 불투명 흰색 (알파 없음) |

이 파일이 배지의 유일한 정본이다. 모든 소비처는 **이 파일의 바이트를 그대로** 쓴다.

## 소비처

| 사이트 | 로컬 자산 / 참조 | 마크업 |
|---|---|---|
| aikorea24.kr | `public/badges/listed-on-aikorea24.webp` | 승인 이메일 (`src/lib/email-notify.ts`) |
| taro.aikorea24.kr | `public/aik24-badge-sm.webp` (정본 복사본) | `<img width="150" height="50">` — `public/index.html` |
| saju.aikorea24.kr | `public/listed-on-aikorea24.webp` (정본 복사본) | `<img width="240" height="80">` — `src/views/layout.ts` |
| link2threads.com | 없음(정본 URL 직접 참조) | `<img src="https://aikorea24.kr/badges/…" width="200">` |

종횡비가 3.0014:1 이므로 `width`/`height` 는 3:1 로 맞춘다 (150×50, 240×80, 200×67).

## ⛔ 재크롭 금지 (2026-11-20 사고)

원본 시안에는 스티커 둘레에 `#333` 프레임이 있는 **다른** 파일(`aik24-badge.webp`, 2480×992, 346KB)이 있었다.
이 파일을 잘라 배지로 쓰면 상·하단에 어두운 프레임 조각이 남아 **다크 푸터에서 '회색 띠'** 로 보인다
(2026-11-20 taro 푸터에서 실측: 상단 y=0 중앙 RGB 234, 하단 208~230).

- 배지가 필요하면 위 정본을 `cp` 로 복사한다. 잘라내기·리사이즈·재인코딩·알파 합성 모두 하지 않는다.
- 축소가 필요하면 CSS `width` 로 줄인다(HTML 속성은 비율 유지용).
- 배지 위아래에 회색 띠가 보이면 → 그 사이트의 자산이 정본 바이트가 아닌 것이다. md5 부터 대조한다.

## 검증 명령

```bash
md5 -q public/badges/listed-on-aikorea24.webp            # f5351dce0bc9ef0421fc2ab697725d96
curl -s https://aikorea24.kr/badges/listed-on-aikorea24.webp | md5
magick identify public/badges/listed-on-aikorea24.webp   # 621x207
```
