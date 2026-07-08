"use client";

// CAD Intelligence mark: an isometric 3D cube (the CAD object) with a small
// neural-network node cluster on its top face as the "intelligence" cue.
// Self-contained SVG (no external assets) so it can be inlined and animated.
export function CADIntelligenceLogo({
  className,
  title = "CAD Intelligence"
}: {
  className?: string;
  title?: string;
}) {
  return (
    <svg
      viewBox="0 0 64 64"
      className={className}
      role="img"
      aria-label={title}
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* three shaded faces of an isometric cube */}
      <path d="M32 12 L50 22 L32 32 L14 22 Z" fill="#ffb488" />
      <path d="M14 22 L32 32 L32 52 L14 42 Z" fill="#f2612f" />
      <path d="M50 22 L32 32 L32 52 L50 42 Z" fill="#d1481c" />

      {/* outer silhouette + inner edges for a crisp CAD wireframe read */}
      <path
        d="M32 12 L50 22 L50 42 L32 52 L14 42 L14 22 Z"
        fill="none"
        stroke="#c9481c"
        strokeOpacity="0.35"
        strokeWidth="1"
        strokeLinejoin="round"
      />
      <g stroke="#b23f18" strokeOpacity="0.5" strokeWidth="0.75" strokeLinecap="round">
        <line x1="14" y1="22" x2="32" y2="32" />
        <line x1="50" y1="22" x2="32" y2="32" />
        <line x1="32" y1="32" x2="32" y2="52" />
      </g>

      {/* neural network mark on the top face — the intelligence cue */}
      <g stroke="#1a1a17" strokeWidth="1" strokeLinecap="round" opacity="0.85">
        <line x1="32" y1="17" x2="26" y2="23" />
        <line x1="32" y1="17" x2="38" y2="23" />
        <line x1="26" y1="23" x2="38" y2="23" />
      </g>
      <g fill="#1a1a17">
        <circle cx="32" cy="17" r="1.6" />
        <circle cx="26" cy="23" r="1.6" />
        <circle cx="38" cy="23" r="1.6" />
      </g>
    </svg>
  );
}
