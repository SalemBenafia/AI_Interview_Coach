"use client";

/**
 * hooks/use-api.ts
 * =================
 * Generic TanStack Query wrappers for the Axios client.
 */

import {
  useQuery,
  useMutation,
  type UseQueryOptions,
  type UseMutationOptions,
  type QueryKey,
} from "@tanstack/react-query";
import apiClient from "@/lib/api/client";
import { normaliseApiError, type NormalisedApiError } from "@/lib/api/transformers";
import type { AxiosRequestConfig, AxiosResponse } from "axios";
export type ApiResponse<T> = {
  success: boolean;
  data: T;
  message: string | null;
};

interface UseApiQueryOptions<TData>
  extends Omit<UseQueryOptions<TData, NormalisedApiError>, "queryKey" | "queryFn"> {
  url: string;
  params?: Record<string, unknown>;
  axiosConfig?: AxiosRequestConfig;
}

export function useApiQuery<T>({
  url,
  params,
  axiosConfig,
  ...queryOptions
}: UseApiQueryOptions<T>) {
  return useQuery<T, NormalisedApiError>({
    queryKey: [url, params] as QueryKey,
    queryFn: async () => {
      try {
        const res: AxiosResponse<ApiResponse<T>> = await apiClient.get(
          url,
          { params, ...axiosConfig }
        );

        const result = res.data?.data;
        // TanStack Query v5 forbids undefined returns — throw so the retry
        // mechanism fires (e.g. report endpoint while Celery is still
        // generating feedback).
        if (result === undefined) {
          throw new Error(res.data?.message ?? "Response contained no data");
        }
        return result;
      } catch (err) {
        throw normaliseApiError(err);
      }
    },
    ...queryOptions,
  });
}

type HttpMethod = "post" | "put" | "patch" | "delete";

interface UseApiMutationOptions<TData, TVariables>
  extends Omit<UseMutationOptions<TData, NormalisedApiError, TVariables>, "mutationFn"> {
  url: string | ((variables: TVariables) => string);
  method?: HttpMethod;
  axiosConfig?: AxiosRequestConfig;
}

export function useApiMutation<TData, TVariables = unknown>({
  url,
  method = "post",
  axiosConfig,
  ...mutationOptions
}: UseApiMutationOptions<TData, TVariables>) {
  return useMutation<TData, NormalisedApiError, TVariables>({
    mutationFn: async (variables) => {
      const resolvedUrl = typeof url === "function" ? url(variables) : url;

      try {
        const res: AxiosResponse<ApiResponse<TData>> = await apiClient[method](
          resolvedUrl,
          method !== "delete" ? variables : undefined,
          axiosConfig
        );

        return res.data.data;
      } catch (err) {
        throw normaliseApiError(err);
      }
    },
    ...mutationOptions,
  });
}

// ─── Paginated query ──────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  success: boolean;
  data: T[];
  meta: {
    page: number;
    limit: number;
    total: number;
    total_pages: number;
    has_next: boolean;
    has_prev: boolean;
  };
}

export interface SuccessResponse<T> {
  success: boolean;
  data: T;
  message?: string | null;
}

export function useApiPaginated<T>({
  url,
  params,
  axiosConfig,
  ...queryOptions
}: UseApiQueryOptions<PaginatedResponse<T>>) {
  return useQuery<PaginatedResponse<T>, NormalisedApiError>({
    queryKey: [url, params] as QueryKey,
    queryFn: async () => {
      try {
        const res: AxiosResponse<PaginatedResponse<T>> = await apiClient.get(
          url,
          { params, ...axiosConfig }
        );
        return res.data;
      } catch (err) {
        throw normaliseApiError(err);
      }
    },
    ...queryOptions,
  });
}
