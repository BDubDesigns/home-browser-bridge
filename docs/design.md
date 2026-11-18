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
  works from the home IP. **Done Nov 18, 2026:** the bridge runs on the laptop
  and, driven from the agent VM over the tailnet, loaded papajohns.com with its
  real title. Papa Johns was then dropped as a target (Brandon tried ordering
  on his own and got a generic rejection, so it was not a clean test).
- **M2: clear a site that blocks automation.** Reddit is the current test: it
  normally blocks datacenter IPs, and it also fingerprints automated browsers.
  The home IP alone did not clear it (Nov 18: reddit.com showed "Prove your
  humanity", old.reddit.com bounced to login, both anonymous, fresh profile).
  Current approach: reduce automation tells (disable the webdriver flag) and
  offer a headed mode (`BRIDGE_HEADED=1`) that looks like a real person using
  the browser. Anti-detection is a moving target; no guarantee Reddit stays
  cleared.
- **M3: usable by others.** README, setup script, and enough docs that someone
  else can run it without asking us questions.

## Verified so far (Nov 18, 2026)

- Cloud-browser sign-in to Papa Johns fails with a generic "an error occurred"
  for both the saved login and the account owner typing it himself. The site
  never says the password is wrong. (Papa Johns later dropped as a target;
  Brandon's own order attempt was also rejected with a generic error.)
- The laptop (`brandons-linux-acer-neo`, CachyOS) is on the tailnet and runs
  openssh-server, Node 22, Python 3, and Google Chrome. SSH from the agent VM
  works with a key, but the tunnel proxy is flaky: file-transfer and install
  commands over SSH (`git clone`, `npm install`, `scp`) repeatedly fail at the
  CONNECT stage while short read-only commands go through. Setup steps on the
  laptop are done by hand for now.
- The agent's browser tasks cannot route through a proxy, and its built-in
  Tailscale client does not support exit nodes.
- The bridge (Node + Playwright + system Chrome, tailnet-only HTTP on port
  8787) runs on the laptop and answers from the agent VM. It loaded
  papajohns.com and reddit.com from the home IP.

## Open questions

- Which port does the bridge listen on? (Proposing 8787.)
- How does the bridge authenticate the agent beyond tailnet-only? A shared
  token in a header is the likely second gate.
- How are stale sessions handled when a site logs the browser out?
- What happens when the laptop sleeps mid-order? (Answer so far: nothing runs
  until it wakes up. Orders wait.)
