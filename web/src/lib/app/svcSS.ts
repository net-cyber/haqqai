import type { Metadata } from "next";
import { fetchEnterpriseSettingsSS } from "@/lib/settings/svcSS";
import { DEFAULT_APP_NAME } from "@/lib/constants";

/** Server-side twin of useSettings().appName for server components. */
export async function fetchAppName(): Promise<string> {
  const enterprise = await fetchEnterpriseSettingsSS();
  return enterprise?.application_name?.trim() || DEFAULT_APP_NAME;
}

export async function generateFaviconMetadata(): Promise<Metadata["icons"]> {
  const enterprise = await fetchEnterpriseSettingsSS();
  return {
    icon: enterprise?.use_custom_logo
      ? "/api/enterprise-settings/logo"
      : "/onyx.ico",
  };
}

export async function generateAdminTitleMetadata(): Promise<Metadata["title"]> {
  return `Admin — ${await fetchAppName()}`;
}
