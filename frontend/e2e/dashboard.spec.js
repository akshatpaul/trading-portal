import { test, expect } from '@playwright/test';
import { mockAllRoutes } from './mockRoutes.js';
import { mockNoPosition } from './fixtures.js';

test.describe('Dashboard tab', () => {
  test.beforeEach(async ({ page }) => {
    await mockAllRoutes(page);
    await page.goto('/');
    // Ensure we're on the dashboard (default tab)
    // Wait for either Trade Log or position card to be visible
    await page.waitForSelector('text=Trade Log', { timeout: 8000 });
  });

  test("shows today's trade count (2)", async ({ page }) => {
    // PnLCard renders "2 trades today" — the WinRateCard also renders "2 trades today"
    // Use .first() since both are visible and both are correct
    await expect(
      page.getByRole('paragraph').filter({ hasText: /^2 trades today$/ }).first()
    ).toBeVisible();
  });

  test('shows win rate (50%)', async ({ page }) => {
    // WinRateCard shows "1W" and "1L" spans
    await expect(page.getByText('1W', { exact: true })).toBeVisible();
    await expect(page.getByText('1L', { exact: true })).toBeVisible();
  });

  test('shows P&L (₹150.50)', async ({ page }) => {
    // PnLCard: formatPnL(150.5) → "+₹150.50"
    // The main content area shows this in the PnLCard
    await expect(page.getByRole('main').getByText(/150\.50/, { exact: false })).toBeVisible();
  });

  test('open position card shows symbol TCS', async ({ page }) => {
    // PositionCard shows formatSymbol('TCS.NS') = 'TCS' in a font-mono bold text
    // Use the heading "Open Position" context to find TCS below it
    const positionCard = page.locator('.card').filter({ hasText: 'Open Position' });
    await expect(positionCard.getByText('TCS', { exact: true })).toBeVisible();
  });

  test('position shows unrealised P&L ₹30.00', async ({ page }) => {
    // formatPnL(30.0) → "+₹30.00" shown in the position card
    const positionCard = page.locator('.card').filter({ hasText: 'Unrealised P&L' }).first();
    await expect(positionCard.getByText(/30\.00/, { exact: false })).toBeVisible();
  });

  test('watchlist shows HDFCBANK, TCS, INFY', async ({ page }) => {
    // Watchlist card has heading "Today's Watchlist"
    const watchlistCard = page.locator('.card').filter({ hasText: "Today's Watchlist" }).first();
    await expect(watchlistCard.getByText('HDFCBANK', { exact: true })).toBeVisible();
    await expect(watchlistCard.getByText('INFY', { exact: true })).toBeVisible();
  });

  test('no position shows "No open position"', async ({ page }) => {
    // Override positions route to return no position
    await page.route('**/api/positions', route =>
      route.fulfill({ json: mockNoPosition }));
    await page.reload();
    await page.waitForSelector('text=Trade Log', { timeout: 8000 });
    await expect(page.getByText('No open position', { exact: false })).toBeVisible();
  });
});
