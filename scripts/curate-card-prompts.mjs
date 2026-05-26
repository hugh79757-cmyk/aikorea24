import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_PATH = join(__dirname, '../public/benefits-clean.json');
const CATEGORY_MAP = {
  '청년':      d => d.category === 'youth' || (d.age_range && d.age_range[0] <= 34),
  '신혼부부':  d => /신혼|혼인|결혼/.test(d.name + d.target + d.purpose),
  '고령자':    d => d.category === 'elderly' || (d.age_range && d.age_range[0] >= 60),
  '자영업자':  d => /자영업|소상공인/.test(d.name + d.target + d.purpose),
  '다자녀':    d => /다자녀|다둥이/.test(d.name + d.target + d.purpose),
  '무주택자':  d => /무주택|전세|월세|주거/.test(d.name + d.target + d.purpose),
  '장애인':    d => /장애/.test(d.name + d.target + d.purpose),
  '농업인':    d => /농업|농어업|농촌/.test(d.name + d.target + d.purpose),
};
const STYLE = `1080x1350 portrait (4:5 ratio) Instagram carousel card.
Pixel art illustration style (Stardew Valley / Korean retro game).
Deep navy gradient background (#0F1E3D to #1E3A5F).
Pixel-art Korean cityscape, hanok, modern apartments, cozy lit windows.
Korean Pretendard-style bold sans-serif overlay text in white and orange (#FFA552).
Atmospheric lighting. No real photos.
Bottom-right tiny watermark "persona.aikorea24.kr".
Top-right pill "@aikorea24" navy outline style.`;
const TITLES = {
  '청년':     n => `청년이라면 무조건 받아야 할 지원금 TOP ${n}`,
  '신혼부부': n => `신혼부부 필수 지원금 TOP ${n}`,
  '고령자':   n => `60세 이상 꼭 챙겨야 할 지원금 TOP ${n}`,
  '자영업자': n => `자영업자·소상공인 지원금 TOP ${n}`,
  '다자녀':   n => `다자녀 가정 지원금 TOP ${n}`,
  '무주택자': n => `무주택자 주거 지원금 TOP ${n}`,
  '장애인':   n => `장애인 복지 지원금 TOP ${n}`,
  '농업인':   n => `농업인 지원금 TOP ${n}`,
};
const cut = (s, n=50) => s ? s.replace(/\s+/g,' ').trim().slice(0,n)+(s.length>n?'…':'') : '';
const args = Object.fromEntries(process.argv.slice(2).filter(a=>a.startsWith('--')).map(a=>a.slice(2).split('=')));
const category = args.category ?? '청년';
const count = parseInt(args.count ?? '5');
const filter = CATEGORY_MAP[category];
if (!filter) { console.error(`카테고리 오류. 가능: ${Object.keys(CATEGORY_MAP).join(', ')}`); process.exit(1); }
const data = JSON.parse(readFileSync(DATA_PATH, 'utf8'));
const items = data.filter(filter).sort((a,b)=>(b._score??0)-(a._score??0)).slice(0,count);
if (!items.length) { console.error('데이터 없음'); process.exit(1); }
const title = (TITLES[category] ?? (n=>`${category} 지원금 TOP ${n}`))(items.length);
console.log('='.repeat(60));
console.log('[슬라이드 1 / 표지]');
console.log(`PROMPT:\n${STYLE}\nCenter text: Line1(white,large):"${title}" Line2(orange):"몰랐으면 손해 👇"\n`);
items.forEach((d,i) => {
  const dl = d.deadline === '상시신청' ? '상시 신청' : `마감: ${d.deadline}`;
  console.log(`[슬라이드 ${i+2} / #${i+1} ${d.name}]`);
  console.log(`PROMPT:\n${STYLE}\nBadge:"#${i+1}" | Title:"${d.name}" | Desc:"${cut(d.purpose,55)}" | Benefit:"${cut(d.content,55)}" | Org:"${d.org}" | Deadline:"${dl}"\n`);
});
console.log(`[슬라이드 ${items.length+2} / CTA]`);
console.log(`PROMPT:\n${STYLE}\nText:"더 많은 지원금이 궁금하다면?" / "persona.aikorea24.kr"(orange,large) / "2,739건 한눈에 확인"\n`);
const hook = `${category}이라면 꼭 받아야 할 지원금 TOP ${items.length} 👇\n\n` + items.slice(0,3).map((d,i)=>`${i+1}. ${d.name}`).join('\n') + `\n\n전체 목록 → persona.aikorea24.kr/benefits\n#정부지원금 #${category}지원금 #복지혜택`;
console.log('='.repeat(60));
console.log('[쓰레드 훅]');
console.log(hook);
console.log(`(${hook.length}자)`);
