"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";

type DepthButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
};

/**
 * The "color depth" duotone button (arlan.me/vault/color-depth): a hard-bevel
 * extruded orange key. Styling lives in globals.css (.depth-btn/.depth-duotone).
 */
export function DepthButton({ children, className = "", ...props }: DepthButtonProps) {
  return (
    <button className={`depth-btn depth-duotone ${className}`} {...props}>
      <span className="depth-label">{children}</span>
    </button>
  );
}
