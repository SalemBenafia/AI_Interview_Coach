import type { Metadata, Viewport } from "next";
import "@/styles/globals.css";
import { Providers } from "@/components/providers/providers";

export const metadata: Metadata = {
  title: {
    default: "InterviewCoach — AI Voice Interview Simulator",
    template: "%s | InterviewCoach",
  },
  description:
    "Practice real, live spoken interviews with an AI recruiter over WebRTC. Get instant scoring on communication, technical depth, and STAR-method structure.",
  keywords: ["interview practice", "AI interview coach", "mock interview", "WebRTC voice AI", "STAR method"],
};

export const viewport: Viewport = {
  themeColor: "#070a08",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className="dark">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
