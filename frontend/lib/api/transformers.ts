import type { AxiosError } from "axios";

export type PrincipalType = "candidate" | "admin";

export interface User {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  principalType: PrincipalType;
  roles: string[];
  avatarUrl?: string | null;
  resumeUrl?: string | null;
  headline?: string | null;
  preferredLanguage?: string;
  notificationPrefs?: Record<string, boolean>;
  mfaEnabled?: boolean;
}

export interface NormalisedApiError {
  message: string;
  code?: string;
  status?: number;
}

export function normaliseApiError(error: unknown): NormalisedApiError {
  const axiosError = error as AxiosError<{
    error?: { code?: string; message?: string };
    detail?: { code?: string; message?: string } | string;
  }>;

  if (!axiosError?.response) {
    return { message: "Network error. Please check your connection and try again." };
  }

  const data = axiosError.response.data;
  const status = axiosError.response.status;

  if (data?.error) {
    return { message: data.error.message ?? "Something went wrong.", code: data.error.code, status };
  }
  if (typeof data?.detail === "object" && data.detail) {
    return { message: data.detail.message ?? "Something went wrong.", code: data.detail.code, status };
  }
  if (typeof data?.detail === "string") {
    return { message: data.detail, status };
  }

  return { message: "Something went wrong. Please try again.", status };
}
