import { env } from 'cloudflare:workers';
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

function normalizeLink(link: string, domain: string): string {
  if (link.startsWith('http://') || link.startsWith('https://')) {
    return link;
  }
  const base = `https://${domain}`;
  const path = link.startsWith('/') ? link : `/${link}`;
  return base + path;
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

  // ponytail: sitemap <url> 폴백 — RSS 없는 사이트(mbti 등)용. 제목은 슬러그 유추라 품질 한계 있음
  if (items.length === 0) {
    const locRegex = /<loc>\s*(.*?)\s*<\/loc>/gi;
    while ((match = locRegex.exec(xml)) !== null && items.length < 5) {
      const link = match[1];
      try {
        const u = new URL(link);
        if (u.pathname === '/' || u.pathname === '') continue;
        const slug = u.pathname.replace(/\/+$/, '').split('/').pop() || '';
        if (!slug) continue;
        const title = decodeURIComponent(slug).replace(/[-_]+/g, ' ');
        items.push({ title, link, pub_date: '' });
      } catch {
        continue;
      }
    }
  }

  return items;
}

export async function GET({ locals, request }: { locals: any; request: Request }) {
  const url = new URL(request.url);
  const key = url.searchParams.get('key');
  const db = env?.DB;

  if (!db) {
    return new Response(JSON.stringify({ error: 'DB not available' }), { status: 500 });
  }

  // fail-open이었다: NETWORK_KEY가 비어 있으면 이 검사가 통째로 건너뛰어져
  // 인증 없는 호출이 통과했다. 키가 없으면 무조건 거부하도록 fail-closed로 바꾼다.
  if (!env.NETWORK_KEY) {
    return new Response(JSON.stringify({ error: 'NETWORK_KEY not configured' }), { status: 500 });
  }

  if (key !== env.NETWORK_KEY) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 401 });
  }

  try {
    const { results: feeds } = await db.prepare(
      'SELECT domain, label, category, rss_url, platform FROM network_feeds WHERE active = 1'
    ).all() as { results: FeedRow[] };

    // Workers 무료 티어 서브요청 50개 제한 대응 — 40개씩 배치 처리 (2026-10-11 AIK24-WORKER-SUBREQ-01)
    // 제한은 invocation 단위 누적이라 한 루프 안에서 나누는 건 의미가 없다(106개 중 50 성공 후 전부 실패로 실증).
    // 배치마다 예산 50개를 새로 받으려면 배치마다 별도 invocation이어야 하는데,
    // 이 Worker 자신에게 self-fetch하면 무료 티어에서 1042(workers script not found)로 막힌다.
    // 따라서 호출자가 ?offset=0,40,80 으로 나눠 호출하는 방식으로 바꾸고,
    // 여기서는 offset 구간만 처리한다. 부모 위임 코드는 넣지 않는다.
    const BATCH_SIZE = 20;
    const batchOffsetParam = url.searchParams.get('offset');
    const offset = batchOffsetParam !== null ? Math.max(0, parseInt(batchOffsetParam, 10) || 0) : 0;
    const batch = feeds.slice(offset, offset + BATCH_SIZE);

    let success = 0;
    let failed = 0;
    const errors: string[] = [];

    for (const feed of batch) {
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

        // 상대경로 링크를 절대경로로 정규화
        for (const item of items) {
          item.link = normalizeLink(item.link, feed.domain);
        }

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
    console.error('Network refresh error:', e);
    return new Response(JSON.stringify({ error: import.meta.env.DEV ? e.message : 'Internal Server Error' }), { status: 500 });
  }
}
