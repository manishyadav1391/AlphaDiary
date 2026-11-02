# DESIGN.md: TJ Design System (Dark Glassmorphism · Violet Accent · Rich Motion)

> This document is the single source of truth for the app's UI/UX design.

---

## 1. Principles

1. **Depth through light, not borders.** Use translucent surfaces, a 1px inner highlight, soft blur and glow — never heavy outlines.
2. **Numbers are heroes.** P&L, win rate, equity — big, monospaced, tabular, colour-coded.
3. **Profit = emerald, loss = rose, brand = violet.** Never use violet to mean profit/loss.
4. **Calm by default, delightful on key moments.** Motion should be smooth and purposeful; celebration (confetti) only on genuinely good events.
5. **One focal point per screen.** Everything else recedes.
6. **Fast.** Animations are GPU-friendly (transform/opacity), never block input, never exceed ~600ms for UI transitions.
7. **Accessible.** Glass must never compromise contrast.

---

## 2. Visual Identity & Palette

- **Base canvas:** Near-black blue/violet (`#07060d`) with a slow-moving aurora gradient behind everything.
- **Surfaces:** Frosted glass cards (`backdrop-filter: blur(16px)`) with gradient hairline borders and top highlights.
- **Brand accent:** Violet gradient (`#8b5cf6` → `#6d28d9`) for primary actions, active navigation, focus rings, selected chips.
- **Semantic indicators:**
  - Profit: `#34d399` (emerald-400), background `rgba(52, 211, 153, 0.12)`, soft glow.
  - Loss: `#fb7185` (rose-400), background `rgba(251, 113, 133, 0.12)`, soft glow.
  - Warning/Attention: `#fbbf24` (amber), pulsing dot on "Login needed".

---

## 3. Typography

- **UI Font:** `Inter` (variable).
- **Numeric Font:** `JetBrains Mono` for P&L, prices, quantities, and times. Always `font-variant-numeric: tabular-nums`.
- Negative numbers use the true minus `−` (U+2212), positives show `+`.
- Currency formatting follows Indian numbering (`en-IN`): `₹1,24,500.00`.

---

## 4. Glass Surface Recipe

```css
.glass {
  position: relative;
  background: linear-gradient(180deg, rgba(255,255,255,0.07) 0%, rgba(255,255,255,0.02) 100%);
  border: 1px solid var(--glass-border);
  border-radius: var(--r-lg);
  backdrop-filter: blur(16px) saturate(140%);
  box-shadow: 0 1px 0 0 rgba(255,255,255,0.18) inset, 0 8px 24px -12px rgba(0,0,0,0.6);
}
```

---

## 5. Motion Guidelines

- **Stagger entrances:** Content enters with a staggered fade-and-rise (delay ~60ms).
- **Celebrations:** Confetti fires exclusively on:
  1. Green day reveal (today's net P&L > 0, max once per day).
  2. New equity high after sync.
  3. Playbook review saved with Discipline rating ≥ 4.
- **Reduced motion:** All ambient drift, stagger, and confetti animations are disabled when `prefers-reduced-motion` is active.
