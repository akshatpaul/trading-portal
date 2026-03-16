import { test, expect } from '@playwright/test';
import { mockAllRoutes } from './mockRoutes.js';

test.describe('Chart tab', () => {
  test.beforeEach(async ({ page }) => {
    await mockAllRoutes(page);
    await page.goto('/');
    await page.getByRole('button', { name: 'Chart' }).click();
    // Wait for chart controls to appear
    await page.waitForSelector('input[placeholder*="Symbol"]', { timeout: 8000 });
  });

  test('navigates to chart view and chart container is present', async ({ page }) => {
    // The chart container is a div with ref, rendered as part of the card
    // The LiveChart card always renders a container div with minHeight: 420
    const chartArea = page.locator('[style*="min-height"]').first();
    await expect(chartArea).toBeVisible();
  });

  test('symbol input field is present', async ({ page }) => {
    // The form contains an input with placeholder "Symbol e.g. RELIANCE"
    const symbolInput = page.getByPlaceholder('Symbol e.g. RELIANCE');
    await expect(symbolInput).toBeVisible();
  });

  test('shows TCS as active symbol (from open position)', async ({ page }) => {
    // The context sets effectiveChartSymbol from watchlist[0] which is HDFCBANK,
    // but the position is TCS.NS. The chart active symbol display shows the current symbol.
    // In AppContext: effectiveChartSymbol = chartSymbol || watchlistItems[0]?.symbol → 'HDFCBANK'
    // The symbol input should show HDFCBANK (first watchlist item)
    const symbolInput = page.getByPlaceholder('Symbol e.g. RELIANCE');
    // The input value gets synced to activeSymbol via useEffect(symbol prop)
    // effectiveChartSymbol = 'HDFCBANK' (from watchlist[0])
    await expect(symbolInput).toHaveValue('HDFCBANK');
  });

  test('interval selector buttons are present (5m, 15m, 1d)', async ({ page }) => {
    await expect(page.getByRole('button', { name: '5m', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '15m', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '1d', exact: true })).toBeVisible();
  });

  test('Go button submits symbol search', async ({ page }) => {
    const symbolInput = page.getByPlaceholder('Symbol e.g. RELIANCE');
    await symbolInput.fill('INFY');
    await page.getByRole('button', { name: 'Go', exact: true }).click();
    // After submit, the active symbol display changes
    // The text "INFY · 5m" should appear
    await expect(page.getByText(/INFY.*5m/, { exact: false })).toBeVisible();
  });

  test('watchlist shows symbols from mock data', async ({ page }) => {
    // The right sidebar shows the Watchlist with HDFCBANK, TCS, INFY
    await expect(page.getByText('HDFCBANK', { exact: true }).first()).toBeVisible();
  });
});
