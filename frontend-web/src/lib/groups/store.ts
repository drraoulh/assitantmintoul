import { randomBytes, randomUUID } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

import type { GroupMember, GroupMessage, GroupRoom, GroupSummary } from '@/lib/groups/types';

const COLORS = ['#007A5E', '#CE1126', '#A67C00', '#0B6E4F', '#9B2335', '#1A1A1A'];
const ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
const MAX_MESSAGES = 300;
const filePath = path.join(process.cwd(), '.data', 'groups.json');

type Db = { groups: GroupRoom[] };

let chain: Promise<unknown> = Promise.resolve();

function queue<T>(task: () => Promise<T>): Promise<T> {
  const run = chain.then(task, task);
  chain = run.then(
    () => undefined,
    () => undefined,
  );
  return run;
}

async function readDb(): Promise<Db> {
  try {
    const raw = await readFile(filePath, 'utf8');
    const parsed = JSON.parse(raw) as Db;
    return { groups: Array.isArray(parsed.groups) ? parsed.groups : [] };
  } catch {
    return { groups: [] };
  }
}

async function writeDb(db: Db): Promise<void> {
  await mkdir(path.dirname(filePath), { recursive: true });
  await writeFile(filePath, JSON.stringify(db), 'utf8');
}

export function normalizeCode(value: string): string {
  return value.trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
}

function makeCode(existing: Set<string>): string {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const bytes = randomBytes(6);
    const code = Array.from(bytes, (byte) => ALPHABET[byte % ALPHABET.length]).join('');
    if (!existing.has(code)) return code;
  }
  return randomUUID().slice(0, 6).toUpperCase();
}

function summary(group: GroupRoom): GroupSummary {
  return {
    code: group.code,
    name: group.name,
    createdAt: group.createdAt,
    memberCount: group.members.length,
  };
}

export function createGroup(name: string): Promise<GroupSummary> {
  const trimmed = name.trim();
  return queue(async () => {
    const db = await readDb();
    const group: GroupRoom = {
      code: makeCode(new Set(db.groups.map((item) => item.code))),
      name: trimmed,
      createdAt: new Date().toISOString(),
      members: [],
      messages: [],
    };
    db.groups.push(group);
    await writeDb(db);
    return summary(group);
  });
}

export function getGroup(code: string): Promise<GroupSummary | null> {
  const normalized = normalizeCode(code);
  return queue(async () => {
    const db = await readDb();
    const group = db.groups.find((item) => item.code === normalized);
    return group ? summary(group) : null;
  });
}

export function joinGroup(
  code: string,
  deviceId: string,
  name: string,
): Promise<GroupMember | null> {
  const normalized = normalizeCode(code);
  const display = name.trim();
  return queue(async () => {
    const db = await readDb();
    const group = db.groups.find((item) => item.code === normalized);
    if (!group) return null;
    const existing = group.members.find((member) => member.id === deviceId);
    if (existing) {
      existing.name = display;
      await writeDb(db);
      return existing;
    }
    const member: GroupMember = {
      id: deviceId,
      name: display,
      color: COLORS[group.members.length % COLORS.length],
      joinedAt: new Date().toISOString(),
    };
    group.members.push(member);
    await writeDb(db);
    return member;
  });
}

export function listMessages(code: string, since?: string): Promise<GroupMessage[] | null> {
  const normalized = normalizeCode(code);
  return queue(async () => {
    const db = await readDb();
    const group = db.groups.find((item) => item.code === normalized);
    if (!group) return null;
    if (!since) return group.messages;
    return group.messages.filter((message) => message.at > since);
  });
}

export function addMessage(
  code: string,
  deviceId: string,
  text: string,
): Promise<GroupMessage | null> {
  const normalized = normalizeCode(code);
  const body = text.trim();
  return queue(async () => {
    const db = await readDb();
    const group = db.groups.find((item) => item.code === normalized);
    if (!group) return null;
    const member = group.members.find((item) => item.id === deviceId);
    if (!member) return null;
    const message: GroupMessage = {
      id: randomUUID(),
      memberId: member.id,
      name: member.name,
      color: member.color,
      text: body,
      at: new Date().toISOString(),
    };
    group.messages.push(message);
    if (group.messages.length > MAX_MESSAGES) {
      group.messages.splice(0, group.messages.length - MAX_MESSAGES);
    }
    await writeDb(db);
    return message;
  });
}
