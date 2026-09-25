import { NextResponse } from 'next/server';

import { getGroup } from '@/lib/groups/store';

export async function GET(
  _request: Request,
  context: { params: Promise<{ code: string }> },
) {
  const { code } = await context.params;
  const group = await getGroup(code);
  if (!group) {
    return NextResponse.json({ error: 'Groupe introuvable.' }, { status: 404 });
  }
  return NextResponse.json(group);
}
