export async function onRequestGet(context) {
  const { env } = context;
  const result = await env.DB.prepare("SELECT 1 as ok").first();
  return Response.json({ result, source: "d1-binding" });
}
