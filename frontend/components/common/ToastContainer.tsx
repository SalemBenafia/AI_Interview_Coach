"use client";

import { useEffect } from "react";
import { CheckCircle2, AlertCircle, AlertTriangle, Info, X } from "lucide-react";
import { useUIStore, type Toast, type ToastVariant } from "@/store/use-ui-store";
import { cn } from "@/lib/utils/utils";

const variantConfig: Record<ToastVariant, { icon: typeof CheckCircle2; classes: string }> = {
  success: { icon: CheckCircle2, classes: "border-success/30 bg-success-muted text-success" },
  error: { icon: AlertCircle, classes: "border-error/30 bg-error-muted text-error" },
  warning: { icon: AlertTriangle, classes: "border-warning/30 bg-warning-muted text-warning" },
  info: { icon: Info, classes: "border-info/30 bg-info/10 text-info" },
};

function ToastCard({ toast }: { toast: Toast }) {
  const removeToast = useUIStore((s) => s.removeToast);
  const { icon: Icon, classes } = variantConfig[toast.variant];

  useEffect(() => {
    const timer = setTimeout(() => removeToast(toast.id), toast.duration ?? 4000);
    return () => clearTimeout(timer);
  }, [toast.id, toast.duration, removeToast]);

  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-lg border px-4 py-3 shadow-dropdown backdrop-blur-md animate-slide-in-right min-w-72 max-w-sm",
        classes
      )}
      role="status"
    >
      <Icon className="w-4.5 h-4.5 flex-shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium leading-snug">{toast.title}</p>
        {toast.description && <p className="text-xs opacity-80 mt-0.5">{toast.description}</p>}
      </div>
      <button
        type="button"
        onClick={() => removeToast(toast.id)}
        className="flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity"
        aria-label="Dismiss"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

export function ToastContainer() {
  const toasts = useUIStore((s) => s.toasts);
  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2" aria-live="polite">
      {toasts.map((toast) => (
        <ToastCard key={toast.id} toast={toast} />
      ))}
    </div>
  );
}
