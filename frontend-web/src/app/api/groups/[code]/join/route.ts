import { NextResponse } from 'next/server';

import { joinGroup } from '@/lib/groups/store';

export async function POST(
  request: Request,
  context: { params: Promise<{ code: string }> },
) {
  const { code } = await context.params;
  const body = (await request.json().catch(() => null)) as {
    deviceId?: unknown;
    name?: unknown;
  } | null;
  const deviceId = typeof body?.deviceId === 'string' ? body.deviceId.trim() : '';
  const name = typeof body?.name === 'string' ? body.name.trim() : '';
  if (!/^[a-zA-Z0-9-]{8,64}$/.test(deviceId)) {
    return NextResponse.json({ error: 'Appareil non reconnu.' }, { status: 400 });
  }
  if (name.length < 2 || name.length > 24) {
    return NextResponse.json(
      { error: 'Choisissez un prénom (2 à 24 caractères).' },
      { status: 400 },
    );
  }
  const member = await joinGroup(code, deviceId, name);
  if (!member) {
    return NextResponse.json({ error: 'Groupe introuvable.' }, { status: 404 });
  }
  return NextResponse.json(member);
}
