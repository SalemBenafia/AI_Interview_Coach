"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Mic, History, UserCircle, Bell, LogOut,
  ChevronLeft, ChevronRight, Menu, X, Users, Bot, GitBranch,
  Briefcase, BarChart3, Activity, Shield, ListTree,
} from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { useMe } from "@/hooks/use-me";
import { cn } from "@/lib/utils/utils";

// ─── Navigation ───────────────────────────────────────────────────────────────

const candidateNav = [
  { href: "/candidate/dashboard", icon: LayoutDashboard, label: "Overview" },
  { href: "/candidate/target-roles", icon: Briefcase, label: "Target Roles" },
  { href: "/candidate/practice", icon: Mic, label: "Practice" },
  { href: "/candidate/history", icon: History, label: "History" },
  { href: "/candidate/profile", icon: UserCircle, label: "Profile" },
];

const adminNav = [
  { href: "/admin/dashboard", icon: LayoutDashboard, label: "Overview" },
  { href: "/admin/users", icon: Users, label: "Candidates" },
  { href: "/admin/agents", icon: Bot, label: "Agents" },
  { href: "/admin/flows", icon: GitBranch, label: "Flows" },
  { href: "/admin/content", icon: ListTree, label: "Difficulty" },
  { href: "/admin/analytics", icon: BarChart3, label: "Analytics" },
  { href: "/admin/monitoring", icon: Activity, label: "Monitoring" },
  { href: "/admin/security", icon: Shield, label: "Security" },
];

// ─── Sidebar ──────────────────────────────────────────────────────────────────

