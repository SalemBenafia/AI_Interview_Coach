import "server-only";

/**
 * lib/auth/auth.server.ts
 * ========================
 * Server-side utilities for auth Server Actions.
 * Mirrors HttpOnly cookies from FastAPI to the browser.
 * Tokens NEVER exposed to client JavaScript.
 */

import { cookies } from "next/headers";

export const API_BASE_URL =
  process.env.API_INTERNAL_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://backend:8000/api/v1";

export const ACCESS_COOKIE = "access_token";
export const REFRESH_COOKIE = "refresh_token";

export type ActionResult<T = void> =
  | { ok: true; data: T }
  | { ok: false; error: NormalisedActionError };

export interface NormalisedActionError {
  message: string;
  fieldErrors: Record<string, string>;
  code?: string;
  status?: number;
}

export interface LoginPayload {
  email: string;
  password: string;
}

interface ServerFetchOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  withAuth?: boolean;
}

export async function serverFetch<T>(
  path: string,
  { method = "POST", body, withAuth = false }: ServerFetchOptions = {}
): Promise<{ data: T; response: Response }> {
    console.log("API_BASE_URL =", API_BASE_URL);
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (withAuth) {
    const cookieStore = await cookies();
    const cookieHeader = cookieStore
      .getAll()
      .map((c) => `${c.name}=${c.value}`)
      .join("; ");

    if (cookieHeader) {
      headers["Cookie"] = cookieHeader;
    }
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    credentials: "include",
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw { response: { data, status: res.status } };
  }

  const text = await res.text();
  const data = text ? JSON.parse(text) : {};
  return { data: data as T, response: res };
}

export async function mirrorAuthCookiesFromResponse(res: Response) {
  const setCookies = res.headers.getSetCookie?.() || [];
  if (setCookies.length === 0) {
    const single = res.headers.get("set-cookie");
    if (single) setCookies.push(single);
  }

  const cookieStore = await cookies();

  for (const cookieStr of setCookies) {
    const [nameValue] = cookieStr.split(";");
    const eqIdx = nameValue.indexOf("=");
    const name = nameValue.slice(0, eqIdx).trim();
    const value = nameValue.slice(eqIdx + 1).trim();

    if (name === ACCESS_COOKIE || name === REFRESH_COOKIE) {
      const isAccess = name === ACCESS_COOKIE;
      cookieStore.set(name, value, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        path: "/",
        maxAge: isAccess ? 60 * 15 : 60 * 60 * 24 * 7,
      });
    }
  }
}

export async function clearAuthCookies(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete(ACCESS_COOKIE);
  cookieStore.delete(REFRESH_COOKIE);
}

export interface JwtPayload {
  principal_type?: "admin" | "candidate";
  principal_id?: string;
  roles?: string[];
  exp?: number;
}

export function decodeJwtPayload(token: string): JwtPayload | null {
  try {
    const [, payloadB64] = token.split(".");
    const padded = payloadB64.replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(padded)) as JwtPayload;
  } catch {
    return null;
  }
}

export function isTokenExpired(payload: JwtPayload): boolean {
  if (!payload.exp) return true;
  return Date.now() / 1000 > payload.exp - 10;
}

export function normaliseActionError(error: unknown): NormalisedActionError {
  if (!error || typeof error !== "object") {
    return { message: "Unexpected error occurred.", fieldErrors: {} };
  }

  const err = error as {
    response?: {
      data?: { error?: { code?: string; message?: string }; detail?: { code?: string; message?: string } | string };
      status?: number;
    };
  };

  if (!err.response?.data) {
    return {
      message: "Network error. Please try again.",
      fieldErrors: {},
      status: err.response?.status,
    };
  }

  const data = err.response.data;
  // FastAPI HTTPException puts detail directly: {"detail": "..." | {code, message}}
  // Our own error responses use: {"error": {code, message}}
  const detail = data.detail;
  const detailMessage =
    typeof detail === "string" ? detail : detail?.message ?? undefined;
  return {
    message: data.error?.message ?? detailMessage ?? "Something went wrong.",
    fieldErrors: {},
    code: data.error?.code ?? (typeof detail === "object" ? detail?.code : undefined),
    status: err.response?.status,
  };
}
