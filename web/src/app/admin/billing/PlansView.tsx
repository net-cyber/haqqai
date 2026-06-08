"use client";

import "@/app/admin/billing/billing.css";

interface PlansViewProps {
  hasSubscription?: boolean;
  hasLicense?: boolean;
  onCheckout: () => void;
  hideFeatures?: boolean;
}

export default function PlansView(_props: PlansViewProps) {
  return null;
}