function Sidebar({
  collapsed,
  onToggle,
  onMobileClose,
}: {
  collapsed: boolean;
  onToggle: () => void;
  onMobileClose?: () => void;
}) {
  const pathname = usePathname();
  const { user, isAdmin, logout } = useAuth();
  const nav = isAdmin ? adminNav : candidateNav;

  return (
    <aside
      className={cn(
        "flex flex-col h-full bg-sidebar border-r border-sidebar-border transition-all duration-200 ease-in-out relative",
        collapsed ? "w-16" : "w-64"
      )}
    >
      {/* Logo */}
      <div className="h-16 flex items-center px-4 border-b border-sidebar-border flex-shrink-0">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center flex-shrink-0 shadow-neon-sm">
            <Mic className="w-4 h-4 text-primary-foreground" />
          </div>
          {!collapsed && (
            <span className="font-display font-semibold text-sidebar-foreground truncate">
              Interview<span className="text-primary">Coach</span>
            </span>
          )}
        </div>
        {onMobileClose ? (
          <button
            type="button"
            onClick={onMobileClose}
            className="ml-auto p-1 text-sidebar-foreground/50 hover:text-sidebar-foreground"
            aria-label="Close menu"
          >
            <X className="w-4 h-4" />
          </button>
        ) : !collapsed ? (
          <button
            type="button"
            onClick={onToggle}
            className="ml-auto p-1 rounded-md text-sidebar-foreground/40 hover:text-sidebar-foreground hover:bg-white/5 transition-colors"
            aria-label="Collapse sidebar"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
        ) : (
          <button
            type="button"
            onClick={onToggle}
            className="absolute -right-3 top-5 w-6 h-6 bg-sidebar border border-sidebar-border rounded-full flex items-center justify-center text-sidebar-foreground/50 hover:text-sidebar-foreground transition-colors shadow-sm"
            aria-label="Expand sidebar"
          >
            <ChevronRight className="w-3 h-3" />
          </button>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 p-2 space-y-0.5 overflow-y-auto scrollbar-thin">
        {!collapsed && (
          <p className="px-3 py-1.5 text-2xs font-semibold uppercase tracking-wider text-sidebar-foreground/25">
            {isAdmin ? "AI Studio" : "Practice"}
          </p>
        )}
        {nav.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              title={collapsed ? item.label : undefined}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all group relative",
                isActive
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-sidebar-foreground/55 hover:text-sidebar-foreground hover:bg-white/5"
              )}
            >
              <item.icon
                className={cn(
                  "w-4 h-4 flex-shrink-0 transition-colors",
                  isActive ? "text-primary" : "text-sidebar-foreground/35 group-hover:text-sidebar-foreground/70"
                )}
              />
              {!collapsed && <span className="truncate flex-1">{item.label}</span>}
              {!collapsed && isActive && (
                <div className="ml-auto w-1.5 h-1.5 rounded-full bg-primary shadow-neon-sm flex-shrink-0" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* User + logout */}
      <div className="p-2 border-t border-sidebar-border space-y-0.5 flex-shrink-0">
        {!collapsed && user && (
          <div className="px-3 py-2 flex items-center gap-2.5 rounded-lg min-w-0">
            <div className="w-7 h-7 rounded-full bg-primary/15 flex items-center justify-center flex-shrink-0">
              <span className="text-xs font-semibold text-primary">
                {user.firstName?.[0]}
                {user.lastName?.[0]}
              </span>
            </div>
            <div className="min-w-0">
              <p className="text-xs font-medium text-sidebar-foreground truncate">
                {user.firstName} {user.lastName}
              </p>
              <p className="text-2xs text-sidebar-foreground/35 capitalize truncate">{user.principalType}</p>
            </div>
          </div>
        )}
        <button
          type="button"
          onClick={logout}
          title={collapsed ? "Sign out" : undefined}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-sidebar-foreground/40 hover:text-error hover:bg-error/10 transition-all"
        >
          <LogOut className="w-4 h-4 flex-shrink-0" />
          {!collapsed && <span>Sign out</span>}
        </button>
      </div>
    </aside>
  );
}

// ─── Topbar ───────────────────────────────────────────────────────────────────

function Topbar({ onMenuClick }: { onMenuClick: () => void }) {
  const pathname = usePathname();
  const { user } = useAuth();

  const segments = pathname.split("/").filter(Boolean);
  const isUuid = (s: string) => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(s);
  // Dynamic routes like /admin/flows/[flowId] end in a raw UUID -- fall back
  // to the nearest non-UUID segment (the section name) instead of showing it.
  let titleSegment = segments[segments.length - 1];
  for (let i = segments.length - 1; i >= 0; i--) {
    if (!isUuid(segments[i])) {
      titleSegment = segments[i];
      break;
    }
  }
  const pageTitle =
    titleSegment
      ?.replace(/-/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase()) || "Dashboard";

  return (
    <header className="h-16 border-b border-border bg-card/60 backdrop-blur-md flex items-center px-4 gap-4 flex-shrink-0">
      <button
        type="button"
        onClick={onMenuClick}
        className="lg:hidden p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors"
        aria-label="Open menu"
      >
        <Menu className="w-5 h-5" />
      </button>
      <div className="flex-1 min-w-0">
        <h1 className="text-base font-display font-semibold text-foreground truncate">{pageTitle}</h1>
      </div>
      <div className="flex items-center gap-1.5">
        <Link
          href="#"
          className="relative p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors"
          aria-label="Notifications"
        >
          <Bell className="w-4 h-4" />
        </Link>
        {user && (
          <div className="flex items-center gap-2 pl-2 border-l border-border ml-1">
            <div className="w-8 h-8 rounded-full bg-primary/15 flex items-center justify-center">
              <span className="text-xs font-semibold text-primary">
                {user.firstName?.[0]}
                {user.lastName?.[0]}
              </span>
            </div>
            <div className="hidden sm:block">
              <p className="text-xs font-medium text-foreground leading-tight">
                {user.firstName} {user.lastName}
              </p>
              <p className="text-2xs text-muted-foreground capitalize">{user.principalType}</p>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}

// ─── Layout ───────────────────────────────────────────────────────────────────

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useMe();

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/70 lg:hidden"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      <div
        className={cn(
          "fixed inset-y-0 left-0 z-50 lg:hidden transition-transform duration-200",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <Sidebar collapsed={false} onToggle={() => {}} onMobileClose={() => setMobileOpen(false)} />
      </div>

      <div className="hidden lg:flex relative">
        <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((p) => !p)} />
      </div>

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Topbar onMenuClick={() => setMobileOpen(true)} />
        <main className="flex-1 overflow-y-auto scrollbar-thin">
          <div className="p-4 sm:p-6 max-w-screen-2xl mx-auto">{children}</div>
        </main>
      </div>
    </div>
  );
}
