import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const OUTPUT_DIR = '/Users/twinssn/Projects/aikorea24/cards';
const HTML_DIR = '/Users/twinssn/Projects/aikorea24/instagram-carousel-output';

if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

const cards = [
  { html: 'minimalist-format-d-1.html', png: 'card_1.png' },
  { html: 'minimalist-format-d-2.html', png: 'card_2.png' },
  { html: 'minimalist-format-d-3.html', png: 'card_3.png' },
  { html: 'minimalist-format-d-4.html', png: 'card_4.png' },
  { html: 'minimalist-format-d-5.html', png: 'card_5.png' },
];

async function captureCard(htmlFile, pngFile) {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1080, height: 1350 },
    deviceScaleFactor: 2
  });
  
  const filePath = `file://${path.join(HTML_DIR, htmlFile)}`;
  await page.goto(filePath, { waitUntil: 'networkidle' });
  await page.waitForTimeout(500);
  
  await page.screenshot({
    path: path.join(OUTPUT_DIR, pngFile),
    fullPage: false
  });
  
  await browser.close();
  console.log(`✅ ${pngFile} 생성 완료`);
}

async function main() {
  for (const card of cards) {
    await captureCard(card.html, card.png);
  }
  console.log('🎉 모든 카드 이미지 생성 완료!');
}

main().catch(console.error);
