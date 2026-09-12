"use client";

import { useEffect } from "react";
import { API_BASE_URL } from "@/lib/api/client";

/**
 * Best-effort cleanup for the "closed the tab mid-interview" case. Fires a
 * bodyless POST to the end-interview endpoint via sendBeacon on `pagehide`
 * (not `beforeunload` -- more reliable across mobile/bfcache and doesn't
 * block navigation with a confirm dialog). This can't guarantee delivery,
 * so it's a fast-path only -- the LiveKit webhook and the Celery sweep task
 * (app.modules.interviews.sweep_tasks) are the reliable mechanisms that
 * actually keep sessions from getting stuck in ACTIVE.
 *
 * Auth cookies are HttpOnly and not port-scoped on localhost, so sendBeacon
 * carries them automatically for the local dev stack (frontend :3000,
 * backend :8000, same "localhost" domain). In a deployment where the API
 * lives on a different registrable domain than the frontend, this beacon
 * would need withCredentials-equivalent cross-site cookie support configured
 * server-side for it to still work.
 */
export function useEndOnUnload(sessionId: string | null, active: boolean): void {
  useEffect(() => {
    if (!sessionId || !active) return;

    const url = `${API_BASE_URL}/interviews/sessions/${sessionId}/end/`;
    const handler = () => {
      navigator.sendBeacon(url);
    };

    window.addEventListener("pagehide", handler);
    return () => window.removeEventListener("pagehide", handler);
  }, [sessionId, active]);
}
