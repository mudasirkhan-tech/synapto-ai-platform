export default function Mascot() {
  return (
    <svg viewBox="0 0 280 250" className="h-full w-full" fill="none" aria-label="Synapto mascot">
      <defs>
        <linearGradient id="m-head" x1="60" y1="20" x2="220" y2="170" gradientUnits="userSpaceOnUse">
          <stop stopColor="#f4f3ff" /><stop offset=".6" stopColor="#c9c4f5" /><stop offset="1" stopColor="#8e86e8" />
        </linearGradient>
        <linearGradient id="m-body" x1="90" y1="150" x2="200" y2="240" gradientUnits="userSpaceOnUse">
          <stop stopColor="#e4e1fb" /><stop offset="1" stopColor="#7d74dc" />
        </linearGradient>
        <linearGradient id="m-orbit" x1="0" y1="0" x2="280" y2="0">
          <stop stopColor="#6d4dff" /><stop offset="1" stopColor="#4aa3ff" />
        </linearGradient>
        <radialGradient id="m-glow" cx=".5" cy=".5" r=".5">
          <stop stopColor="#6d4dff" stopOpacity=".35" /><stop offset="1" stopColor="#6d4dff" stopOpacity="0" />
        </radialGradient>
      </defs>
      <ellipse cx="140" cy="125" rx="130" ry="115" fill="url(#m-glow)" />
      {/* orbit ring (back) */}
      <ellipse cx="150" cy="190" rx="120" ry="30" transform="rotate(-12 150 190)" stroke="url(#m-orbit)" strokeWidth="2.5" />
      {/* body */}
      <path d="M100 168c0-14 80-14 80 0 4 26-6 52-40 52s-44-26-40-52Z" fill="url(#m-body)" />
      <circle cx="140" cy="190" r="15" fill="#2b2470" />
      <path d="M135 183c6-3 12 0 8 4s-10 4-6 9c3 3 9 1 10-1" stroke="#c4b5fd" strokeWidth="3.5" strokeLinecap="round" />
      {/* arm */}
      <ellipse cx="86" cy="196" rx="14" ry="11" fill="url(#m-body)" transform="rotate(-30 86 196)" />
      <ellipse cx="196" cy="188" rx="12" ry="10" fill="url(#m-body)" />
      {/* headphones */}
      <rect x="44" y="76" width="16" height="42" rx="8" fill="#5b4fd6" />
      <rect x="220" y="76" width="16" height="42" rx="8" fill="#5b4fd6" />
      {/* head */}
      <rect x="56" y="30" width="168" height="130" rx="58" fill="url(#m-head)" />
      <rect x="72" y="50" width="136" height="88" rx="40" fill="#07080e" />
      <rect x="72" y="50" width="136" height="88" rx="40" stroke="#4d3fd0" strokeWidth="2" />
      {/* eyes + smile */}
      <path d="M96 94c6-14 24-14 30 0" stroke="#22d3ee" strokeWidth="6" strokeLinecap="round" />
      <path d="M154 94c6-14 24-14 30 0" stroke="#22d3ee" strokeWidth="6" strokeLinecap="round" />
      <path d="M128 112c6 7 18 7 24 0" stroke="#22d3ee" strokeWidth="5" strokeLinecap="round" />
      {/* orbit ring (front) */}
      <path d="M32 172c30 30 150 36 215-6" stroke="url(#m-orbit)" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}
