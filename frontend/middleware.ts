/**
 * middleware.ts
 * ==============
 * Next.js Edge Middleware — route protection via HttpOnly JWT cookie.
 * Decodes JWT payload (no signature verification — FastAPI handles that).
 */

import { NextRequest, NextResponse } from "next/server";

const ACCESS_COOKIE = "access_token";
const REFRESH_COOKIE = "refresh_token";

const PUBLIC_ROUTES = ["/login", "/register", "/forgot-password"];
const ADMIN_ROUTES = ["/admin"];
const CANDIDATE_ROUTES = ["/candidate"];

interface JwtPayload {
  principal_type?: "admin" | "candidate";
  principal_id?: string;
  exp?: number;
}

function decodeJwt(token: string): JwtPayload | null {
  try {
    const [, b64] = token.split(".");
    const padded = b64.replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(padded)) as JwtPayload;
  } catch {
    return null;
  }
}

function isExpired(payload: JwtPayload): boolean {
  if (!payload.exp) return true;
  return Date.now() / 1000 > payload.exp - 10;
}

async function silentRefresh(
  refreshToken: string
): Promise<{ newAccess: string; newRefresh: string } | null> {
  try {
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

    const res = await fetch(`${apiBase}/auth/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Cookie: `${REFRESH_COOKIE}=${refreshToken}` },
      body: JSON.stringify({}),
    });

    if (!res.ok) return null;

    const setCookies = res.headers.getSetCookie?.() || [];
    let newAccess = "";
    let newRefresh = "";

    for (const cookieStr of setCookies) {
      const [nameValue] = cookieStr.split(";");
      const eqIdx = nameValue.indexOf("=");
      const name = nameValue.slice(0, eqIdx).trim();
      const value = nameValue.slice(eqIdx + 1).trim();
      if (name === ACCESS_COOKIE) newAccess = value;
      if (name === REFRESH_COOKIE) newRefresh = value;
    }

    return newAccess ? { newAccess, newRefresh } : null;
  } catch {
    return null;
  }
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (pathname.startsWith("/_next") || pathname.startsWith("/api") || pathname.includes(".")) {
    return NextResponse.next();
  }

  const isPublic = PUBLIC_ROUTES.some((r) => pathname === r || pathname.startsWith(`${r}/`));

  const accessToken = request.cookies.get(ACCESS_COOKIE)?.value;
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;

  if (!accessToken && !refreshToken) {
    if (isPublic || pathname === "/") return NextResponse.next();
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  let payload: JwtPayload | null = accessToken ? decodeJwt(accessToken) : null;
  let response = NextResponse.next();

  if ((!payload || isExpired(payload)) && refreshToken) {
    const refreshed = await silentRefresh(refreshToken);
    if (refreshed) {
      payload = decodeJwt(refreshed.newAccess);
      response = NextResponse.next();
      const isProduction = process.env.NODE_ENV === "production";

      response.cookies.set(ACCESS_COOKIE, refreshed.newAccess, {
        httpOnly: true,
        secure: isProduction,
        sameSite: "lax",
        path: "/",
        maxAge: 60 * 15,
      });
      if (refreshed.newRefresh) {
        response.cookies.set(REFRESH_COOKIE, refreshed.newRefresh, {
          httpOnly: true,
          secure: isProduction,
          sameSite: "lax",
          path: "/",
          maxAge: 60 * 60 * 24 * 7,
        });
      }
    } else if (!isPublic && pathname !== "/") {
      const res = NextResponse.redirect(new URL("/login?session=expired", request.url));
      res.cookies.delete(ACCESS_COOKIE);
      res.cookies.delete(REFRESH_COOKIE);
      return res;
    }
  }

  if (payload && !isExpired(payload)) {
    if (isPublic) {
      const dest = payload.principal_type === "admin" ? "/admin/dashboard" : "/candidate/dashboard";
      return NextResponse.redirect(new URL(dest, request.url));
    }

    if (ADMIN_ROUTES.some((r) => pathname.startsWith(r))) {
      if (payload.principal_type !== "admin") {
        return NextResponse.redirect(new URL("/candidate/dashboard", request.url));
      }
    }

    if (CANDIDATE_ROUTES.some((r) => pathname.startsWith(r))) {
      if (payload.principal_type !== "candidate") {
        return NextResponse.redirect(new URL("/admin/dashboard", request.url));
      }
    }

    return response;
  }

  if (!isPublic && pathname !== "/") {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    const res = NextResponse.redirect(loginUrl);
    res.cookies.delete(ACCESS_COOKIE);
    res.cookies.delete(REFRESH_COOKIE);
    return res;
  }

  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
