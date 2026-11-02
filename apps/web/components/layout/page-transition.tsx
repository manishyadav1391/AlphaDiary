import type { ReactNode } from "react";

/**
 * The page entrance.
 *
 * This used to be a `motion.div` animating opacity, y and `filter: blur()`.
 * Both a transform and a filter make an element a containing block for
 * `position: sticky` and `position: fixed` descendants — and because the
 * animation settled on `blur(0px)` rather than `none`, that containing block
 * never went away. The trades page's `sticky top-16` filter bar was therefore
 * anchored to this wrapper instead of the viewport and sat on top of the
 * rows.
 *
 * A CSS animation without `forwards` leaves no transform and no filter behind
 * once it finishes, so sticky children behave normally. There is no
 * AnimatePresence above this, so the old `exit` variant never ran anyway.
 */
export function PageTransition({ children }: { children: ReactNode }) {
  return <div className="page-enter w-full flex-1">{children}</div>;
}
