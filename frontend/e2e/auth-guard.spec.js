import { test, expect } from '@playwright/test';

test('dashboard redirects unauthenticated users to login', async ({ page }) => {
  await page.goto('/dashboard');
  await expect(page).toHaveURL(/\/login/);
  await expect(page.locator('#auth-login-identifier')).toBeVisible();
});

test('upload page redirects unauthenticated users to login', async ({ page }) => {
  await page.goto('/upload');
  await expect(page).toHaveURL(/\/login/);
});
