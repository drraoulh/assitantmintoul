import Link from 'next/link';
import type { ButtonHTMLAttributes, ReactNode } from 'react';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Size = 'sm' | 'md' | 'lg';

const variants: Record<Variant, string> = {
  primary:
    'bg-[var(--yellow)] text-[var(--green-deep)] hover:brightness-105 shadow-sm',
  secondary:
    'bg-[var(--green)] text-[var(--ivory)] hover:bg-[var(--green-mid)]',
  ghost:
    'bg-transparent text-[var(--ivory)] border border-white/30 hover:bg-white/10',
  danger: 'bg-[var(--red)] text-white hover:brightness-110',
};

const sizes: Record<Size, string> = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-5 py-2.5 text-sm',
  lg: 'px-6 py-3 text-base',
};

export function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  href,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  href?: string;
  children: ReactNode;
}) {
  const cls = `inline-flex items-center justify-center gap-2 rounded-full font-semibold transition ${variants[variant]} ${sizes[size]} ${className}`;
  if (href) {
    return (
      <Link href={href} className={cls}>
        {children}
      </Link>
    );
  }
  return (
    <button className={cls} {...props}>
      {children}
    </button>
  );
}

export function Badge({
  children,
  tone = 'green',
}: {
  children: ReactNode;
  tone?: 'green' | 'yellow' | 'red' | 'muted';
}) {
  const tones = {
    green: 'bg-[var(--green)]/10 text-[var(--green-deep)]',
    yellow: 'bg-[var(--yellow)]/30 text-[var(--green-deep)]',
    red: 'bg-[var(--red)]/10 text-[var(--red)]',
    muted: 'bg-[var(--line)] text-[var(--muted)]',
  };
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-xl bg-[var(--line)]/80 ${className}`}
      aria-hidden
    />
  );
}

export function EmptyState({
  title,
  body,
}: {
  title: string;
  body?: string;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-[var(--line)] bg-white/50 px-6 py-10 text-center">
      <p className="font-display text-lg text-[var(--green-deep)]">{title}</p>
      {body ? <p className="mt-2 text-sm text-[var(--muted)]">{body}</p> : null}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="rounded-2xl border border-[var(--red)]/20 bg-[var(--red)]/5 px-5 py-4 text-sm text-[var(--red)]">
      {message}
    </div>
  );
}

export function Input({
  className = '',
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={`w-full rounded-xl border border-[var(--line)] bg-white px-4 py-3 text-[var(--ink)] outline-none ring-[var(--green)] focus:ring-2 ${className}`}
      {...props}
    />
  );
}

export function Select({
  className = '',
  children,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={`w-full rounded-xl border border-[var(--line)] bg-white px-4 py-3 text-[var(--ink)] outline-none ring-[var(--green)] focus:ring-2 ${className}`}
      {...props}
    >
      {children}
    </select>
  );
}

export function TextArea({
  className = '',
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={`w-full rounded-xl border border-[var(--line)] bg-white px-4 py-3 text-[var(--ink)] outline-none ring-[var(--green)] focus:ring-2 ${className}`}
      {...props}
    />
  );
}
