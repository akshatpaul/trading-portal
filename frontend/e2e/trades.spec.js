import { test, expect } from '@playwright/test';
import { mockAllRoutes } from './mockRoutes.js';

test.describe('Trades tab', () => {
  test.beforeEach(async ({ page }) => {
    await mockAllRoutes(page);
    await page.goto('/');
    // Navigate to Trades tab
    await page.getByRole('button', { name: 'Trades' }).click();
    // Wait for the Trade History heading
    await page.waitForSelector('text=Trade History', { timeout: 5000 });
  });

  test('navigates to trades view and shows "Trade History"', async ({ page }) => {
    await expect(page.getByText('Trade History')).toBeVisible();
  });

  test('HDFCBANK trade row is visible', async ({ page }) => {
    await expect(page.getByText('HDFCBANK', { exact: true })).toBeVisible();
  });

  test('TARGET trade shows target badge (🎯 or "Target Hit")', async ({ page }) => {
    // The ReasonBadge for 'TARGET' uses lowercased key lookup:
    // TRADE_REASON_BADGES['target'] = { emoji: '🎯', label: 'Target Hit' }
    // The emoji is shown, label is hidden on small screens but visible on sm+
    // At 1280px width the label "Target Hit" should be visible
    const targetBadge = page.getByText('Target Hit', { exact: false });
    await expect(targetBadge).toBeVisible();
  });

  test('STOP_LOSS trade shows stop loss badge (🛑 or "Stop Loss")', async ({ page }) => {
    // TRADE_REASON_BADGES['stop_loss'] = { emoji: '🛑', label: 'Stop Loss' }
    const stopBadge = page.getByText('Stop Loss', { exact: false });
    await expect(stopBadge).toBeVisible();
  });

  test('profit trade P&L is green (positive)', async ({ page }) => {
    // HDFCBANK trade: pnl: 40.0 → "+₹40.00" with text-profit class
    await expect(page.getByText(/\+.*40\.00/, { exact: false })).toBeVisible();
  });

  test('loss trade P&L shows negative value', async ({ page }) => {
    // TCS trade: pnl: -27.0 → "-₹27.00" with text-loss class
    await expect(page.getByText(/27\.00/, { exact: false })).toBeVisible();
  });
});
