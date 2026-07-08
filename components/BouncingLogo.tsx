"use client";

import { useEffect, useRef, useState } from "react";
import { CADIntelligenceLogo } from "@/components/CADIntelligenceLogo";

// DVD-screensaver-style bouncer, driven by requestAnimationFrame so we can (a)
// tune the speed and (b) detect corner hits — which pure CSS keyframes can't.
// On each corner it cycles color: normal -> black -> inverted -> normal ...
// Must live inside a `relative overflow-hidden` parent. Decorative (no pointer).
const PHASE_FILTER = ["none", "brightness(0)", "invert(1)"];

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
    let corner = 0;
    let lastCorner = -1;
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

      // Corner = we bounced while sitting near a corner on both axes. Debounced
      // so a single corner approach only advances the color once.
      const near = size * 0.9;
      const nearCorner = (x <= near || x >= maxX - near) && (y <= near || y >= maxY - near);
      if (hit && nearCorner && now - lastCorner > 600) {
        lastCorner = now;
        corner += 1;
        setPhase(corner % PHASE_FILTER.length);
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
        filter: PHASE_FILTER[phase],
        transition: "filter 0.3s ease",
        willChange: "transform"
      }}
      aria-hidden
    >
      <CADIntelligenceLogo className="h-full w-full drop-shadow-sm" />
    </div>
  );
}
