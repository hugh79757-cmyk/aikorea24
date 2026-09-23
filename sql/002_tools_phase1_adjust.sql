-- Phase 42: price → price_model + price_detail, category_custom + screenshot_url
ALTER TABLE tool_submissions ADD COLUMN price_model TEXT;
ALTER TABLE tool_submissions ADD COLUMN price_detail TEXT;
ALTER TABLE tool_submissions ADD COLUMN category_custom TEXT;
ALTER TABLE tool_submissions ADD COLUMN screenshot_url TEXT;
-- 기존 price 값 보존 (현재 0행이나 규칙으로 유지):
-- '무료' → price_model='무료' / '유료' → '유료' / 그 외(예: '무료 / 유료') → price_model='Freemium', price_detail=원값
UPDATE tool_submissions SET price_model = CASE
  WHEN price = '무료' THEN '무료'
  WHEN price = '유료' THEN '유료'
  WHEN price IS NOT NULL AND TRIM(price) != '' THEN 'Freemium'
  ELSE NULL END,
  price_detail = CASE
  WHEN price = '무료' OR price = '유료' THEN NULL
  ELSE price END
WHERE price_model IS NULL;
ALTER TABLE tool_submissions DROP COLUMN price;
