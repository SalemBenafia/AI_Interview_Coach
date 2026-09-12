import { format, formatDistanceToNow, parseISO } from "date-fns";

export function formatDateTime(value: string | Date | null): string {
  if (!value) return "—";
  const date = typeof value === "string" ? parseISO(value) : value;
  return format(date, "MMM d, yyyy 'at' h:mm a");
}

export function formatDate(value: string | Date | null): string {
  if (!value) return "—";
  const date = typeof value === "string" ? parseISO(value) : value;
  return format(date, "MMM d, yyyy");
}

export function formatTimeAgo(value: string | Date | null): string {
  if (!value) return "—";
  const date = typeof value === "string" ? parseISO(value) : value;
  return formatDistanceToNow(date, { addSuffix: true });
}

export function formatDuration(totalSeconds: number | null): string {
  if (totalSeconds == null) return "—";
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function formatScore(score: number | null | undefined): string {
  if (score == null) return "—";
  return Math.round(score).toString();
}

export function scoreToLabel(score: number | null | undefined): string {
  if (score == null) return "Not scored";
  if (score >= 85) return "Excellent";
  if (score >= 70) return "Strong";
  if (score >= 50) return "Developing";
  return "Needs work";
}

export function scoreToColorClass(score: number | null | undefined): string {
  if (score == null) return "text-muted-foreground";
  if (score >= 85) return "text-primary";
  if (score >= 70) return "text-accent";
  if (score >= 50) return "text-warning";
  return "text-error";
}
