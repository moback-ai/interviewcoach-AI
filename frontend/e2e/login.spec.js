import { test, expect } from '@playwright/test';

test('login page renders email and password fields', async ({ page }) => {
  await page.goto('/login');
  await expect(page.locator('#auth-login-identifier')).toBeVisible();
  await expect(page.locator('#auth-login-password')).toBeVisible();
  await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible();
});

test('forgot password page loads', async ({ page }) => {
  await page.goto('/forgot-password');
  await expect(page.getByRole('textbox')).toBeVisible();
  await expect(page.getByRole('button', { name: /send reset link/i })).toBeVisible();
});
