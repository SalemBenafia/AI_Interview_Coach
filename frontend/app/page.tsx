import Link from "next/link";
import {
  Mic, ArrowRight, Sparkles, Gauge, Brain, FileBarChart,
  Sliders, Radio, MessageSquareText, ClipboardCheck,
  TrendingUp, ShieldCheck,
} from "lucide-react";
import { VoiceOrbCanvas } from "@/components/marketing/VoiceOrbCanvas";
import { AmbientParticles } from "@/components/marketing/AmbientParticles";

// ─── Data ─────────────────────────────────────────────────────────────────────

const FEATURES = [
  {
    icon: Radio,
    title: "Real, live voice — not a chatbot",
    description:
      "Speak naturally over WebRTC and hear the interviewer respond in under two seconds. Interrupt, hesitate, restart — it follows along like a real call.",
  },
  {
    icon: Brain,
    title: "Adapts to how you answer",
    description:
      "A strong answer gets pushed harder; a vague one gets a pointed follow-up. The difficulty moves with you, not on a fixed script.",
  },
  {
    icon: ClipboardCheck,
    title: "Scored on STAR, not vibes",
    description:
      "Every answer is checked for Situation, Task, Action, and Result — plus relevance, clarity, and confidence signals from how you actually spoke.",
  },
  {
    icon: FileBarChart,
    title: "A real report, not a grade",
    description:
      "Strengths, specific weak spots, rewritten versions of your weaker answers, and exactly what to practice next — downloadable as a PDF.",
  },
  {
    icon: Sliders,
    title: "Built for your actual role",
    description:
      "Frontend, backend, data, support, sales — behavioral, technical, mixed, or a straight HR screening. Pick what you're walking into.",
  },
  {
    icon: TrendingUp,
    title: "Improvement you can see",
    description:
      "Every session adds a point to your trend line. Watch communication, technical depth, and confidence move over weeks, not guesses.",
  },
];

const STEPS = [
  {
    step: "01",
    title: "Pick the interview",
    description: "Choose a role, a difficulty, and a mode — behavioral, technical, mixed, or HR screening.",
  },
  {
    step: "02",
    title: "Talk it through, live",
    description: "Allow your mic, and the AI greets you and asks its first question — out loud, in real time.",
  },
  {
    step: "03",
    title: "Get pushed where it matters",
    description: "Weak answers get follow-ups. Strong ones get harder. It behaves like a recruiter, not a quiz.",
  },
  {
    step: "04",
    title: "Read the breakdown",
    description: "A scored report lands right after — what worked, what didn't, and what to do before the real thing.",
  },
];

const STATS = [
  { value: "<2s", label: "AI response time" },
  { value: "$0", label: "LLM cost (free tier)" },
  { value: "24/7", label: "Practice availability" },
];

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground overflow-x-hidden">
      <SiteHeader />
      <Hero />
      <LogoStrip />
      <Features />
      <HowItWorks />
      <ModesShowcase />
      <FinalCta />
      <SiteFooter />
    </div>
  );
}

// ─── Header ───────────────────────────────────────────────────────────────────

function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-white/5 bg-background/70 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center shadow-neon-sm">
            <Mic className="w-4 h-4 text-primary-foreground" />
          </div>
          <span className="font-display font-semibold text-foreground">
            Interview<span className="text-primary">Coach</span>
          </span>
        </Link>
        <nav className="hidden md:flex items-center gap-8 text-sm text-muted-foreground">
          <a href="#features" className="hover:text-foreground transition-colors">Features</a>
          <a href="#how-it-works" className="hover:text-foreground transition-colors">How it works</a>
          <a href="#modes" className="hover:text-foreground transition-colors">Interview modes</a>
        </nav>
        <div className="flex items-center gap-3">
          <Link href="/login" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
            Sign in
          </Link>
          <Link
            href="/register"
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium px-4 py-2 hover:shadow-neon-sm hover:brightness-110 transition-all"
          >
            Start practicing
          </Link>
        </div>
      </div>
    </header>
  );
}

// ─── Hero ─────────────────────────────────────────────────────────────────────

