-- 네트워크 피드 캐시 테이블
CREATE TABLE IF NOT EXISTS network_feeds (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  domain TEXT NOT NULL UNIQUE,
  category TEXT NOT NULL,
  label TEXT NOT NULL,
  rss_url TEXT NOT NULL,
  platform TEXT NOT NULL DEFAULT 'hugo',
  active INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS network_cache (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  domain TEXT NOT NULL,
  title TEXT NOT NULL,
  link TEXT NOT NULL UNIQUE,
  pub_date TEXT,
  fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (domain) REFERENCES network_feeds(domain)
);

CREATE INDEX IF NOT EXISTS idx_network_cache_domain ON network_cache(domain);
CREATE INDEX IF NOT EXISTS idx_network_cache_fetched ON network_cache(fetched_at DESC);

-- 피드 등록 (33개)
INSERT OR IGNORE INTO network_feeds (domain, category, label, rss_url, platform) VALUES
-- 스포츠
('sports.rotcha.kr', '스포츠', '스포츠롯차', 'https://sports.rotcha.kr/feeds/posts/default?alt=rss', 'blogger'),
('kbo.rotcha.kr', '스포츠', 'KBO롯차', 'https://kbo.rotcha.kr/feeds/posts/default?alt=rss', 'blogger'),
-- 여행
('travel.rotcha.kr', '여행', '여행롯차', 'https://travel.rotcha.kr/feeds/posts/default?alt=rss', 'blogger'),
('travel1.rotcha.kr', '여행', '여행가이드1', 'https://travel1.rotcha.kr/index.xml', 'hugo'),
('travel2.rotcha.kr', '여행', '여행가이드2', 'https://travel2.rotcha.kr/index.xml', 'hugo'),
('tour1.rotcha.kr', '여행', '투어가이드1', 'https://tour1.rotcha.kr/index.xml', 'hugo'),
('tour2.rotcha.kr', '여행', '투어가이드2', 'https://tour2.rotcha.kr/index.xml', 'hugo'),
('tour3.rotcha.kr', '여행', '투어가이드3', 'https://tour3.rotcha.kr/index.xml', 'hugo'),
('guide.rotcha.kr', '여행', '가이드롯차', 'https://guide.rotcha.kr/index.xml', 'hugo'),
-- 자동차
('ev.rotcha.kr', '자동차', 'EV롯차', 'https://ev.rotcha.kr/index.xml', 'hugo'),
('compare.rotcha.kr', '자동차', '비교롯차', 'https://compare.rotcha.kr/index.xml', 'hugo'),
('tco.rotcha.kr', '자동차', 'TCO롯차', 'https://tco.rotcha.kr/index.xml', 'hugo'),
('hotissue.rotcha.kr', '자동차', '핫이슈롯차', 'https://hotissue.rotcha.kr/index.xml', 'hugo'),
('deal.rotcha.kr', '자동차', '딜롯차', 'https://deal.rotcha.kr/index.xml', 'hugo'),
-- 부동산
('apt.informationhot.kr', '부동산', '아파트정보', 'https://apt.informationhot.kr/index.xml', 'hugo'),
('rent.informationhot.kr', '부동산', '임대정보', 'https://rent.informationhot.kr/index.xml', 'hugo'),
('apply.informationhot.kr', '부동산', '청약정보', 'https://apply.informationhot.kr/index.xml', 'hugo'),
('tax.informationhot.kr', '부동산', '세금정보', 'https://tax.informationhot.kr/index.xml', 'hugo'),
-- 생활정보
('informationhot.kr', '생활정보', '인포메이션핫', 'https://informationhot.kr/index.xml', 'hugo'),
('brand.informationhot.kr', '생활정보', '브랜드정보', 'https://brand.informationhot.kr/index.xml', 'hugo'),
('kuta.informationhot.kr', '생활정보', '쿠타정보', 'https://kuta.informationhot.kr/feed/', 'wordpress'),
('ud.informationhot.kr', '생활정보', 'UD정보', 'https://ud.informationhot.kr/feeds/posts/default?alt=rss', 'blogger'),
-- 금융·투자
('techpawz.com', '금융·투자', '테크포우즈', 'https://techpawz.com/feed/', 'wordpress'),
('dividend.techpawz.com', '금융·투자', '배당정보', 'https://dividend.techpawz.com/index.xml', 'hugo'),
('etf.techpawz.com', '금융·투자', 'ETF정보', 'https://etf.techpawz.com/index.xml', 'hugo'),
('sector.techpawz.com', '금융·투자', '섹터분석', 'https://sector.techpawz.com/index.xml', 'hugo'),
('ipo.techpawz.com', '금융·투자', 'IPO정보', 'https://ipo.techpawz.com/index.xml', 'hugo'),
('finance.techpawz.com', '금융·투자', '금융정보', 'https://finance.techpawz.com/index.xml', 'hugo'),
('stock.informationhot.kr', '금융·투자', '주식정보', 'https://stock.informationhot.kr/index.xml', 'hugo'),
-- 노인복지
('senior.informationhot.kr', '노인복지', '시니어정보', 'https://senior.informationhot.kr/index.xml', 'hugo'),
('2.techpawz.com', '노인복지', '복지정보', 'https://2.techpawz.com/feeds/posts/default?alt=rss', 'blogger'),
-- 맛집·레시피
('foodwater.tistory.com', '맛집·레시피', '방송맛집', 'https://foodwater.tistory.com/rss', 'tistory'),
-- 시사·이슈
('rotcha.kr', '시사·이슈', '롯차', 'https://rotcha.kr/index.xml', 'hugo'),
('info.techpawz.com', '시사·이슈', '이슈정보', 'https://info.techpawz.com/feed/', 'wordpress');
