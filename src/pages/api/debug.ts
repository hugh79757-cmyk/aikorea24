import type { APIRoute } from 'astro';

export const GET: APIRoute = async ({ locals }) => {
  const runtime = (locals as any).runtime;
  
  return new Response(JSON.stringify({
    has_runtime: !!runtime,
    has_env: !!runtime?.env,
    env_keys: runtime?.env ? Object.keys(runtime.env) : [],
    has_client_id: !!runtime?.env?.GOOGLE_CLIENT_ID,
    client_id_start: runtime?.env?.GOOGLE_CLIENT_ID?.substring(0, 8) || 'NOT_FOUND',
    import_meta: !!import.meta.env.GOOGLE_CLIENT_ID,
    import_meta_start: import.meta.env.GOOGLE_CLIENT_ID?.substring(0, 8) || 'NOT_FOUND',
  }, null, 2), {
    headers: { 'Content-Type': 'application/json' }
  });
};
