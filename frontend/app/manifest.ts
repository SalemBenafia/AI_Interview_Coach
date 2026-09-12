import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "InterviewCoach — AI Voice Interview Simulator",
    short_name: "InterviewCoach",
    description: "Practice real, live spoken interviews with an AI recruiter over WebRTC.",
    start_url: "/",
    display: "standalone",
    background_color: "#070a08",
    theme_color: "#070a08",
    icons: [{ src: "/favicon.svg", sizes: "any", type: "image/svg+xml" }],
  };
}
