/**
 * store/use-ui-store.ts
 * ======================
 * Global UI state: sidebar, toasts, theme. Kept separate from auth/interview
 * stores so each concern can be reasoned about independently.
 */
import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";

export type ToastVariant = "success" | "error" | "warning" | "info";

export interface Toast {
  id: string;
  title: string;
  description?: string;
  variant: ToastVariant;
  duration?: number;
}

interface UIState {
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (v: boolean) => void;
  toggleSidebar: () => void;

  toasts: Toast[];
  addToast: (toast: Omit<Toast, "id">) => void;
  removeToast: (id: string) => void;
  clearToasts: () => void;
}

export const useUIStore = create<UIState>()(
  devtools(
    persist(
      (set) => ({
        sidebarCollapsed: false,
        setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }, false, "ui/setSidebarCollapsed"),
        toggleSidebar: () =>
          set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed }), false, "ui/toggleSidebar"),

        toasts: [],
        addToast: (toast) =>
          set(
            (s) => ({
              toasts: [...s.toasts, { ...toast, id: `${Date.now()}-${Math.random()}` }].slice(-5),
            }),
            false,
            "ui/addToast"
          ),
        removeToast: (id) =>
          set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }), false, "ui/removeToast"),
        clearToasts: () => set({ toasts: [] }, false, "ui/clearToasts"),
      }),
      {
        name: "interview-coach-ui",
        partialize: (s) => ({ sidebarCollapsed: s.sidebarCollapsed }),
      }
    ),
    { name: "InterviewCoach/UI" }
  )
);

export function useToast() {
  const { addToast, removeToast, toasts } = useUIStore();

  const toast = {
    success: (title: string, description?: string) =>
      addToast({ title, description, variant: "success", duration: 4000 }),
    error: (title: string, description?: string) =>
      addToast({ title, description, variant: "error", duration: 6000 }),
    warning: (title: string, description?: string) =>
      addToast({ title, description, variant: "warning", duration: 5000 }),
    info: (title: string, description?: string) =>
      addToast({ title, description, variant: "info", duration: 4000 }),
  };

  return { toast, toasts, removeToast };
}
