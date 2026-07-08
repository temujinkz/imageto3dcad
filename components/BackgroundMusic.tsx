"use client";

import { useEffect, useRef, useState } from "react";
import { Volume1, Volume2, VolumeX } from "lucide-react";

// Loops a background track with a volume slider. Browsers block autoplay-with-
// sound until the user interacts, so playback kicks off on the first pointer/
// key event anywhere. The speaker icon toggles mute; the slider sets volume.
export function BackgroundMusic({ src = "/minecraft.mp3", defaultVolume = 0.6 }: { src?: string; defaultVolume?: number }) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const prevVolume = useRef(defaultVolume);
  const [volume, setVolume] = useState(defaultVolume);

  // Keep the element volume in sync with state.
  useEffect(() => {
    const el = audioRef.current;
    if (el) el.volume = volume;
  }, [volume]);

  // Start playback on the first interaction (autoplay policy).
  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;
    const start = () => el.play().catch(() => {});
    window.addEventListener("pointerdown", start, { once: true });
    window.addEventListener("keydown", start, { once: true });
    return () => {
      window.removeEventListener("pointerdown", start);
      window.removeEventListener("keydown", start);
    };
  }, []);

  function ensurePlaying() {
    const el = audioRef.current;
    if (el?.paused) el.play().catch(() => {});
  }

  function onSlide(event: React.ChangeEvent<HTMLInputElement>) {
    const next = Number(event.target.value) / 100;
    setVolume(next);
    if (next > 0) {
      prevVolume.current = next;
      ensurePlaying();
    }
  }

  function toggleMute() {
    if (volume > 0) {
      prevVolume.current = volume;
      setVolume(0);
    } else {
      setVolume(prevVolume.current || 0.6);
      ensurePlaying();
    }
  }

  const Icon = volume === 0 ? VolumeX : volume < 0.45 ? Volume1 : Volume2;

  return (
    <>
      <audio ref={audioRef} src={src} loop preload="auto" />
      <div className="fixed bottom-4 right-4 z-50 flex items-center gap-2.5 rounded-full border border-line bg-card/90 px-3 py-2 shadow-card backdrop-blur">
        <button
          type="button"
          onClick={toggleMute}
          aria-label={volume === 0 ? "Unmute background music" : "Mute background music"}
          title={volume === 0 ? "Unmute" : "Mute"}
          className="inline-flex h-6 w-6 items-center justify-center text-muted transition-colors duration-200 hover:text-accent"
        >
          <Icon className="h-4 w-4" aria-hidden />
        </button>
        <input
          type="range"
          min={0}
          max={100}
          value={Math.round(volume * 100)}
          onChange={onSlide}
          aria-label="Music volume"
          className="h-1 w-24 cursor-pointer accent-[#f2612f]"
        />
      </div>
    </>
  );
}
