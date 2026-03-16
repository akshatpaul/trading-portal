import { test, expect } from '@playwright/test';
import { mockAllRoutes } from './mockRoutes.js';
import { mockStatusLive } from './fixtures.js';

test.describe('Settings tab', () => {
  test.beforeEach(async ({ page }) => {
    await mockAllRoutes(page);
    await page.goto('/');
    await page.getByRole('button', { name: 'Settings' }).click();
    // Wait for the Trading Mode card
    await page.waitForSelector('text=Trading Mode', { timeout: 5000 });
  });

  test('shows Trading Mode card', async ({ page }) => {
    await expect(page.getByText('Trading Mode')).toBeVisible();
  });

  test('shows Risk Limits section with max daily loss 300', async ({ page }) => {
    // Wait for risk limits to load
    await page.waitForSelector('text=Risk Limits', { timeout: 5000 });
    await expect(page.getByText('Risk Limits').first()).toBeVisible();
    // LimitRow for Max Daily Loss: formatINR(300.0) → "₹300.00"
    const riskCard = page.locator('.card').filter({ hasText: 'Risk Limits' });
    await expect(riskCard.getByText(/300\.00/, { exact: false })).toBeVisible();
  });

  test('shows PAPER mode badge in settings', async ({ page }) => {
    // The settings page shows PAPER badge in the trading mode card
    const modeCard = page.locator('.card').filter({ hasText: 'Trading Mode' });
    await expect(modeCard.getByText('PAPER', { exact: true })).toBeVisible();
  });

  test('"Switch to Live Trading" button is present', async ({ page }) => {
    await expect(page.getByRole('button', { name: /Switch to Live Trading/i })).toBeVisible();
  });

  test('clicking "Switch to Live Trading" opens confirmation dialog', async ({ page }) => {
    await page.getByRole('button', { name: /Switch to Live Trading/i }).click();
    // LiveModeConfirmModal heading should appear
    await expect(page.getByRole('heading', { name: 'Switch to Live Trading' })).toBeVisible();
    // The confirm text is shown in an orange monospace box
    await expect(page.getByText('I understand this uses real money')).toBeVisible();
  });

  test('wrong confirmation text keeps Go Live button disabled', async ({ page }) => {
    await page.getByRole('button', { name: /Switch to Live Trading/i }).click();
    await page.waitForSelector('text=Type exactly to confirm:', { timeout: 5000 });

    // Type wrong text
    await page.getByPlaceholder('Type the confirmation text...').fill('wrong text');

    // "Go Live" button should be disabled
    const goLiveBtn = page.getByRole('button', { name: 'Go Live', exact: true });
    await expect(goLiveBtn).toBeDisabled();

    // Error message appears
    await expect(page.getByText(/doesn't match/i, { exact: false })).toBeVisible();
  });

  test('correct confirmation text enables Go Live button', async ({ page }) => {
    await page.getByRole('button', { name: /Switch to Live Trading/i }).click();
    await page.waitForSelector('text=Type exactly to confirm:', { timeout: 5000 });

    // Type the exact confirm text (from constants.js)
    await page.getByPlaceholder('Type the confirmation text...').fill('I understand this uses real money');

    // "Go Live" button should now be enabled
    const goLiveBtn = page.getByRole('button', { name: 'Go Live', exact: true });
    await expect(goLiveBtn).toBeEnabled();
  });

  test('paper mode switch button calls POST /api/mode/paper (when in live mode)', async ({ page }) => {
    // Set up all routes fresh for this test — live mode status
    await page.route('**/api/status', route =>
      route.fulfill({ json: mockStatusLive }));

    // Track if mode/paper was called
    let paperCalled = false;
    await page.route('**/api/mode/paper', route => {
      paperCalled = true;
      return route.fulfill({ json: { mode: 'paper', message: 'Back to paper trading.' } });
    });

    // Navigate to settings with the live mode status already in place
    await page.goto('/');
    await page.getByRole('button', { name: 'Settings' }).click();
    await page.waitForSelector('text=Trading Mode', { timeout: 8000 });

    // In live mode, the button shows "Switch to Paper"
    const switchPaperBtn = page.getByRole('button', { name: 'Switch to Paper', exact: true });
    await expect(switchPaperBtn).toBeVisible();
    await switchPaperBtn.click();

    // Wait a moment for the API call
    await page.waitForTimeout(500);
    expect(paperCalled).toBe(true);
  });
});
