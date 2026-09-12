"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { Save, KeyRound } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { useApiMutation } from "@/hooks/use-api";
import { Card, CardContent, CardHeader, CardTitle, Input, Select, Toggle, Button } from "@/components/ui";
import { useToast } from "@/store/use-ui-store";
import apiClient from "@/lib/api/client";

interface ProfileFormValues {
  firstName: string;
  lastName: string;
  headline: string;
  preferredLanguage: string;
}

interface PasswordFormValues {
  currentPassword: string;
  newPassword: string;
}

const LANGUAGE_OPTIONS = [
  { value: "en", label: "English" },
  { value: "fr", label: "French" },
  { value: "ar", label: "Arabic" },
];

export default function ProfilePage() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [notifyReportReady, setNotifyReportReady] = useState(true);
  const [notifyReminders, setNotifyReminders] = useState(true);

  const profileForm = useForm<ProfileFormValues>({
    defaultValues: {
      firstName: user?.firstName ?? "",
      lastName: user?.lastName ?? "",
      headline: user?.headline ?? "",
      preferredLanguage: user?.preferredLanguage ?? "en",
    },
  });

  const passwordForm = useForm<PasswordFormValues>({
    defaultValues: { currentPassword: "", newPassword: "" },
  });

  const updateProfile = useApiMutation<{ success: boolean }, Record<string, string>>({
    url: "/users/me/",
    method: "patch",
    onSuccess: () => toast.success("Profile updated"),
    onError: () => toast.error("Couldn't update profile"),
  });

  const changePassword = useApiMutation<{ success: boolean }, Record<string, string>>({
    url: "/users/me/change-password/",
    method: "post",
    onSuccess: () => {
      toast.success("Password changed");
      passwordForm.reset();
    },
    onError: () => toast.error("Current password is incorrect"),
  });

  const onSaveProfile = (values: ProfileFormValues) => {
    // Backend Pydantic schemas (ProfileUpdate) expect snake_case field names.
    updateProfile.mutate({
      first_name: values.firstName,
      last_name: values.lastName,
      headline: values.headline,
      preferred_language: values.preferredLanguage,
    });
  };

  const onChangePassword = (values: PasswordFormValues) => {
    changePassword.mutate({
      current_password: values.currentPassword,
      new_password: values.newPassword,
    });
  };

  const updateNotificationPrefs = async (key: "email_report_ready" | "email_reminders", value: boolean) => {
    try {
      await apiClient.patch("/users/me/", {
        notification_prefs: { email_report_ready: notifyReportReady, email_reminders: notifyReminders, [key]: value },
      });
    } catch {
      toast.error("Couldn't update notification preferences");
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-display font-bold text-foreground">Profile</h1>
        <p className="text-sm text-muted-foreground mt-1">Manage your account and preferences.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Personal information</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={profileForm.handleSubmit(onSaveProfile)} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <Input label="First name" {...profileForm.register("firstName")} />
              <Input label="Last name" {...profileForm.register("lastName")} />
            </div>
            <Input label="Headline" placeholder="e.g. Junior Frontend Developer" {...profileForm.register("headline")} />
            <Select label="Preferred language" options={LANGUAGE_OPTIONS} {...profileForm.register("preferredLanguage")} />
            <div className="flex justify-end">
              <Button type="submit" loading={updateProfile.isPending} leftIcon={<Save className="w-4 h-4" />}>
                Save changes
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Change password</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={passwordForm.handleSubmit(onChangePassword)} className="space-y-4">
            <Input type="password" label="Current password" {...passwordForm.register("currentPassword")} />
            <Input type="password" label="New password" {...passwordForm.register("newPassword")} />
            <div className="flex justify-end">
              <Button type="submit" loading={changePassword.isPending} leftIcon={<KeyRound className="w-4 h-4" />}>
                Update password
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Notifications</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-foreground">Report ready emails</p>
              <p className="text-xs text-muted-foreground">Get notified when your feedback report is generated.</p>
            </div>
            <Toggle
              checked={notifyReportReady}
              onChange={(v) => {
                setNotifyReportReady(v);
                updateNotificationPrefs("email_report_ready", v);
              }}
            />
          </div>
          <div className="h-px bg-border" />
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-foreground">Practice reminders</p>
              <p className="text-xs text-muted-foreground">Occasional nudges to keep practicing.</p>
            </div>
            <Toggle
              checked={notifyReminders}
              onChange={(v) => {
                setNotifyReminders(v);
                updateNotificationPrefs("email_reminders", v);
              }}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
