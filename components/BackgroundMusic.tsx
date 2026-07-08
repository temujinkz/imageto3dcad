"use client";

import { useEffect, useRef, useState } from "react";
import { Volume2, VolumeX } from "lucide-react";

// Loops a background track. Browsers block autoplay-with-sound until the user
// interacts, so we kick playback off on the first pointer/key event anywhere,
// then expose a mute toggle so it's never a trap.
export function BackgroundMusic({ src = "/minecraft.mp3", volume = 0.35 }: { src?: string; volume?: number }) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [muted, setMuted] = useState(false);

  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;
    el.volume = volume;
    const start = () => {
      el.play().catch(() => {});
    };
    // `once` so each listener self-removes after the first interaction.
    window.addEventListener("pointerdown", start, { once: true });
    window.addEventListener("keydown", start, { once: true });
    return () => {
      window.removeEventListener("pointerdown", start);
      window.removeEventListener("keydown", start);
    };
  }, [volume]);

  function toggle() {
    const el = audioRef.current;
    if (!el) return;
    if (el.paused) {
      el.muted = false;
      setMuted(false);
      el.play().catch(() => {});
      return;
    }
    const next = !el.muted;
    el.muted = next;
    setMuted(next);
  }

  return (
    <>
      <audio ref={audioRef} src={src} loop preload="auto" />
      <button
        type="button"
        onClick={toggle}
        aria-label={muted ? "Unmute background music" : "Mute background music"}
        title={muted ? "Unmute music" : "Mute music"}
        className="fixed bottom-4 right-4 z-50 inline-flex h-10 w-10 items-center justify-center rounded-full border border-line bg-card/90 text-muted shadow-card backdrop-blur transition duration-200 hover:-translate-y-0.5 hover:text-accent"
      >
        {muted ? <VolumeX className="h-4 w-4" aria-hidden /> : <Volume2 className="h-4 w-4" aria-hidden />}
      </button>
    </>
  );
}
