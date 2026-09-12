/**
 * store/use-auth-store.ts
 * ========================
 * Global authentication state (Zustand).
 * Stores the User profile — NOT tokens (those stay in HttpOnly cookies).
 */

import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";
import type { User } from "@/lib/api/transformers";

interface AuthState {
  user: User | null;
  isLoading: boolean;
  error: string | null;

  setUser: (user: User) => void;
  clearUser: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string) => void;
  clearError: () => void;

  isAuthenticated: boolean;
  isAdmin: boolean;
  isCandidate: boolean;
  isSuperAdmin: boolean;
}

export const useAuthStore = create<AuthState>()(
  devtools(
    persist(
      (set) => ({
        user: null,
        isLoading: false,
        error: null,

        setUser: (user) =>
          set(
            {
              user,
              isLoading: false,
              error: null,
              isAuthenticated: true,
              isAdmin: user.principalType === "admin",
              isCandidate: user.principalType === "candidate",
              isSuperAdmin: user.principalType === "admin" && user.roles.includes("super_admin"),
            },
            false,
            "auth/setUser"
          ),

        clearUser: () =>
          set(
            { user: null, isAuthenticated: false, isAdmin: false, isCandidate: false, isSuperAdmin: false },
            false,
            "auth/clearUser"
          ),

        setLoading: (isLoading) => set({ isLoading }, false, "auth/setLoading"),
        setError: (error) => set({ error, isLoading: false }, false, "auth/setError"),
        clearError: () => set({ error: null }, false, "auth/clearError"),

        isAuthenticated: false,
        isAdmin: false,
        isCandidate: false,
        isSuperAdmin: false,
      }),
      {
        name: "interview-coach-auth",
        partialize: (state) => ({
          user: state.user,
          isAuthenticated: state.isAuthenticated,
          isAdmin: state.isAdmin,
          isCandidate: state.isCandidate,
          isSuperAdmin: state.isSuperAdmin,
        }),
      }
    ),
    { name: "InterviewCoach/Auth" }
  )
);

export const selectUser = (s: AuthState) => s.user;
export const selectIsAuthenticated = (s: AuthState) => s.isAuthenticated;
export const selectIsLoading = (s: AuthState) => s.isLoading;
export const selectAuthError = (s: AuthState) => s.error;
export const selectIsAdmin = (s: AuthState) => s.isAdmin;
export const selectIsCandidate = (s: AuthState) => s.isCandidate;
export const selectIsSuperAdmin = (s: AuthState) => s.isSuperAdmin;
