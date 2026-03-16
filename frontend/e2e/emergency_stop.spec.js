import { test, expect } from '@playwright/test';
import { mockAllRoutes } from './mockRoutes.js';

test.describe('Emergency Stop modal', () => {
  test.beforeEach(async ({ page }) => {
    await mockAllRoutes(page);
    await page.goto('/');
  });

  test('Emergency Stop button opens modal', async ({ page }) => {
    await page.getByRole('button', { name: /STOP/i }).click();
    // Modal appears with "Emergency Stop" heading
    await expect(page.getByText('Emergency Stop')).toBeVisible();
    await expect(page.getByText(/close all open positions/i, { exact: false })).toBeVisible();
  });

  test('confirming calls POST /api/emergency-stop', async ({ page }) => {
    let emergencyCalled = false;
    await page.route('**/api/emergency-stop', route => {
      emergencyCalled = true;
      return route.fulfill({ json: { stopped: true, positions_closed: 1, message: 'Bot paused.' } });
    });

    await page.getByRole('button', { name: /STOP/i }).click();
    await page.waitForSelector('text=Emergency Stop', { timeout: 5000 });

    // Click the "STOP ALL TRADING" confirmation button
    await page.getByRole('button', { name: 'STOP ALL TRADING' }).click();

    // Wait for API to be called
    await page.waitForTimeout(500);
    expect(emergencyCalled).toBe(true);
  });

  test('Cancel closes modal without calling emergency-stop', async ({ page }) => {
    let emergencyCalled = false;
    await page.route('**/api/emergency-stop', route => {
      emergencyCalled = true;
      return route.fulfill({ json: { stopped: true, positions_closed: 0, message: 'Bot paused.' } });
    });

    await page.getByRole('button', { name: /STOP/i }).click();
    await page.waitForSelector('text=Emergency Stop', { timeout: 5000 });

    // Click Cancel
    await page.getByRole('button', { name: 'Cancel' }).click();

    // Modal should be closed
    await expect(page.getByText('STOP ALL TRADING')).not.toBeVisible();

    // API should NOT have been called
    expect(emergencyCalled).toBe(false);
  });
});
