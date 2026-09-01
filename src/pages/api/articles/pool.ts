import type { APIRoute } from 'astro';

export const GET: APIRoute = async ({ url, locals }) => {
  const runtime = (locals as any).runtime;
  const db = runtime?.env?.DB;
  if (!db) {
    return new Response(JSON.stringify({ articles: [], meta: { total: 0, error: 'DB not available' } }), {
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const today = url.searchParams.get('date') || new Date().toISOString().slice(0, 10);
  const maxArticles = parseInt(url.searchParams.get('limit') || '50', 10);

  // Source filter: crawlable + api_based sources from config
  const SOURCES = [
    'Wired AI', 'MarkTechPost', 'AI News EU', 'HuggingFace Blog', 'GitHub Blog',
    'The Decoder', 'The Guardian AI', 'MIT Tech Review', 'TechCrunch AI', 'Google AI Blog',
    'Ars Technica AI', 'City AM', 'Guardian US News', 'BBC Technology', 'The Next Web',
    'ZDNET AI', 'Politico EU Tech', 'Memphis Flyer', 'CNBC Tech', 'NYT AI Spotlight',
    '9to5Google', 'Android Central', 'SamMobile', 'AI타임스', '인공지능신문', 'The Hacker News',
    'TechCrunch', 'BBC', 'Business Insider AI',
  ];
  const placeholders = SOURCES.map(() => '?').join(', ');

  const articles: any[] = [];
  const existingIds = new Set<string>();

  try {
    // 1순위: 오늘 브리핑 기사
    const p1Query = `
      SELECT n.id, n.title, n.link, n.description, n.source, n.pub_date,
             COALESCE(bi.comment, '') as comment,
             COALESCE(n.original_title, '') as original_title
      FROM news n
      JOIN briefing_items bi ON bi.news_id = n.id
      JOIN briefings b ON b.id = bi.briefing_id
      WHERE b.date LIKE ? AND b.status = 'published'
        AND n.source IN (${placeholders})
      GROUP BY n.id ORDER BY bi.sort_order ASC
    `;
    const p1Results = await db.prepare(p1Query).bind(`${today}%`, ...SOURCES).all();
    for (const r of (p1Results.results || [])) {
      if (!existingIds.has(String(r.id))) {
        r.priority = 1;
        articles.push(r);
        existingIds.add(String(r.id));
      }
    }

    // 2순위: 최근 7일 news
    if (articles.length < maxArticles) {
      const p2Query = `
        SELECT id, title, link, description, source, pub_date, '' as comment,
               COALESCE(original_title, '') as original_title
        FROM news
        WHERE date(pub_date) >= date(?, '-7 days')
          AND source IN (${placeholders})
        ORDER BY pub_date DESC LIMIT 2000
      `;
      const p2Results = await db.prepare(p2Query).bind(today, ...SOURCES).all();
      for (const r of (p2Results.results || [])) {
        if (!existingIds.has(String(r.id))) {
          r.priority = 2;
          articles.push(r);
          existingIds.add(String(r.id));
        }
      }
    }

    // 3순위: 이전 기사
    if (articles.length < maxArticles) {
      const remaining = maxArticles - articles.length;
      const p3Query = `
        SELECT id, title, link, description, source, pub_date, '' as comment,
               COALESCE(original_title, '') as original_title
        FROM news
        WHERE date(pub_date) < date(?, '-7 days')
          AND source IN (${placeholders})
        ORDER BY pub_date DESC LIMIT ?
      `;
      const p3Results = await db.prepare(p3Query).bind(today, ...SOURCES, remaining + 20).all();
      for (const r of (p3Results.results || [])) {
        if (!existingIds.has(String(r.id))) {
          r.priority = 3;
          articles.push(r);
          existingIds.add(String(r.id));
        }
      }
    }
  } catch (e: any) {
    return new Response(JSON.stringify({ articles: [], meta: { total: 0, error: e.message } }), {
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const p1 = articles.filter(a => a.priority === 1).length;
  const p2 = articles.filter(a => a.priority === 2).length;
  const p3 = articles.filter(a => a.priority === 3).length;

  return new Response(JSON.stringify({
    articles,
    meta: { total: articles.length, p1, p2, p3, date: today },
  }), {
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
};
