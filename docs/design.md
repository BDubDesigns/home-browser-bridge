# Design

## Architecture

Two halves, joined by Tailscale:

```
Agent VM (cloud)                        Your computer (home)
+------------------+    Tailscale    +---------------------------+
| Agent            |  -- JSON over -- | Bridge service (Node)     |
| - builds payload |   tailnet only  | - Playwright + Chromium   |
| - sends actions  |                 | - persistent profile      |
| - reports back   |                 | - HTTP on tailnet IP only |
+------------------+                 +---------------------------+
```

**Bridge (laptop side):** Node.js + Playwright. One persistent browser context, so
logins and sessions stick around between actions. A tiny HTTP service listens
only on the tailnet IP (never 0.0.0.0, never public). It takes an action payload,
drives the browser, and returns a result: what it did, what it saw, and the
current state (URL, cart contents, totals).

**Agent (cloud side):** builds the payload (site, steps, items, details) and
sends it over the tailnet with curl through the tunnel proxy. It never sees a
password and never holds a session cookie. Setup and maintenance go over SSH
through the same tunnel.

## Payload format (draft)

```json
{
  "site": "papajohns.com",
  "action": "order",
  "steps": [
    { "go": "https://www.papajohns.com/order/specials" },
    { "deal": "two-large-2-topping" },
    { "pizza": { "size": "large", "crust": "epic-stuffed", "toppings": ["pepperoni"], "sauce": "original", "sauceAmount": "normal" } },
    { "pizza": { "size": "large", "crust": "original", "toppings": ["canadian-bacon", "pineapple"], "sauce": "original", "sauceAmount": "normal" } },
    { "fulfillment": "carryout", "store": "1306 Lakeway Dr, Bellingham, WA" }
  ],
  "confirmBeforeSpend": true
}
```

Money actions stop at the cart and wait for the human to confirm. The bridge
never completes a purchase on its own.

## Milestones

- **M1: prove the path.** SSH from the agent VM to the laptop works; Playwright
  + Chromium run on the laptop; the bridge loads papajohns.com and sign-in
  works from the home IP.
- **M2: first real order.** The Papa Johns order that started this project,
  placed through the bridge with human confirmation.
- **M3: usable by others.** README, setup script, and enough docs that someone
  else can run it without asking us questions.

## Verified so far (Nov 18, 2026)

- Cloud-browser sign-in to Papa Johns fails with a generic "an error occurred"
  for both the saved login and the account owner typing it himself. The site
  never says the password is wrong.
- The laptop (`brandons-linux-acer-neo`) is on the tailnet and answers TCP on
  port 22, but no SSH banner comes back yet, so SSH server status is still
  unconfirmed.
- The agent's browser tasks cannot route through a proxy, and its built-in
  Tailscale client does not support exit nodes.

## Open questions

- Which port does the bridge listen on? (Proposing 8787.)
- How does the bridge authenticate the agent beyond tailnet-only? A shared
  token in a header is the likely second gate.
- How are stale sessions handled when a site logs the browser out?
- What happens when the laptop sleeps mid-order? (Answer so far: nothing runs
  until it wakes up. Orders wait.)
