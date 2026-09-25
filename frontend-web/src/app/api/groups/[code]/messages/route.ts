import { NextResponse } from 'next/server';

import { addMessage, listMessages } from '@/lib/groups/store';

export async function GET(
  request: Request,
  context: { params: Promise<{ code: string }> },
) {
  const { code } = await context.params;
  const since = new URL(request.url).searchParams.get('since') ?? undefined;
  const messages = await listMessages(code, since);
  if (!messages) {
    return NextResponse.json({ error: 'Groupe introuvable.' }, { status: 404 });
  }
  return NextResponse.json({ messages });
}

export async function POST(
  request: Request,
  context: { params: Promise<{ code: string }> },
) {
  const { code } = await context.params;
  const body = (await request.json().catch(() => null)) as {
    deviceId?: unknown;
    text?: unknown;
  } | null;
  const deviceId = typeof body?.deviceId === 'string' ? body.deviceId.trim() : '';
  const text = typeof body?.text === 'string' ? body.text.trim() : '';
  if (!/^[a-zA-Z0-9-]{8,64}$/.test(deviceId)) {
    return NextResponse.json({ error: 'Rejoignez le groupe avant d’écrire.' }, { status: 400 });
  }
  if (!text || text.length > 500) {
    return NextResponse.json({ error: 'Message vide ou trop long.' }, { status: 400 });
  }
  const message = await addMessage(code, deviceId, text);
  if (!message) {
    return NextResponse.json(
      { error: 'Rejoignez le groupe avant d’écrire.' },
      { status: 403 },
    );
  }
  return NextResponse.json(message);
}
