export const prerender = false;

export async function GET({ locals }: { locals: any }) {
  const runtime = (locals as any).runtime;
  const db = runtime?.env?.DB;

  if (!db) {
    return new Response(JSON.stringify({ error: 'DB not available' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    });
  }

  try {
    const { results: feeds } = await db.prepare(
      'SELECT domain, label, category FROM network_feeds WHERE active = 1 ORDER BY category, label'
    ).all();

    const { results: cache } = await db.prepare(
      'SELECT domain, title, link FROM network_cache ORDER BY pub_date DESC'
    ).all();

    const cacheMap: Record<string, { title: string; link: string }[]> = {};
    for (const row of cache as any[]) {
      if (!cacheMap[row.domain]) cacheMap[row.domain] = [];
      if (cacheMap[row.domain].length < 2) {
        cacheMap[row.domain].push({ title: row.title, link: row.link });
      }
    }

    const categories: Record<string, { domain: string; label: string; items: { title: string; link: string }[] }[]> = {};
    for (const feed of feeds as any[]) {
      if (!categories[feed.category]) categories[feed.category] = [];
      categories[feed.category].push({
        domain: feed.domain,
        label: feed.label,
        items: cacheMap[feed.domain] || [],
      });
    }

    return new Response(JSON.stringify({ categories, updated: new Date().toISOString() }), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Cache-Control': 'public, max-age=3600',
      },
    });
  } catch (e: any) {
    return new Response(JSON.stringify({ error: e.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    });
  }
}
