// Motionsite - scroll reveal hook for React. Pair with the .reveal / .is-in CSS from templates/site.html.
// Content is visible when IntersectionObserver is missing or the visitor prefers reduced motion.
import { useEffect, useRef, useState } from "react";

export function useReveal<T extends HTMLElement>(options: IntersectionObserverInit = { threshold: 0.15, rootMargin: "0px 0px -8% 0px" }) {
  const ref = useRef<T | null>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce || !("IntersectionObserver" in window)) {
      setShown(true);
      return;
    }
    const io = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setShown(true);
        io.disconnect();
      }
    }, options);
    io.observe(el);
    return () => io.disconnect();
    // options object is intentionally read once
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { ref, shown };
}

/* Usage
   const { ref, shown } = useReveal<HTMLDivElement>();
   <div ref={ref} className={`reveal ${shown ? "is-in" : ""}`}>...</div>
   Add "js" to <html> in your root layout script so the hidden state only applies when JS runs.
*/
