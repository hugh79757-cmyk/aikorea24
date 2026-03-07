export interface SitemapEntry {
  loc: string;
  lastmod?: string;
  changefreq?: string;
  priority?: number;
}

export function buildUrlset(entries: SitemapEntry[]): string {
  const urls = entries.map(e => {
    let xml = '  <url>\n    <loc>' + esc(e.loc) + '</loc>';
    if (e.lastmod) xml += '\n    <lastmod>' + e.lastmod + '</lastmod>';
    if (e.changefreq) xml += '\n    <changefreq>' + e.changefreq + '</changefreq>';
    if (e.priority !== undefined) xml += '\n    <priority>' + e.priority.toFixed(1) + '</priority>';
    return xml + '\n  </url>';
  }).join('\n');
  return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + '\n</urlset>';
}

export function buildIndex(sitemaps: { loc: string; lastmod?: string }[]): string {
  const entries = sitemaps.map(s => {
    let xml = '  <sitemap>\n    <loc>' + esc(s.loc) + '</loc>';
    if (s.lastmod) xml += '\n    <lastmod>' + s.lastmod + '</lastmod>';
    return xml + '\n  </sitemap>';
  }).join('\n');
  return '<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + entries + '\n</sitemapindex>';
}

export function toDateStr(d: Date | string): string {
  const date = typeof d === 'string' ? new Date(d) : d;
  return date.toISOString().split('T')[0];
}

function esc(s: string): string {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
