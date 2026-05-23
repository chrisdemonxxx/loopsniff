import { expect, test } from "@playwright/test";
import { loginAsAdmin } from "./helpers/login";

const NAV_LINKS = [
  "/dashboard",
  "/clients",
  "/crm",
  "/conversations",
  "/chat",
  "/tickets",
  "/accounts",
  "/finance",
  "/outreach",
  "/team",
  "/affiliates",
  "/subscriptions",
  "/alerts",
  "/deposit-config",
  "/bot",
  "/settings",
];

test.describe("Admin full UI", () => {
  test("negative login shows error", async ({ page }) => {
    await page.goto("/login");
    await page.locator('input[type="email"]').fill("bad@example.com");
    await page.locator('input[type="password"]').fill("wrongpass");
    await page.getByRole("button", { name: "Sign In" }).click();
    await expect(page.getByText("Invalid email or password").first()).toBeVisible();
  });

  test("all main nav routes are reachable", async ({ page }) => {
    await loginAsAdmin(page);
    for (const route of NAV_LINKS) {
      await page.goto(route);
      await expect(page).toHaveURL(new RegExp(route.replace("/", "\\/")));
      await expect(page.locator("main").first()).toBeVisible();
    }
  });

  test("core interactive elements are clickable", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/clients");
    const clientSearch = page.getByPlaceholder("Search clients...");
    if (await clientSearch.count()) {
      await clientSearch.fill("alice");
      await expect(clientSearch).toHaveValue("alice");
    }

    await page.goto("/tickets");
    const ticketSearch = page.getByPlaceholder("Search tickets...");
    if (await ticketSearch.count()) {
      await ticketSearch.fill("open");
      await expect(ticketSearch).toHaveValue("open");
    }

    await page.goto("/finance");
    const financeSearch = page.getByPlaceholder("Search by client or reference...");
    if (await financeSearch.count()) {
      await financeSearch.fill("ref");
      await expect(financeSearch).toHaveValue("ref");
    }
  });
});
