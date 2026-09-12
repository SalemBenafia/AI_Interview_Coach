/**
 * lib/api/client.ts
 * ==================
 * Axios instance for the AI Interview Coach API.
 * HttpOnly cookie auth — withCredentials: true on all requests.
 * Silent 401 refresh via /auth/token/refresh/.
 */

import axios, {
  type AxiosInstance,
  type AxiosResponse,
  type AxiosError,
  type InternalAxiosRequestConfig,
} from "axios";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  timeout: 20_000,
  headers: { "Content-Type": "application/json" },
});

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value: unknown) => void;
  reject: (reason?: unknown) => void;
}> = [];

function processQueue(error: AxiosError | null): void {
  for (const p of failedQueue) {
    error ? p.reject(error) : p.resolve(undefined);
  }
  failedQueue = [];
}

apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };

    if (
      error.response?.status === 401 &&
      !original._retry &&
      !original.url?.includes("/auth/token/refresh/") &&
      !original.url?.includes("/auth/login/") &&
      !original.url?.includes("/auth/admin/login/")
    ) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then(() => apiClient(original));
      }

      original._retry = true;
      isRefreshing = true;

      try {
        await apiClient.post("/auth/token/refresh/", {});
        processQueue(null);
        return apiClient(original);
      } catch (refreshError) {
        processQueue(refreshError as AxiosError);
        if (typeof window !== "undefined") {
          window.location.href = "/login?session=expired";
        }
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;
