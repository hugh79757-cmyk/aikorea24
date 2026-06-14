import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';
import { buildUrlset } from '../lib/sitemap';
import { TASK_SLUGS } from '../config/tasks';

export const prerender = false;

export const GET: APIRoute = async () => {
  const base = 'https://aikorea24.kr';
  const tools = await getCollection('tools');

  // 기존 툴 상세 페이지
  const toolEntries = tools.map(tool => ({
    loc: base + '/tools/' + tool.id + '/',
    changefreq: 'monthly' as const,
    priority: 0.7,
  }));

  // 신규: 태스크 페이지 (우선순위 높게)
  const taskEntries = TASK_SLUGS.map(slug => ({
    loc: base + '/tools/task/' + slug + '/',
    changefreq: 'weekly' as const,
    priority: 0.9,
  }));

  // 태스크 목록 페이지
  const taskIndexEntry = {
    loc: base + '/tools/task/',
    changefreq: 'weekly' as const,
    priority: 0.8,
  };

  const entries = [...toolEntries, ...taskEntries, taskIndexEntry];

  return new Response(buildUrlset(entries), {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  });
};
