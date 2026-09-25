import { NextResponse } from 'next/server';

import { createGroup } from '@/lib/groups/store';

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as { name?: unknown } | null;
  const name = typeof body?.name === 'string' ? body.name.trim() : '';
  if (name.length < 2 || name.length > 60) {
    return NextResponse.json(
      { error: 'Donnez un nom au groupe (2 à 60 caractères).' },
      { status: 400 },
    );
  }
  const group = await createGroup(name);
  return NextResponse.json(group);
}
