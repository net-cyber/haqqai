import { test } from "@playwright/test";
import { LoginPage } from "@tests/e2e/pages/LoginPage";

// The login page shows the default Scovra branding when no custom
// application name or login subtitle is set.

test.describe("Login page branding", () => {
  test.beforeEach(async ({ page }) => {
    await page.context().clearCookies();
  });

  test("shows the Scovra heading and subtitle", async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.expectBranding(
      "Welcome to Scovra",
      "We scout the opportunities. We cover the follow-through."
    );
  });
});
