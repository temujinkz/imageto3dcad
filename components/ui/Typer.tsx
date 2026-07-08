"use client";

import { Fragment, useEffect, useMemo, useState } from "react";

/**
 * "Typer" reveal animation, faithful port of arlan.me/vault/typer:
 * each character ripples through a few randomized visual states (fill, inverse,
 * accent, accent-inverse, accent-fill, border) before settling into plain text,
 * staggered left-to-right. Styling lives in globals.css (.typer-*).
 */
const VARIATIONS = [
  "typer-charFill",
  "typer-charInverse",
  "typer-charAccent",
  "typer-charAccentInverse",
  "typer-charAccentFill",
  "typer-charBorder"
];

const FPS = 22;
const CYCLES = 4; // random states each char cycles through before settling
const STAGGER_MS = 42; // delay between characters

type CharState = { phase: "hidden" | "active" | "settled"; variation: number };

function variationFor(index: number, frame: number): number {
  const hash = (Math.imul(index + 1, 73856093) ^ Math.imul(frame + 1, 19349663)) >>> 0;
  return hash % VARIATIONS.length;
}

export function Typer({ text, className = "" }: { text: string; className?: string }) {
  const layout = useMemo(() => {
    const words = text.split(" ");
    let index = 0;
    return words.map((word) => ({
      chars: word.split("").map((char) => ({ char, index: index++ }))
    }));
  }, [text]);
  const total = useMemo(() => text.replace(/ /g, "").length, [text]);

  const [states, setStates] = useState<CharState[]>(() =>
    Array.from({ length: total }, () => ({ phase: "hidden", variation: 0 }))
  );

  useEffect(() => {
    if (typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setStates(Array.from({ length: total }, () => ({ phase: "settled", variation: 0 })));
      return;
    }

    const frameMs = 1000 / FPS;
    const start = performance.now();
    let raf = 0;

    const loop = (now: number) => {
      const elapsed = now - start;
      let allSettled = true;
      const next: CharState[] = Array.from({ length: total }, (_unused, i) => {
        const charStart = i * STAGGER_MS;
        if (elapsed < charStart) {
          allSettled = false;
          return { phase: "hidden", variation: 0 };
        }
        const frame = Math.floor((elapsed - charStart) / frameMs);
        if (frame >= CYCLES) return { phase: "settled", variation: 0 };
        allSettled = false;
        return { phase: "active", variation: variationFor(i, frame) };
      });
      setStates(next);
      if (!allSettled) raf = requestAnimationFrame(loop);
    };

    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [total]);

  function classFor(state: CharState | undefined): string {
    if (!state || state.phase === "hidden") return "typer-charHidden";
    if (state.phase === "settled") return "";
    return VARIATIONS[state.variation];
  }

  return (
    <h1 className={className} aria-label={text}>
      {layout.map((word, wordIndex) => (
        <Fragment key={wordIndex}>
          <span className="typer-word" aria-hidden>
            {word.chars.map(({ char, index }) => (
              <span key={index} className={`typer-char ${classFor(states[index])}`}>
                {char}
              </span>
            ))}
          </span>
          {wordIndex < layout.length - 1 ? " " : null}
        </Fragment>
      ))}
    </h1>
  );
}
