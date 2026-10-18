"use client";
import { useEffect, useState } from "react";
import { fetchStatus, type SystemStatus } from "./api";

export type StatusState =
  | { phase: "loading" }
  | { phase: "api-down" }
  | { phase: "ready"; data: SystemStatus };

export function useSystemStatus(intervalMs = 10000): StatusState {
  const [state, setState] = useState<StatusState>({ phase: "loading" });

  useEffect(() => {
    let alive = true;
    let controller = new AbortController();

    const poll = async () => {
      controller = new AbortController();
      try {
        const data = await fetchStatus(controller.signal);
        if (alive) setState({ phase: "ready", data });
      } catch {
        if (alive && !controller.signal.aborted) setState({ phase: "api-down" });
      }
    };

    poll();
    const id = setInterval(poll, intervalMs);
    return () => { alive = false; controller.abort(); clearInterval(id); };
  }, [intervalMs]);

  return state;
}
