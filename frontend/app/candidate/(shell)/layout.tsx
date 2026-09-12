import AppLayout from "@/components/layouts/AppLayout";

// Shared shell (sidebar + top bar) for every candidate page that isn't a
// full-screen experience — dashboard, practice, history, profile,
// target-roles. The live interview page (app/candidate/interview/) sits
// outside this route group deliberately, so it keeps its own distraction-free
// full-screen layout instead of inheriting this sidebar.
export default function CandidateShellLayout({ children }: { children: React.ReactNode }) {
  return <AppLayout>{children}</AppLayout>;
}
