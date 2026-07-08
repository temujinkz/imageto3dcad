"use client";

import { Fragment, useEffect, useMemo, useState } from "react";

/**
 * "Typer" reveal animation, adapted from arlan.me/vault/typer: each character
 * ripples through a few randomized visual states (fill, inverse, accent,
 * accent-inverse, accent-fill, border) before settling into plain text. The
 * wave sweeps left-to-right, then right-to-left, then repeats (with a short
 * pause between passes). Styling lives in globals.css (.typer-*).
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
const PAUSE_MS = 1500; // rest between each directional sweep

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
    if (total === 0) return;
    if (typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setStates(Array.from({ length: total }, () => ({ phase: "settled", variation: 0 })));
      return;
    }

    const frameMs = 1000 / FPS;
    // One sweep = every char takes its turn, plus the trailing settle + pause.
    const sweepMs = (total - 1) * STAGGER_MS + CYCLES * frameMs + PAUSE_MS;
    const activeEndMs = (total - 1) * STAGGER_MS + CYCLES * frameMs;
    const settledStates = Array.from({ length: total }, () => ({ phase: "settled", variation: 0 }) as CharState);

    const start = performance.now();
    let raf = 0;
    let lastTick = -1;
    let pausedSweep = -1;

    const loop = (now: number) => {
      const elapsed = now - start;
      const sweep = Math.floor(elapsed / sweepMs);
      const local = elapsed - sweep * sweepMs;
      const leftToRight = sweep % 2 === 0;

      if (local > activeEndMs) {
        // Trailing pause: everything settled. Push once, then idle until the
        // next sweep instead of re-rendering every frame.
        if (pausedSweep !== sweep) {
          pausedSweep = sweep;
          setStates(settledStates);
        }
      } else {
        const tick = Math.floor(local / frameMs);
        if (tick !== lastTick) {
          lastTick = tick;
          const next: CharState[] = Array.from({ length: total }, (_unused, i) => {
            const order = leftToRight ? i : total - 1 - i; // sweep direction
            const charStart = order * STAGGER_MS;
            if (local < charStart) {
              // Hidden only during the very first reveal; visible thereafter.
              return { phase: sweep === 0 ? "hidden" : "settled", variation: 0 };
            }
            const frame = Math.floor((local - charStart) / frameMs);
            if (frame >= CYCLES) return { phase: "settled", variation: 0 };
            return { phase: "active", variation: variationFor(order, frame) };
          });
          setStates(next);
        }
      }
      raf = requestAnimationFrame(loop);
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
