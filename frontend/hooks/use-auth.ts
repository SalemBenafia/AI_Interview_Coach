"use client";

/**
 * hooks/use-auth.ts
 * ==================
 * Authentication hook — wraps Server Actions, manages Zustand state.
 * Never handles token strings.
 */

import { useCallback, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  useAuthStore,
  selectUser,
  selectIsAuthenticated,
  selectIsLoading,
  selectAuthError,
  selectIsAdmin,
  selectIsSuperAdmin,
  selectIsCandidate,
} from "@/store/use-auth-store";
import { loginAction, registerAction, logoutAction } from "@/app/actions/auth.actions";
import type { LoginPayload } from "@/lib/auth/auth.server";

export function useAuth() {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  const user = useAuthStore(selectUser);
  const isAuthenticated = useAuthStore(selectIsAuthenticated);
  const storeLoading = useAuthStore(selectIsLoading);
  const error = useAuthStore(selectAuthError);
  const isAdmin = useAuthStore(selectIsAdmin);
  const isSuperAdmin = useAuthStore(selectIsSuperAdmin);
  const isCandidate = useAuthStore(selectIsCandidate);

  const { setUser, clearUser, setLoading, setError, clearError } = useAuthStore();

  const isLoading = isPending || storeLoading;

  // One unified login for both candidates and admins — the backend resolves
  // which kind of account it is from the credentials alone (see
  // POST /auth/login/). Where we redirect afterward depends on the
  // returned user's principalType, never on a choice the caller made.
  const login = useCallback(
    async (payload: LoginPayload): Promise<boolean> => {
      setLoading(true);
      clearError();
      try {
        const result = await loginAction(payload);
        if (!result.ok) {
          setError(result.error.message);
          return false;
        }
        setUser(result.data);
        router.replace(result.data.principalType === "admin" ? "/admin/dashboard" : "/candidate/dashboard");
        router.refresh();
        return true;
      } catch {
        setError("An unexpected error occurred.");
        return false;
      } finally {
        setLoading(false);
      }
    },
    [setLoading, clearError, setError, setUser, router]
  );

  const register = useCallback(
    async (payload: { email: string; password: string; firstName: string; lastName: string }) => {
      setLoading(true);
      clearError();
      try {
        const result = await registerAction({
          email: payload.email,
          password: payload.password,
          first_name: payload.firstName,
          last_name: payload.lastName,
        });
        if (!result.ok) {
          setError(result.error.message);
          return false;
        }
        setUser(result.data);
        router.replace("/candidate/dashboard");
        router.refresh();
        return true;
      } catch {
        setError("Could not create your account.");
        return false;
      } finally {
        setLoading(false);
      }
    },
    [setLoading, clearError, setError, setUser, router]
  );

  const logout = useCallback(() => {
    startTransition(async () => {
      clearUser();
      await logoutAction();
      router.replace("/login");
    });
  }, [clearUser, router]);

  return {
    user,
    isAuthenticated,
    isLoading,
    error,
    isAdmin,
    isSuperAdmin,
    isCandidate,
    login,
    register,
    logout,
    clearError,
  };
}
