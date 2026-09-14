import { useEffect, useRef, useState } from "react";

/** Ticks a counter every second while `active`, resetting to 0 whenever it becomes active. */
export function useElapsedSeconds(active: boolean): number {
  const [seconds, setSeconds] = useState(0);
  const startRef = useRef<number | null>(null);

  useEffect(() => {
    if (!active) {
      startRef.current = null;
      setSeconds(0);
      return;
    }
    startRef.current = Date.now();
    const id = setInterval(() => {
      setSeconds(Math.floor((Date.now() - (startRef.current ?? Date.now())) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, [active]);

  return seconds;
}
