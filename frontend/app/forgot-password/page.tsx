"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Mic, ArrowRight, Loader2, CheckCircle2 } from "lucide-react";
import Link from "next/link";
import { forgotPasswordAction } from "@/app/actions/auth.actions";
import { forgotPasswordSchema, type ForgotPasswordFormValues } from "@/lib/auth/schemas";

export default function ForgotPasswordPage() {
  const [submitted, setSubmitted] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const form = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: "" },
  });

  const onSubmit = async (values: ForgotPasswordFormValues) => {
    setIsLoading(true);
    await forgotPasswordAction(values.email);
    setIsLoading(false);
    setSubmitted(true);
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-6 circuit-grid">
      <div className="w-full max-w-md space-y-8">
        <Link href="/" className="flex items-center gap-3 mb-2 justify-center">
          <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center shadow-neon-sm">
            <Mic className="w-4.5 h-4.5 text-primary-foreground" />
          </div>
          <span className="text-foreground text-lg font-display font-semibold">
            Interview<span className="text-primary">Coach</span>
          </span>
        </Link>

        {submitted ? (
          <div className="rounded-xl border border-border bg-card p-8 text-center space-y-3">
            <div className="inline-flex p-3 rounded-full bg-success/10">
              <CheckCircle2 className="w-6 h-6 text-success" />
            </div>
            <h1 className="font-display font-semibold text-foreground">Check your email</h1>
            <p className="text-sm text-muted-foreground">
              If an account exists for that address, we've sent a link to reset your password.
            </p>
            <Link href="/login" className="inline-block text-sm text-primary hover:text-primary/80 transition-colors">
              Back to sign in
            </Link>
          </div>
        ) : (
          <>
            <div className="space-y-2 text-center">
              <h1 className="text-2xl font-display font-bold text-foreground">Reset your password</h1>
              <p className="text-muted-foreground text-sm">
                Enter your email and we'll send you a link to reset it.
              </p>
            </div>

            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 rounded-xl border border-border bg-card p-6">
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">Email address</label>
                <input
                  type="email"
                  autoComplete="email"
                  placeholder="you@example.com"
                  {...form.register("email")}
                  className="w-full px-3.5 py-2.5 rounded-lg border border-input bg-background text-foreground text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring transition-colors"
                />
                {form.formState.errors.email && (
                  <p className="text-xs text-error">{form.formState.errors.email.message}</p>
                )}
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:shadow-neon-sm hover:brightness-110 disabled:opacity-50 transition-all"
              >
                {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Send reset link <ArrowRight className="w-4 h-4" /></>}
              </button>
            </form>

            <p className="text-center text-sm text-muted-foreground">
              <Link href="/login" className="text-primary hover:text-primary/80 font-medium transition-colors">
                Back to sign in
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
