import Link from "next/link";
import { MicOff } from "lucide-react";
import { Button } from "@/components/ui";

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-6 circuit-grid">
      <div className="text-center max-w-sm space-y-4">
        <div className="inline-flex p-4 rounded-full bg-primary/10 glow-border">
          <MicOff className="w-7 h-7 text-primary" />
        </div>
        <div>
          <h1 className="font-display font-bold text-3xl text-foreground glow-text-sm">404</h1>
          <p className="text-sm text-muted-foreground mt-2">
            This page didn't make the cut. Let's get you back to practicing.
          </p>
        </div>
        <Link href="/candidate/dashboard">
          <Button>Back to dashboard</Button>
        </Link>
      </div>
    </div>
  );
}
