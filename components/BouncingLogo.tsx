"use client";

import { useEffect, useRef, useState } from "react";
import { CADIntelligenceLogo } from "@/components/CADIntelligenceLogo";

// DVD-screensaver-style bouncer, driven by requestAnimationFrame so we can tune
// the speed and recolor the logo on every wall bounce. Each border touch cycles
// to the next palette entry below. Every color is a hue-rotation of the orange
// mark, which keeps the cube's 3D shading readable (no flat black knockouts).
// Must live inside a `relative overflow-hidden` parent. Decorative (no pointer).
const COLOR_FILTERS = [
  "none", // brand orange
  "hue-rotate(-25deg) saturate(1.3)", // red
  "hue-rotate(310deg) saturate(1.35)", // pink
  "hue-rotate(255deg) saturate(1.2)", // purple
  "hue-rotate(200deg) saturate(1.25)", // blue
  "hue-rotate(160deg) saturate(1.2)", // cyan
  "hue-rotate(120deg) saturate(1.15)" // green
];

export function BouncingLogo({
  size = 56,
  speed = 62, // px per second, per axis. Lower = slower.
  className = ""
}: {
  size?: number;
  speed?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    const el = ref.current;
    const parent = el?.parentElement;
    if (!el || !parent) return;

    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      el.style.transform = `translate3d(${(parent.clientWidth - size) / 2}px, ${
        (parent.clientHeight - size) / 2
      }px, 0)`;
      return;
    }

    let x = 10;
    let y = 10;
    let vx = 1;
    let vy = 1; // direction only; magnitude comes from `speed`
    let colorIndex = 0;
    let lastHit = -1;
    let last = performance.now();
    let raf = 0;

    const step = (now: number) => {
      const dt = Math.min(48, now - last) / 1000;
      last = now;
      const maxX = Math.max(0, parent.clientWidth - size);
      const maxY = Math.max(0, parent.clientHeight - size);

      x += vx * speed * dt;
      y += vy * speed * dt;

      let hit = false;
      if (x <= 0) {
        x = 0;
        vx = 1;
        hit = true;
      } else if (x >= maxX) {
        x = maxX;
        vx = -1;
        hit = true;
      }
      if (y <= 0) {
        y = 0;
        vy = 1;
        hit = true;
      } else if (y >= maxY) {
        y = maxY;
        vy = -1;
        hit = true;
      }

      // Recolor on every border touch. Short cooldown guards against edge
      // jitter double-counting a single bounce.
      if (hit && now - lastHit > 120) {
        lastHit = now;
        colorIndex += 1;
        setPhase(colorIndex % COLOR_FILTERS.length);
      }

      el.style.transform = `translate3d(${x}px, ${y}px, 0)`;
      raf = requestAnimationFrame(step);
    };

    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [size, speed]);

  return (
    <div
      ref={ref}
      className={`pointer-events-none absolute left-0 top-0 ${className}`}
      style={{
        width: size,
        height: size,
        opacity: 0.7,
        filter: COLOR_FILTERS[phase],
        transition: "filter 0.3s ease",
        willChange: "transform"
      }}
      aria-hidden
    >
      <CADIntelligenceLogo className="h-full w-full drop-shadow-sm" />
    </div>
  );
}
