"use client";

import { SettingsLayouts } from "@opal/layouts";
import { SvgWallet } from "@opal/icons";
import { MessageCard } from "@opal/components";

export default function BillingPage() {
  return (
    <SettingsLayouts.Root>
      <SettingsLayouts.Header
        icon={SvgWallet}
        title="Plans & Billing"
        divider
      />
      <SettingsLayouts.Body>
        <MessageCard
          variant="info"
          title="Billing is currently unavailable"
          description="Billing management is temporarily unavailable. Please contact support if you need assistance."
        />
      </SettingsLayouts.Body>
    </SettingsLayouts.Root>
  );
}
