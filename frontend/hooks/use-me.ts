"use client";

/**
 * hooks/use-me.ts
 * =================
 * Hydrates the auth store from /me/ on mount — keeps the Zustand store in
 * sync with the HttpOnly-cookie session without ever touching the tokens.
 */
import { useEffect } from "react";
import apiClient from "@/lib/api/client";
import { useAuthStore } from "@/store/use-auth-store";
import type { User } from "@/lib/api/transformers";

interface RawMe {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  principalType: "candidate" | "admin";
  roles: string[];
  avatarUrl?: string | null;
  resumeUrl?: string | null;
  headline?: string | null;
  preferredLanguage?: string;
  notificationPrefs?: Record<string, boolean>;
  mfaEnabled?: boolean;
}

export function useMe() {
  const setUser = useAuthStore((s) => s.setUser);
  const user = useAuthStore((s) => s.user);

  useEffect(() => {
    let cancelled = false;
    apiClient
      .get<{ success: boolean; data: RawMe | null }>("/me/")
      .then((res) => {
        if (cancelled || !res.data.data) return;
        const raw = res.data.data;
        setUser(raw as User);
      })
      .catch(() => {
        // Silent — middleware already redirects unauthenticated users away
        // from protected routes before this hook ever runs.
      });
    return () => {
      cancelled = true;
    };
  }, [setUser]);

  return { user };
}
