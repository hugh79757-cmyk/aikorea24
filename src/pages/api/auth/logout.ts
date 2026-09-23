import type { APIRoute } from 'astro';

export const GET: APIRoute = async ({ cookies, redirect }) => {
  cookies.delete('session', { path: '/', domain: import.meta.env.PROD ? '.aikorea24.kr' : undefined });
  return redirect('/');
};
