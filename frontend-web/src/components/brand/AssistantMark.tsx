import Image from 'next/image';

const SIZES = {
  sm: 'h-9 w-9',
  md: 'h-14 w-14',
  lg: 'h-24 w-24',
} as const;

/** Official emblem, framed as the assistant mark. */
export function AssistantMark({
  size = 'md',
  className = '',
}: {
  size?: keyof typeof SIZES;
  className?: string;
}) {
  return (
    <span
      className={`relative inline-flex shrink-0 items-center justify-center ${SIZES[size]} ${className}`}
      aria-hidden
    >
      <span className="assistant-halo absolute -inset-1 rounded-full bg-[#FCD116] blur-md" />
      <span className="relative flex h-full w-full items-center justify-center overflow-hidden rounded-full bg-white shadow-[0_10px_24px_rgba(0,122,94,0.28)] ring-[3px] ring-[#007A5E]">
        <span className="pointer-events-none absolute inset-[3px] rounded-full ring-[2px] ring-[#CE1126]" />
        <Image
          src="/brand/mark.png"
          alt=""
          width={512}
          height={512}
          className="h-[175%] w-[175%] max-w-none object-contain"
        />
      </span>
    </span>
  );
}
