export const prerender = false;

interface FeedRow {
  domain: string;
  label: string;
  category: string;
  rss_url: string;
  platform: string;
}

interface ParsedItem {
  title: string;
  link: string;
  pub_date: string;
}

function extractItems(xml: string, platform: string): ParsedItem[] {
  const items: ParsedItem[] = [];
  const itemRegex = /<item[\s>]([\s\S]*?)<\/item>/gi;
  let match;
  while ((match = itemRegex.exec(xml)) !== null && items.length < 5) {
    const block = match[1];
    const title = block.match(/<title[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?<\/title>/s)?.[1]?.trim() || '';
    let link = '';
    const linkMatch = block.match(/<link[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?<\/link>/s);
    if (linkMatch) {
      link = linkMatch[1].trim();
    }
    if (!link) {
      const guidMatch = block.match(/<guid[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?<\/guid>/s);
      if (guidMatch) link = guidMatch[1].trim();
    }
    const pubDateMatch = block.match(/<pubDate[^>]*>(.*?)<\/pubDate>/s)
      || block.match(/<dc:date[^>]*>(.*?)<\/dc:date>/s)
      || block.match(/<published[^>]*>(.*?)<\/published>/s);
    const pub_date = pubDateMatch?.[1]?.trim() || '';

    if (title && link) {
      items.push({ title, link, pub_date });
    }
  }

  if (items.length === 0) {
    const entryRegex = /<entry[\s>]([\s\S]*?)<\/entry>/gi;
    while ((match = entryRegex.exec(xml)) !== null && items.length < 5) {
      const block = match[1];
      const title = block.match(/<title[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?<\/title>/s)?.[1]?.trim() || '';
      const linkMatch = block.match(/<link[^>]*rel=["']alternate["'][^>]*href=["'](.*?)["']/);
      const link = linkMatch?.[1]?.trim() || '';
      const pubMatch = block.match(/<published[^>]*>(.*?)<\/published>/s)
        || block.match(/<updated[^>]*>(.*?)<\/updated>/s);
      const pub_date = pubMatch?.[1]?.trim() || '';
      if (title && link) {
        items.push({ title, link, pub_date });
      }
    }
  }

  return items;
}

export async function GET({ locals, request }: { locals: any; request: Request }) {
  const url = new URL(request.url);
  const key = url.searchParams.get('key');
  const runtime = (locals as any).runtime;
  const env = runtime?.env;
  const db = env?.DB;

  if (!db) {
    return new Response(JSON.stringify({ error: 'DB not available' }), { status: 500 });
  }

  if (env.NETWORK_KEY && key !== env.NETWORK_KEY) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 401 });
  }

  try {
    const { results: feeds } = await db.prepare(
      'SELECT domain, label, category, rss_url, platform FROM network_feeds WHERE active = 1'
    ).all() as { results: FeedRow[] };

    let success = 0;
    let failed = 0;
    const errors: string[] = [];

    for (const feed of feeds) {
      try {
        const res = await fetch(feed.rss_url, {
          headers: { 'User-Agent': 'AIKorea24-NetworkBot/1.0' },
          signal: AbortSignal.timeout(8000),
        });

        if (!res.ok) {
          errors.push(`${feed.domain}: HTTP ${res.status}`);
          failed++;
          continue;
        }

        const xml = await res.text();
        const items = extractItems(xml, feed.platform);

        if (items.length === 0) {
          errors.push(`${feed.domain}: no items parsed`);
          failed++;
          continue;
        }

        await db.prepare('DELETE FROM network_cache WHERE domain = ?').bind(feed.domain).run();

        for (const item of items) {
          await db.prepare(
            "INSERT OR IGNORE INTO network_cache (domain, title, link, pub_date, fetched_at) VALUES (?, ?, ?, ?, datetime('now'))"
          ).bind(feed.domain, item.title, item.link, item.pub_date).run();
        }

        success++;
      } catch (e: any) {
        errors.push(`${feed.domain}: ${e.message || 'unknown error'}`);
        failed++;
      }
    }

    return new Response(JSON.stringify({
      total: feeds.length,
      success,
      failed,
      errors: errors.length > 0 ? errors : undefined,
      timestamp: new Date().toISOString(),
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });

  } catch (e: any) {
    return new Response(JSON.stringify({ error: e.message }), { status: 500 });
  }
}
