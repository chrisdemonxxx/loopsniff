import { expect, type Page } from "@playwright/test";

const ADMIN_EMAIL = process.env.ADMIN_E2E_EMAIL || "superadmin@kliqboost.store";
const ADMIN_PASSWORD = process.env.ADMIN_E2E_PASSWORD || "SuperAdmin2026!";

export async function loginAsAdmin(page: Page) {
  await page.goto("/login");
  // Use type="email" selector which is more reliable
  await page.locator('input[type="email"]').fill(ADMIN_EMAIL);
  await page.locator('input[type="password"]').fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/dashboard/);
}

export { ADMIN_EMAIL, ADMIN_PASSWORD };
