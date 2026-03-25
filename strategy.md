# Strategy — Future Features

## Phase 2: Real-Time Streaming
- WebSocket connection to Kalshi streaming API
- Sub-second price updates for high-urgency markets (Fed decisions, election night)
- Heartbeat + auto-reconnect logic

## Phase 3: Cross-Platform Arbitrage
- Compare Kalshi vs Polymarket prices for overlapping markets
- Flag price discrepancies > 5% as arb opportunities
- Feed into OpenClaw arb-scanner module

## Phase 4: Auto-Hedge Integration
- When Kalshi Fed market moves significantly, auto-adjust crypto position sizing
- Map Kalshi economic signals to crypto exposure recommendations
- Integration with OpenClaw portfolio module

## Phase 5: Economic Calendar
- Sync with economic release calendar (BLS, Fed, Treasury)
- Pre-position signal alerts before scheduled releases
- Post-release surprise detection (actual vs Kalshi consensus)

## Phase 6: Historical Accuracy Tracker
- Track Kalshi market predictions vs actual outcomes
- Build calibration curves per category
- Weight signal confidence by historical accuracy

## Phase 7: Settlement Event Intelligence
- Track market resolution patterns
- Detect early settlement signals
- Build notification pipeline for high-value settlements
