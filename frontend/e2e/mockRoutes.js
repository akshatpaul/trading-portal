import * as f from './fixtures.js';

export async function mockAllRoutes(page, overrides = {}) {
  const fixtures = { ...f, ...overrides };

  await page.route('**/health', route =>
    route.fulfill({ json: fixtures.mockHealth }));
  await page.route('**/api/status', route =>
    route.fulfill({ json: fixtures.mockStatus }));
  await page.route('**/api/watchlist', route =>
    route.fulfill({ json: fixtures.mockWatchlist }));
  await page.route('**/api/positions', route =>
    route.fulfill({ json: fixtures.mockPosition }));
  await page.route('**/api/trades**', route =>
    route.fulfill({ json: fixtures.mockTrades }));
  await page.route('**/api/candles/**', route =>
    route.fulfill({ json: fixtures.mockCandles }));
  await page.route('**/api/performance', route =>
    route.fulfill({ json: fixtures.mockPerformance }));
  await page.route('**/api/risk-limits', route =>
    route.fulfill({ json: fixtures.mockRiskLimits }));
  await page.route('**/api/emergency-stop', route =>
    route.fulfill({ json: { stopped: true, positions_closed: 1, message: 'Bot paused.' } }));
  await page.route('**/api/mode/paper', route =>
    route.fulfill({ json: { mode: 'paper', message: 'Back to paper trading.' } }));
  await page.route('**/api/mode/live', route =>
    route.fulfill({ json: { mode: 'live', message: 'Now trading with real money.' } }));
  await page.route('**/api/kite/login-url', route =>
    route.fulfill({ json: { url: 'https://kite.zerodha.com/connect/login' } }));
  // Block WebSocket connections (Playwright doesn't support WS mocking easily)
  await page.route('**/ws', route => route.abort());
}
