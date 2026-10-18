export default function Logo({ size = 56 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="syn-g" x1="8" y1="8" x2="56" y2="58" gradientUnits="userSpaceOnUse">
          <stop stopColor="#c084fc" />
          <stop offset=".55" stopColor="#7c5cff" />
          <stop offset="1" stopColor="#3b82f6" />
        </linearGradient>
      </defs>
      <g transform="skewX(-8) translate(5 0)">
        <path d="M46 16c-4-6-20-8-24 1-4 9 6 12 15 15 9 3 12 10 6 16-6 6-20 4-27-3"
          stroke="url(#syn-g)" strokeWidth="11" strokeLinecap="round" strokeLinejoin="round" />
      </g>
    </svg>
  );
}
