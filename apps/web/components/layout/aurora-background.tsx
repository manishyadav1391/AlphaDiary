"use client";

/*
  Aurora background (spec §7).

  Three large blurred radial gradients slowly drifting on a 30–40s loop.
  A faint grid overlay and SVG noise prevent gradient banding. Everything
  is position: fixed behind all content with pointer-events: none.

  The aurora drift pauses when the tab is hidden (visibilitychange) and
  when prefers-reduced-motion is set (CSS handles that via globals.css).
*/

export function AuroraBackground() {
  return (
    <div
      className="pointer-events-none fixed inset-0 -z-10 overflow-hidden"
      aria-hidden
    >
      {/* Base */}
      <div className="absolute inset-0 bg-bg-0" />

      {/* Aurora blob 1: violet, top-left */}
      <div
        className="absolute -left-[10%] -top-[10%] h-[800px] w-[800px] rounded-full opacity-35 blur-[120px] motion-safe:animate-[aurora-drift-1_35s_ease-in-out_infinite]"
        style={{ background: "#7c3aed" }}
      />

      {/* Aurora blob 2: indigo, bottom-right */}
      <div
        className="absolute -bottom-[15%] -right-[10%] h-[700px] w-[700px] rounded-full opacity-25 blur-[120px] motion-safe:animate-[aurora-drift-2_40s_ease-in-out_infinite]"
        style={{ background: "#4f46e5" }}
      />

      {/* Aurora blob 3: magenta, center-right */}
      <div
        className="absolute right-[10%] top-[40%] h-[600px] w-[600px] rounded-full opacity-15 blur-[120px] motion-safe:animate-[aurora-drift-3_32s_ease-in-out_infinite]"
        style={{ background: "#c026d3" }}
      />

      {/* Subtle grid (spec §7, optional) */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          maskImage:
            "radial-gradient(ellipse 70% 70% at 50% 50%, black 30%, transparent 80%)",
          WebkitMaskImage:
            "radial-gradient(ellipse 70% 70% at 50% 50%, black 30%, transparent 80%)",
        }}
      />

      {/* Noise overlay to prevent gradient banding (spec §7). */}
      <svg className="absolute inset-0 h-full w-full opacity-[0.03]">
        <filter id="aurora-noise">
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.65"
            numOctaves="3"
            stitchTiles="stitch"
          />
        </filter>
        <rect width="100%" height="100%" filter="url(#aurora-noise)" />
      </svg>
    </div>
  );
}

