"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-6">
      <div className="text-center max-w-sm space-y-4">
        <div className="inline-flex p-3 rounded-full bg-error/10">
          <AlertTriangle className="w-6 h-6 text-error" />
        </div>
        <div>
          <h1 className="font-display font-semibold text-lg text-foreground">Something went wrong</h1>
          <p className="text-sm text-muted-foreground mt-1">
            An unexpected error occurred. You can try again, or head back to your dashboard.
          </p>
        </div>
        <div className="flex items-center justify-center gap-2">
          <Button variant="outline" onClick={() => reset()}>
            Try again
          </Button>
          <Button onClick={() => (window.location.href = "/candidate/dashboard")}>Go to dashboard</Button>
        </div>
      </div>
    </div>
  );
}
