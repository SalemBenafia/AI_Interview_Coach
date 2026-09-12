"use server";

/**
 * app/actions/auth.actions.ts
 * ==============================
 * Server Actions for authentication. There is exactly ONE login form and
 * ONE backend endpoint (/auth/login/) — the caller never declares whether
 * they're a candidate or an admin. The returned user's principalType tells
 * the caller where to route afterward.
 */

import {
  type ActionResult,
  type LoginPayload,
  clearAuthCookies,
  mirrorAuthCookiesFromResponse,
  normaliseActionError,
  serverFetch,
} from "@/lib/auth/auth.server";
import type { User } from "@/lib/api/transformers";

interface RawPrincipal {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  principal_type: "candidate" | "admin";
  roles: string[];
}

function toUser(raw: RawPrincipal): User {
  return {
    id: raw.id,
    email: raw.email,
    firstName: raw.first_name,
    lastName: raw.last_name,
    principalType: raw.principal_type,
    roles: raw.roles,
  };
}

export async function loginAction(payload: LoginPayload): Promise<ActionResult<User>> {
  try {
    const { data, response } = await serverFetch<{ data: { user: RawPrincipal } }>("/auth/login/", {
      body: payload,
    });
    await mirrorAuthCookiesFromResponse(response);
    return { ok: true, data: toUser(data.data.user) };
  } catch (error) {
    return { ok: false, error: normaliseActionError(error) };
  }
}

export async function registerAction(payload: {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
}): Promise<ActionResult<User>> {
  try {
    const { data, response } = await serverFetch<{ data: { user: RawPrincipal } }>("/auth/register/", {
      body: payload,
    });
    await mirrorAuthCookiesFromResponse(response);
    return { ok: true, data: toUser(data.data.user) };
  } catch (error) {
    return { ok: false, error: normaliseActionError(error) };
  }
}

export async function forgotPasswordAction(email: string): Promise<ActionResult<void>> {
  try {
    await serverFetch("/auth/forgot-password/", { body: { email } });
    return { ok: true, data: undefined };
  } catch (error) {
    return { ok: false, error: normaliseActionError(error) };
  }
}

export async function logoutAction(): Promise<void> {
  try {
    await serverFetch("/auth/logout/", { withAuth: true });
  } catch {
    // Always clear cookies client-side regardless of API outcome.
  } finally {
    await clearAuthCookies();
  }
}
