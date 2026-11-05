// Skeletonizer - avoid skeleton flashes.
// show=false for the first `delay` ms of loading (fast loads never show a skeleton),
// and once shown it stays at least `minDuration` ms (no blink-and-gone).
// While loading but not yet shown, render nothing or the previous data - not the final empty state.
import { useEffect, useRef, useState } from "react";

export function useDelayedLoading(
  isLoading: boolean,
  { delay = 200, minDuration = 400 }: { delay?: number; minDuration?: number } = {}
): boolean {
  const [show, setShow] = useState(false);
  const shownAt = useRef<number | null>(null);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    if (isLoading && !show) {
      timer = setTimeout(() => {
        shownAt.current = Date.now();
        setShow(true);
      }, delay);
    } else if (!isLoading && show) {
      const elapsed = Date.now() - (shownAt.current ?? Date.now());
      timer = setTimeout(() => {
        shownAt.current = null;
        setShow(false);
      }, Math.max(0, minDuration - elapsed));
    }
    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [isLoading, show, delay, minDuration]);

  return show;
}

/* Usage
   const { data, isLoading } = useQuery(...);
   const showSkeleton = useDelayedLoading(isLoading);
   if (showSkeleton) return <ProjectListSkeleton />;
   if (isLoading) return null;          // inside the 200 ms grace period
   if (error) return <ErrorState />;
   return <ProjectList items={data} />;
*/
