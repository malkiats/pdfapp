import { useSyncExternalStore } from "react";

const noopSubscribe = () => () => undefined;

/** False during server rendering and hydration, true afterwards. Avoids hydration mismatches for client-only state. */
export function useMounted(): boolean {
  return useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false,
  );
}
