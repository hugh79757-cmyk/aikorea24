import type { APIRoute } from 'astro';
import { verifySession } from '../../../lib/auth';

export const GET: APIRoute = async ({ locals, cookies }) => {
  const session = cookies.get('session')?.value;
  if (!session) {
    return new Response(JSON.stringify({ loggedIn: false }), { status: 200 });
  }
  try {
    const user = await verifySession(session, (locals as any).sessionSecret);
    if (!user || !user.email) {
      return new Response(JSON.stringify({ loggedIn: false }), { status: 200 });
    }
    return new Response(
      JSON.stringify({ loggedIn: true, email: user.email }),
      { status: 200 }
    );
  } catch {
    return new Response(JSON.stringify({ loggedIn: false }), { status: 200 });
  }
};
