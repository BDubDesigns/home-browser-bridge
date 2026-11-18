# Home Browser Bridge

Your AI agent's browser lives in a datacenter. Some sites notice, and they block it.

This project runs a real browser on your own computer at home instead, and lets your agent drive it remotely over Tailscale. The site sees you, on your home IP, in a real browser. The agent just sends it actions.

## The problem

AI assistants like Muse run their browsers on cloud servers. To a website, that traffic comes from a datacenter IP, which is exactly what bot detection looks for. The result:

- Sign-in fails with a generic error, even when the password is right. We watched Papa Johns do this: the saved login failed three times, and then the account owner himself failed signing in from the same cloud browser, with the same "an error occurred, please try again later" message. The site never said the password was wrong.
- A proxy through your home machine does not fix it, because the agent's browser tasks cannot route through a proxy. Exit nodes are not supported by the agent's built-in Tailscale client either.

So the agent can research a site but cannot sign in or order on the ones that care.

## The fix

Flip it around: do not bring the home network to the cloud browser. Bring the browser home.

1. A small service runs on your own computer (the "bridge"). It runs a real Chromium browser with a persistent profile.
2. You sign in once, in that browser, on your own machine. Your sessions and logins live there, in your browser profile. They never go to the agent.
3. The agent sends action payloads over Tailscale (your private network) as JSON: open this site, add these items, fill this form.
4. The bridge drives the browser and reports back what happened.
5. Anything that spends money is drafted first and confirmed by you before it runs. No silent checkouts.

## Security model

- **Tailnet only.** The bridge listens on the Tailscale address, never the public internet. If you are not on the tailnet, you cannot reach it.
- **Credentials stay home.** The agent never holds your passwords. It sends actions, not logins. If the bridge ever needs a login it does not have, you sign in yourself in the laptop browser.
- **Approve before spend.** Orders, purchases, and anything that costs money require your confirmation first.
- **Your machine, your rules.** The bridge only runs when your computer is awake and on the tailnet. Turn it off and the agent loses the browser, nothing else changes.

## Status

In progress. First milestone: prove the path end to end with a Papa Johns order (two large pizzas, the order that started this project). See `docs/design.md` for the plan.

## Setup

Prerequisites: Tailscale on both machines, SSH access from the agent machine to your computer, Node.js, Playwright + Chromium on your computer.

1. Clone this repo on your computer.
2. Install dependencies and the browser: `npm install`, then `npx playwright install chromium`.
3. Start the bridge: `node bridge/server.mjs`. It binds to your tailnet IP only.
4. Sign in to the sites you want the agent to use, once, in the bridge browser profile.
5. From the agent side, send actions to `http://<your-tailnet-ip>:<port>/action`.

See `docs/design.md` for the payload format and the full plan.

## Why not just use a proxy or an exit node?

We tried that reasoning first. The agent's built-in Tailscale client does not support exit nodes, and its browser tasks cannot route through a proxy, so the cloud browser cannot borrow your home IP. Running the browser on your machine sidesteps the question entirely: the browser is already home.

## Who this is for

Anyone whose AI assistant can browse but cannot sign in, check out, or order because the site blocks datacenter traffic. If you have hit the same wall, this is the workaround.
