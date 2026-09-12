"use client";

import { useState } from "react";
import { Shield, Plus, ScrollText } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useApiQuery, useApiMutation, useApiPaginated } from "@/hooks/use-api";
import { Card, CardContent, CardHeader, CardTitle, Badge, Skeleton, Button, Modal, Input, Select, Tabs, Pagination } from "@/components/ui";
import { useToast } from "@/store/use-ui-store";
import { formatTimeAgo, formatDateTime } from "@/lib/utils/format";
import { capitalize } from "@/lib/utils/utils";

interface AdminRow {
  id: string; email: string; username: string; firstName: string; lastName: string;
  role: string; isActive: boolean; mfaEnabled: boolean; lastLoginAt: string | null;
}

interface AuditLogRow {
  id: string; adminId: string | null; action: string; resourceType: string | null;
  resourceId: string | null; timestamp: string;
}

const ROLE_OPTIONS = [
  { value: "support", label: "Support" },
  { value: "flow_designer", label: "Flow Designer" },
  { value: "ai_manager", label: "AI Manager" },
  { value: "platform_admin", label: "Platform Admin" },
  { value: "super_admin", label: "Super Admin" },
];

export default function AdminSecurityPage() {
  const [tab, setTab] = useState("admins");

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-display font-bold text-foreground">Security</h1>
        <p className="text-sm text-muted-foreground mt-1">Admin accounts, roles, and the audit trail.</p>
      </div>

      <Tabs
        tabs={[
          { value: "admins", label: "Admin accounts" },
          { value: "audit", label: "Audit log" },
        ]}
        value={tab}
        onChange={setTab}
      />

      {tab === "admins" ? <AdminsTab /> : <AuditLogTab />}
    </div>
  );
}

function AdminsTab() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const { data: admins, isLoading } = useApiQuery<AdminRow[]>({ url: "/admin/security/admins/" });
  const [createOpen, setCreateOpen] = useState(false);

  return (
    <>
      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-primary" /> Admin accounts
          </CardTitle>
          <Button size="sm" leftIcon={<Plus className="w-3.5 h-3.5" />} onClick={() => setCreateOpen(true)}>
            New admin
          </Button>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-32 w-full" />
          ) : (
            <div className="divide-y divide-border">
              {(admins ?? []).map((a) => (
                <div key={a.id} className="flex items-center justify-between py-3">
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      {a.firstName} {a.lastName}
                    </p>
                    <p className="text-xs text-muted-foreground">{a.email}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="primary">{capitalize(a.role)}</Badge>
                    <Badge variant={a.isActive ? "success" : "error"}>{a.isActive ? "Active" : "Disabled"}</Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <CreateAdminModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ["/admin/security/admins/"] });
          toast.success("Admin account created");
        }}
      />
    </>
  );
}

function CreateAdminModal({ open, onClose, onSuccess }: { open: boolean; onClose: () => void; onSuccess: () => void }) {
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [role, setRole] = useState("support");

  const createMutation = useApiMutation<
    unknown,
    { email: string; username: string; password: string; first_name: string; last_name: string; role: string }
  >({
    url: "/admin/security/admins/",
    onSuccess: () => {
      onSuccess();
      onClose();
    },
  });

  return (
    <Modal open={open} onClose={onClose} title="New admin account" size="sm">
      <div className="p-6 pt-0 space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <Input label="First name" value={firstName} onChange={(e) => setFirstName(e.target.value)} />
          <Input label="Last name" value={lastName} onChange={(e) => setLastName(e.target.value)} />
        </div>
        <Input label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <Input label="Username" value={username} onChange={(e) => setUsername(e.target.value)} />
        <Input label="Temporary password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <Select label="Role" value={role} onChange={(e) => setRole(e.target.value)} options={ROLE_OPTIONS} />
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button
            loading={createMutation.isPending}
            disabled={!email || !username || !password || !firstName || !lastName}
            onClick={() =>
              createMutation.mutate({
                email,
                username,
                password,
                first_name: firstName,
                last_name: lastName,
                role,
              })
            }
          >
            Create
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function AuditLogTab() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useApiPaginated<AuditLogRow>({ url: "/admin/security/audit-logs/", params: { page, limit: 20 } });

  const logs = data?.data ?? [];
  const meta = data?.meta;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ScrollText className="w-4 h-4 text-accent" /> Audit log
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <div className="p-5">
            <Skeleton className="h-48 w-full" />
          </div>
        ) : logs.length === 0 ? (
          <p className="text-sm text-muted-foreground py-10 text-center">No audit events recorded yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground uppercase tracking-wider">
                <th className="px-5 py-3 font-medium">Action</th>
                <th className="px-5 py-3 font-medium">Resource</th>
                <th className="px-5 py-3 font-medium">When</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {logs.map((log) => (
                <tr key={log.id}>
                  <td className="px-5 py-3 font-mono-coach text-xs text-primary">{log.action}</td>
                  <td className="px-5 py-3 text-muted-foreground">
                    {log.resourceType} {log.resourceId ? `#${log.resourceId.slice(0, 8)}` : ""}
                  </td>
                  <td className="px-5 py-3 text-muted-foreground" title={formatDateTime(log.timestamp)}>
                    {formatTimeAgo(log.timestamp)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
      {meta && meta.total > 0 && (
        <Pagination page={meta.page} totalPages={meta.total_pages} total={meta.total} limit={meta.limit} onPageChange={setPage} />
      )}
    </Card>
  );
}
