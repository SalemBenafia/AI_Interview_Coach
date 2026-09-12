import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// ─── Status → badge variant mappings ───────────────────────────────────────

export type StatusVariant = "success" | "warning" | "error" | "info" | "neutral";

export const sessionStatusVariant: Record<string, StatusVariant> = {
  scheduled: "neutral",
  connecting: "info",
  active: "success",
  paused: "warning",
  completed: "success",
  abandoned: "neutral",
  failed: "error",
};

export const difficultyVariant: Record<string, StatusVariant> = {
  junior: "info",
  mid: "success",
  senior: "warning",
};

export function getStatusVariantClasses(variant: StatusVariant): string {
  const map: Record<StatusVariant, string> = {
    success: "text-success bg-success-muted border-success/20",
    warning: "text-warning bg-warning-muted border-warning/20",
    error: "text-error bg-error-muted border-error/20",
    info: "text-info bg-info/10 border-info/20",
    neutral: "text-muted-foreground bg-muted border-border",
  };
  return map[variant];
}

// A feedback report is generated both when a session finishes normally and
// when it's abandoned/ended early — only these two statuses have a report to show.
export function hasSessionReport(status: string): boolean {
  return status === "completed" || status === "abandoned";
}

export function capitalize(value: string): string {
  if (!value) return value;
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

// ─── Debounce ───────────────────────────────────────────────────────────────

export function debounce<T extends (...args: never[]) => void>(fn: T, delayMs: number) {
  let timer: ReturnType<typeof setTimeout> | null = null;
  return (...args: Parameters<T>) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delayMs);
  };
}

// ─── Misc ─────────────────────────────────────────────────────────────────

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export function initials(firstName?: string, lastName?: string): string {
  return `${firstName?.[0] ?? ""}${lastName?.[0] ?? ""}`.toUpperCase();
}