function Hero() {
  return (
    <section className="relative pt-20 pb-28 px-6 circuit-grid">
      <AmbientParticles />
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 60% 50% at 50% 0%, hsl(156 100% 50% / 0.12), transparent 60%)",
        }}
        aria-hidden="true"
      />

      <div className="relative max-w-7xl mx-auto grid lg:grid-cols-2 gap-16 items-center">
        <div className="space-y-8">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 border border-primary/20">
            <span className="live-indicator" />
            <span className="text-xs text-primary font-medium tracking-wide">
              Live voice AI · real models, zero LLM hosting cost
            </span>
          </div>

          <h1 className="font-display font-bold text-5xl sm:text-6xl leading-[1.05] text-foreground">
            Practice the interview
            <br />
            <span className="gradient-text glow-text">out loud,</span>
            <br />
            before it counts.
          </h1>

          <p className="text-lg text-muted-foreground max-w-md leading-relaxed">
            A live, spoken mock interview with an AI recruiter over WebRTC — it listens, follows up,
            adapts the difficulty, and scores you like a real hiring conversation would.
          </p>

          {/* Voice/text hybrid CTA bar — the brief's "big input bar" adapted as a hybrid mic + text entry */}
          <div className="max-w-md">
            <Link
              href="/register"
              className="group flex items-center gap-3 rounded-xl bg-card border border-white/10 hover:border-primary/40 px-4 py-3.5 transition-all glow-border"
            >
              <span className="relative flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-primary/15">
                <span className="absolute inline-flex h-full w-full rounded-full bg-primary/20 animate-ping" />
                <Mic className="relative w-4 h-4 text-primary" />
              </span>
              <span className="flex-1 text-sm text-muted-foreground group-hover:text-foreground transition-colors">
                "Tell me about a time you faced a tight deadline…"
              </span>
              <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-0.5 transition-all flex-shrink-0" />
            </Link>
            <p className="text-xs text-muted-foreground/70 mt-2 pl-1">
              No credit card. Practice your first interview in under two minutes.
            </p>
          </div>

          <div className="grid grid-cols-3 gap-6 pt-4 max-w-md">
            {STATS.map((stat) => (
              <div key={stat.label}>
                <div className="text-2xl font-display font-bold text-primary glow-text-sm">{stat.value}</div>
                <div className="text-xs text-muted-foreground mt-0.5">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: signature voice-orb + floating code window */}
        <div className="relative h-[420px] lg:h-[520px]">
          <VoiceOrbCanvas className="absolute inset-0 w-full h-full" />

          <div className="absolute top-2 right-0 w-64 rounded-lg border border-white/10 bg-card/90 backdrop-blur-md shadow-dropdown overflow-hidden hidden sm:block">
            <div className="flex items-center gap-1.5 px-3 py-2 border-b border-white/5 bg-white/[0.02]">
              <span className="w-2 h-2 rounded-full bg-error/70" />
              <span className="w-2 h-2 rounded-full bg-warning/70" />
              <span className="w-2 h-2 rounded-full bg-success/70" />
              <span className="ml-2 text-2xs text-muted-foreground font-mono-coach">router_agent.py</span>
            </div>
            <pre className="px-3 py-2.5 text-2xs leading-relaxed font-mono-coach overflow-hidden">
              <code>
                <span className="text-muted-foreground">{"{"}</span>{"\n"}
                {"  "}<span className="text-accent">"action"</span>:{" "}
                <span className="text-primary">"increase_difficulty"</span>,{"\n"}
                {"  "}<span className="text-accent">"reason"</span>:{" "}
                <span className="text-foreground/80">"strong answer,"</span>{"\n"}
                <span className="text-muted-foreground">{"}"}</span>
              </code>
            </pre>
          </div>

          <div className="absolute bottom-4 left-0 flex items-center gap-2 px-3 py-2 rounded-lg border border-white/10 bg-card/90 backdrop-blur-md shadow-dropdown">
            <Gauge className="w-3.5 h-3.5 text-accent" />
            <span className="text-2xs text-muted-foreground">Latency</span>
            <span className="text-2xs font-mono-coach text-primary font-semibold">840ms</span>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Logo strip (real tech stack badges — not fake client logos) ───────────

function LogoStrip() {
  const stack = ["LangGraph", "Groq", "LiveKit", "Whisper", "Piper"];
  return (
    <section className="border-y border-white/5 bg-white/[0.015] py-6">
      <div className="max-w-7xl mx-auto px-6 flex flex-wrap items-center justify-center gap-x-10 gap-y-3">
        <span className="text-2xs uppercase tracking-wider text-muted-foreground/60 mr-2">
          Built on real, open AI infrastructure
        </span>
        {stack.map((name) => (
          <span key={name} className="text-sm font-mono-coach text-muted-foreground/70">
            {name}
          </span>
        ))}
      </div>
    </section>
  );
}

// ─── Features ─────────────────────────────────────────────────────────────────

function Features() {
  return (
    <section id="features" className="py-28 px-6">
      <div className="max-w-7xl mx-auto">
        <div className="max-w-2xl mb-16">
          <span className="text-xs font-semibold tracking-wider text-primary uppercase">Why it works</span>
          <h2 className="font-display font-bold text-3xl sm:text-4xl text-foreground mt-3">
            It's not graded by a script. It's graded like a person would.
          </h2>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((feature) => (
            <div
              key={feature.title}
              className="group rounded-xl border border-white/8 bg-card/60 p-6 hover:border-primary/25 hover:bg-card transition-all"
            >
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-4 group-hover:shadow-neon-sm transition-shadow">
                <feature.icon className="w-5 h-5 text-primary" />
              </div>
              <h3 className="font-display font-semibold text-foreground text-base mb-2">{feature.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── How it works ─────────────────────────────────────────────────────────────

function HowItWorks() {
  return (
    <section id="how-it-works" className="py-28 px-6 bg-white/[0.015] border-y border-white/5">
      <div className="max-w-7xl mx-auto">
        <div className="max-w-2xl mb-16">
          <span className="text-xs font-semibold tracking-wider text-primary uppercase">The flow</span>
          <h2 className="font-display font-bold text-3xl sm:text-4xl text-foreground mt-3">
            From "start" to a finished report in one sitting.
          </h2>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-px bg-white/5 rounded-xl overflow-hidden">
          {STEPS.map((item) => (
            <div key={item.step} className="bg-background p-6 relative">
              <span className="font-mono-coach text-3xl font-bold text-primary/30">{item.step}</span>
              <h3 className="font-display font-semibold text-foreground mt-4 mb-2">{item.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{item.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Interview modes ──────────────────────────────────────────────────────────

function ModesShowcase() {
  const modes = [
    { icon: MessageSquareText, name: "Behavioral", detail: "STAR-method storytelling questions" },
    { icon: Brain, name: "Technical", detail: "Role-specific depth questions" },
    { icon: Sparkles, name: "Mixed", detail: "A blend of both, paced naturally" },
    { icon: ShieldCheck, name: "Mock HR Screening", detail: "A first-round recruiter call" },
  ];
  return (
    <section id="modes" className="py-28 px-6">
      <div className="max-w-7xl mx-auto">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          <div>
            <span className="text-xs font-semibold tracking-wider text-primary uppercase">Interview modes</span>
            <h2 className="font-display font-bold text-3xl sm:text-4xl text-foreground mt-3 mb-5">
              Whatever interview is actually coming up.
            </h2>
            <p className="text-muted-foreground leading-relaxed max-w-md">
              Junior, mid-level, or senior difficulty, in English, French, or Arabic, for frontend,
              backend, data, support, or sales roles — set it once in Practice and the AI carries the
              persona for the whole session.
            </p>
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            {modes.map((mode) => (
              <div
                key={mode.name}
                className="rounded-xl border border-white/8 bg-card/60 p-5 hover:border-accent/30 transition-colors"
              >
                <mode.icon className="w-5 h-5 text-accent mb-3" />
                <h3 className="font-display font-semibold text-foreground text-sm">{mode.name}</h3>
                <p className="text-xs text-muted-foreground mt-1">{mode.detail}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Final CTA ────────────────────────────────────────────────────────────────

function FinalCta() {
  return (
    <section className="py-28 px-6 relative overflow-hidden">
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: "radial-gradient(ellipse 50% 60% at 50% 50%, hsl(156 100% 50% / 0.1), transparent 65%)",
        }}
        aria-hidden="true"
      />
      <div className="relative max-w-3xl mx-auto text-center space-y-6">
        <h2 className="font-display font-bold text-3xl sm:text-4xl text-foreground">
          Your next interview shouldn't be the first time you say it out loud.
        </h2>
        <p className="text-muted-foreground">Run your first practice interview free — it takes about ten minutes.</p>
        <Link
          href="/register"
          className="inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground font-medium px-7 py-3.5 hover:shadow-neon hover:brightness-110 transition-all"
        >
          Start your first interview
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </section>
  );
}

// ─── Footer ───────────────────────────────────────────────────────────────────

function SiteFooter() {
  return (
    <footer className="border-t border-white/5 py-10 px-6">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 rounded-md bg-primary flex items-center justify-center">
            <Mic className="w-3 h-3 text-primary-foreground" />
          </div>
          <span className="font-display font-semibold text-sm text-foreground">
            Interview<span className="text-primary">Coach</span>
          </span>
        </div>
        <p className="text-xs text-muted-foreground/60">© 2026 InterviewCoach. Practice makes ready.</p>
      </div>
    </footer>
  );
}
