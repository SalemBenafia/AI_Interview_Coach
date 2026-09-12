"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff, Mic, ArrowRight, Loader2 } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/hooks/use-auth";
import { loginSchema, type LoginFormValues } from "@/lib/auth/schemas";

export default function LoginPage() {
  const [showPassword, setShowPassword] = useState(false);
  const { login, isLoading, error, clearError } = useAuth();

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  // One form, one endpoint — the backend resolves candidate vs admin from
  // the credentials alone (see POST /auth/login/). There's no role switch
  // to get wrong or to leak account-type information through.
  const onSubmit = async (values: LoginFormValues) => {
    clearError();
    await login({ email: values.email, password: values.password });
  };

  return (
    <div className="min-h-screen bg-background flex">
      {/* ── Left Panel — Branding ─────────────────────────────────────── */}
      <div className="hidden lg:flex lg:w-1/2 bg-sidebar flex-col justify-between p-12 relative overflow-hidden circuit-grid">
        <div className="absolute inset-0 opacity-40" aria-hidden="true">
          <div className="absolute top-20 left-20 w-72 h-72 rounded-full bg-primary/20 blur-3xl" />
          <div className="absolute bottom-20 right-20 w-56 h-56 rounded-full bg-accent/15 blur-3xl" />
        </div>

        <div className="relative z-10 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center shadow-neon-sm">
            <Mic className="w-5 h-5 text-primary-foreground" />
          </div>
          <span className="text-sidebar-foreground text-xl font-display font-semibold">
            Interview<span className="text-primary">Coach</span>
          </span>
        </div>

        <div className="relative z-10 space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/15 border border-primary/25">
            <div className="live-indicator" />
            <span className="text-xs text-primary font-medium">Live, real-time AI interviews</span>
          </div>
          <h1 className="text-4xl font-display font-bold text-sidebar-foreground leading-tight">
            Walk in already
            <br />
            having said it
            <br />
            <span className="text-primary glow-text-sm">out loud once.</span>
          </h1>
          <p className="text-sidebar-foreground/60 text-base leading-relaxed max-w-sm">
            A live voice interview over WebRTC, scored on communication, technical depth, and the
            STAR method — not a quiz, a conversation.
          </p>

          <div className="grid grid-cols-3 gap-4 pt-4">
            {[
              { value: "<2s", label: "Response time" },
              { value: "STAR", label: "Method scoring" },
              { value: "24/7", label: "Available" },
            ].map((stat) => (
              <div key={stat.label} className="space-y-1">
                <div className="text-2xl font-display font-bold text-primary">{stat.value}</div>
                <div className="text-xs text-sidebar-foreground/50">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="relative z-10 text-sidebar-foreground/30 text-xs">
          © 2026 InterviewCoach · Practice makes ready
        </div>
      </div>

      {/* ── Right Panel — Login Form ──────────────────────────────────── */}
      <div className="flex-1 flex items-center justify-center p-6 lg:p-12">
        <div className="w-full max-w-md space-y-8">
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center shadow-neon-sm">
              <Mic className="w-4.5 h-4.5 text-primary-foreground" />
            </div>
            <span className="text-foreground text-lg font-display font-semibold">
              Interview<span className="text-primary">Coach</span>
            </span>
          </div>

          <div className="space-y-2">
            <h2 className="text-2xl font-display font-bold text-foreground">Welcome back</h2>
            <p className="text-muted-foreground text-sm">Sign in to your account</p>
          </div>

          {error && (
            <div className="px-4 py-3 rounded-lg bg-error-muted border border-error/20 text-error text-sm">
              {error}
            </div>
          )}

          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-foreground">Email address</label>
              <input
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                {...form.register("email")}
                className="w-full px-3.5 py-2.5 rounded-lg border border-input bg-background text-foreground text-sm
                  placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring
                  disabled:opacity-50 transition-colors"
              />
              {form.formState.errors.email && (
                <p className="text-xs text-error mt-1">{form.formState.errors.email.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-foreground">Password</label>
                <Link href="/forgot-password" className="text-xs text-primary hover:text-primary/80 transition-colors">
                  Forgot password?
                </Link>
              </div>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  placeholder="••••••••"
                  {...form.register("password")}
                  className="w-full px-3.5 py-2.5 pr-10 rounded-lg border border-input bg-background text-foreground text-sm
                    placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring
                    disabled:opacity-50 transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((p) => !p)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {form.formState.errors.password && (
                <p className="text-xs text-error mt-1">{form.formState.errors.password.message}</p>
              )}
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg
                bg-primary text-primary-foreground text-sm font-semibold
                hover:shadow-neon-sm hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed
                transition-all shadow-sm"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  Sign in
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <p className="text-center text-sm text-muted-foreground">
            New here?{" "}
            <Link href="/register" className="text-primary hover:text-primary/80 font-medium transition-colors">
              Create an account
            </Link>
          </p>

         
        </div>
      </div>
    </div>
  );
}
