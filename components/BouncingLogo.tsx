"use client";

import type { CSSProperties } from "react";
import { CADIntelligenceLogo } from "@/components/CADIntelligenceLogo";

// A DVD-screensaver-style bouncer: the logo drifts corner to corner forever,
// bouncing off every edge. Must live inside a `relative overflow-hidden` parent.
// Two independent x/y animations at coprime durations give the classic path
// that occasionally kisses a corner. Decorative only (pointer-events: none).
export function BouncingLogo({
  size = 60,
  durX = "3.6s",
  durY = "2.7s",
  className = ""
}: {
  size?: number;
  durX?: string;
  durY?: string;
  className?: string;
}) {
  return (
    <div
      className={`ci-bouncer pointer-events-none ${className}`}
      style={
        {
          "--ci-size": `${size}px`,
          "--ci-dur-x": durX,
          "--ci-dur-y": durY,
          width: size,
          height: size
        } as CSSProperties
      }
      aria-hidden
    >
      <CADIntelligenceLogo className="h-full w-full drop-shadow-sm" />
    </div>
  );
}
