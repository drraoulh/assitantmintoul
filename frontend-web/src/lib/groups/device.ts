const DEVICE_KEY = 'smartmboa-device';

export function getDeviceId(): string {
  const existing = localStorage.getItem(DEVICE_KEY);
  if (existing) return existing;
  const id = crypto.randomUUID();
  localStorage.setItem(DEVICE_KEY, id);
  return id;
}

export function savedName(code: string): string {
  return localStorage.getItem(`smartmboa-group:${code}`) ?? '';
}

export function rememberName(code: string, name: string): void {
  localStorage.setItem(`smartmboa-group:${code}`, name);
}
