import { test, expect } from '@playwright/test';
import { mockAllRoutes } from './mockRoutes.js';

test.describe('Performance tab', () => {
  test.beforeEach(async ({ page }) => {
    await mockAllRoutes(page);
    await page.goto('/');
    await page.getByRole('button', { name: 'Performance' }).click();
    // Wait for the Overall Statistics heading
    await page.waitForSelector('text=Overall Statistics', { timeout: 8000 });
  });

  test('shows Overall Statistics heading', async ({ page }) => {
    await expect(page.getByText('Overall Statistics')).toBeVisible();
  });

  test('win rate 60% is displayed', async ({ page }) => {
    // StatRow for Win Rate: "60.0%" in the Overall Statistics card
    const statsCard = page.locator('.card').filter({ hasText: 'Overall Statistics' });
    await expect(statsCard.getByText('60.0%', { exact: true })).toBeVisible();
  });

  test('profit factor 2.1 is displayed', async ({ page }) => {
    // StatRow for Profit Factor: "2.10" in the Overall Statistics card
    const statsCard = page.locator('.card').filter({ hasText: 'Overall Statistics' });
    await expect(statsCard.getByText('2.10', { exact: true })).toBeVisible();
  });

  test('net P&L ₹720 is displayed', async ({ page }) => {
    // StatRow for Net P&L: formatPnL(720.0) → "+₹720.00" in Overall Statistics
    const statsCard = page.locator('.card').filter({ hasText: 'Overall Statistics' });
    await expect(statsCard.getByText('+₹720.00', { exact: true })).toBeVisible();
  });
});
