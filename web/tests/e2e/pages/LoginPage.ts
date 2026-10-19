/**
 * Page Object Model for the login page (/auth/login).
 *
 * Covers the branding text above the login form: the welcome heading and the
 * subtitle under it.
 */

import { type Page, type Locator, expect } from "@playwright/test";

export class LoginPage {
  readonly page: Page;
  readonly emailInput: Locator;

  constructor(page: Page) {
    this.page = page;
    this.emailInput = page.getByTestId("email");
  }

  /** Open the login page and wait for the login form. */
  async goto(): Promise<void> {
    await this.page.goto("/auth/login");
    await expect(this.emailInput).toBeVisible();
  }

  /** Assert that the page shows the given welcome heading and subtitle. */
  async expectBranding(heading: string, subtitle: string): Promise<void> {
    await expect(this.page.getByText(heading, { exact: true })).toBeVisible();
    await expect(this.page.getByText(subtitle, { exact: true })).toBeVisible();
  }
}
