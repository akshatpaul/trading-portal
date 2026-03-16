import { test, expect } from '@playwright/test';
import { mockAllRoutes } from './mockRoutes.js';
import { mockStatusLive, mockStatusBlocked, mockHealth } from './fixtures.js';

test.describe('Header / TopBar', () => {
  test('renders PAPER mode badge', async ({ page }) => {
    await mockAllRoutes(page);
    await page.goto('/');
    // The TopBar shows a PAPER badge when mode is 'paper'
    await expect(page.getByText('PAPER').first()).toBeVisible();
  });

  test('displays capital ₹10,000', async ({ page }) => {
    await mockAllRoutes(page);
    await page.goto('/');
    // Capital is shown in the header banner area (getByRole banner is the <header>)
    // Use the header-specific capital display
    await expect(page.getByRole('banner').getByText(/10,000/)).toBeVisible();
  });

  test('shows market OPEN indicator', async ({ page }) => {
    await mockAllRoutes(page);
    await page.goto('/');
    // market_open: true → "OPEN" text with emerald color
    await expect(page.getByText('OPEN', { exact: true })).toBeVisible();
  });

  test('Emergency Stop button is present', async ({ page }) => {
    await mockAllRoutes(page);
    await page.goto('/');
    // The button has text "STOP"
    await expect(page.getByRole('button', { name: /STOP/i })).toBeVisible();
  });

  test('LIVE mode shows LIVE badge', async ({ page }) => {
    await mockAllRoutes(page, {
      mockStatus: mockStatusLive,
      mockHealth: { ...mockHealth, mode: 'live' },
    });
    await page.goto('/');
    await expect(page.getByText('LIVE').first()).toBeVisible();
  });

  test('blocked trading shows block reason', async ({ page }) => {
    await mockAllRoutes(page, {
      mockStatus: mockStatusBlocked,
    });
    await page.goto('/');
    // trading_allowed: false → "✗ Blocked: Daily loss limit reached"
    await expect(page.getByText(/Blocked/i, { exact: false }).first()).toBeVisible();
  });
});
