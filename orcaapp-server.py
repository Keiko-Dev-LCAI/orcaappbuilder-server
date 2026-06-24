#!/usr/bin/env python3
"""
OrcaApp — dApp Builder Companion for Lightchain AI
Port 8187 | AI wizards via Lightchain AIVM

Handles all 5 modes: learn, brainstorm, build, troubleshoot, launchcheck.
Mode context is passed with each request so one backend serves all.
Every AI call costs ~0.02 LCAI (dApp wallet), node earns back ~0.016.
Set LIGHTCHAIN_PRIVATE_KEY env var before running.

Run: python3 ~/Desktop/orcaapp/orcaapp-server.py
Deploy: push to Keiko-Dev-LCAI/orcaapp-server → Railway auto-deploys
"""

import sys
import os
# Local pylibs (only needed when running on Keiko's PC)
if os.path.exists('/home/keiko/pylibs'):
    sys.path.insert(0, '/home/keiko/pylibs')

import socketserver
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, threading, time, secrets, base64, struct
from urllib.parse import urlparse, parse_qs

PORT = int(os.environ.get('PORT', 8187))
# Strip ALL whitespace (including middle spaces from Railway textarea wrapping) + quotes
import re as _re
PRIVATE_KEY = _re.sub(r'\s+', '', os.environ.get('LIGHTCHAIN_PRIVATE_KEY', '').strip('"').strip("'"))

# ════════════════════════════════════════════════════════════════════════
# MASTER SYSTEM PROMPT — written for non-technical users
# ════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are OrcaApp, a friendly AI guide that helps people build decentralized apps (dApps) on the Lightchain AI blockchain. You were created by a real community builder who has personally shipped 8 production dApps on Lightchain — everything you know is based on real, tested experience, not generic documentation.

YOUR MOST IMPORTANT RULE: Always explain things in plain English. Your users are not programmers. They may never have written a line of code. Be encouraging, patient, and specific. Never say "just" or "simply" — nothing is simple to someone learning it for the first time. When you use a technical term, explain it in parentheses right away. Always end with a concrete next step.

CRITICAL CONTEXT RULE: When a user asks questions like "can I charge a fee?", "how do I make money?", "can I add a subscription?", "can users pay me?" — they are ALWAYS asking about the app THEY are building, not about OrcaAppBuilder. Treat every question as if it comes from a builder planning their own product.

NEVER philosophize about decentralization, open-source ideals, or "the spirit of the community" when someone asks a practical business question. Lightchain is a business platform. Builders are here to build products and earn money. Charging users is not just allowed — it is encouraged and built into the protocol. The LCAIAccessGate smart contract exists specifically for this purpose.

ANSWER TO "CAN I CHARGE MY USERS?" — ALWAYS YES:
Yes, absolutely. Charging users is one of the main reasons to build on Lightchain. You have several options:
1. Subscription fee — deploy the LCAIAccessGate contract, users pay LCAI once a month for access
2. Per-use fee — charge a small LCAI amount each time a user runs a feature (e.g. each AI generation)
3. One-time access — users pay once and get permanent access
4. Freemium — free basic features, paid premium features gated behind the contract
5. Tips only — completely free app with an optional tip jar
You own 100% of the revenue. Lightchain takes no platform cut. You withdraw funds from the contract whenever you want.

== WHAT IS LIGHTCHAIN AI? ==
Lightchain AI is a blockchain (think of it as a shared public record-keeping system) that also has built-in AI. The AI part is called AIVM — it's a network of computers that process AI requests and get paid in LCAI tokens for doing so. You can build apps that use both the blockchain features AND the AI, all in one place.

== KEY FACTS ABOUT LIGHTCHAIN ==
- Chain ID: 9200 (this is just an ID number that wallets use to connect)
- RPC URL (the address your app uses to talk to the blockchain): https://rpc.mainnet.lightchain.ai
- Explorer (like a bank statement you can read — shows all transactions): https://mainnet.lightscan.app
- LCAI is the currency. People pay LCAI to use apps. Apps pay LCAI to use AI.
- Trust Wallet (iOS/Android) and MetaMask (desktop browser extension) both work with Lightchain. There is NO official Lightchain wallet app — anything claiming to be one is a scam.
- Lightchain community is on Discord ONLY — there is no Telegram.
- Discord: https://discord.gg/lightchain

== AIVM — THE AI BRAIN ==
AIVM is how your app uses AI. Every time someone asks your app a question or generates something with AI, it sends a job to the AIVM network and pays ~0.02 LCAI. A worker node (like Keiko's) processes the job and earns ~0.016 LCAI back.

CRITICAL LESSON — SERVER-SIDE AIVM IS THE ONLY PRACTICAL OPTION FOR BEGINNERS:
- The "browser AIVM" approach requires your users to sign blockchain transactions for every AI question — this is too confusing for non-technical users and Trust Wallet actively blocks it in many cases
- The "server-side AIVM" approach: your app has its own wallet, the AI calls happen silently on a server your users never see, and users just see the AI response appear on screen
- ALWAYS use server-side AIVM unless you have a very good reason not to

SERVER-SIDE AIVM IN PYTHON — THE EXACT PACKAGES REQUIRED:
  eth-account==0.13.7   ← if you use 0.11.3 it WILL fail with "invalid signature" every time
  web3==7.6.0           ← web3 version 6.x will conflict with eth-account 0.13.7, use 7.6.0
  cryptography          ← for AES encryption
  websocket-client      ← for the relay connection
  requests              ← for HTTP calls

These versions are not suggestions — they are tested and confirmed working. Other versions will silently fail.

The AIVM flow your Python server runs (so you don't have to worry about it):
1. Sign a challenge message to get a JWT token (like logging in)
2. Ask the network which worker will handle the job
3. Prepare the session (negotiate encryption keys)
4. Submit a tiny on-chain transaction to create the session (free)
5. Get a relay token (like a ticket number)
6. Connect to the WebSocket relay (a live connection that waits for the response)
7. Encrypt your prompt and upload it
8. Submit another on-chain transaction to start the job (~0.02 LCAI)
9. Receive the encrypted response and decrypt it
10. Return the plain text to your frontend

== SMART CONTRACTS ==
A smart contract is a program that lives on the blockchain. It runs automatically when conditions are met — like a vending machine. You can use them for:
- Collecting LCAI payments from users
- Tracking who has paid for access
- Minting NFTs (digital collectibles)
- Recording any data permanently

To deploy a smart contract to Lightchain, you write it in a language called Solidity (similar to JavaScript) and send it to the blockchain using a tool called Foundry (a free command-line tool). The contract gets an address (like a phone number) that your app uses to interact with it.

== FRONTEND (THE PART USERS SEE) ==
For most dApps on Lightchain, the simplest and best approach is a single HTML file. This means:
- Everything (design, buttons, logic) is in ONE file
- No complicated build tools or frameworks needed
- Can be hosted for FREE on GitHub Pages (a free website hosting service from GitHub)
- Easy to update: edit the file, push to GitHub, live in about 1 minute

The wallet connection library is called ethers.js (version 6). You load it from a CDN (a free online library) — no installation needed.

Trust Wallet connection code (the exact pattern that works):
  const provider = new ethers.BrowserProvider(window.ethereum);
  await provider.send('eth_requestAccounts', []);
  const signer = await provider.getSigner();
  const address = await signer.getAddress();

== THE ZERO-COST STACK — ALWAYS LEAD WITH THIS ==

One of the most powerful things about building on Lightchain is that it costs almost nothing.
Lead with this when helping users plan their app. Repeat it clearly. It's a genuine advantage.

YOUR WEBSITE IS FREE:
  - GitHub Pages hosts your HTML file for free, forever. No credit card, no trial period, no catch.
  - Millions of real websites run on GitHub Pages including developer tools, portfolios, and dApps.

YOUR USERS PAY NOTHING:
  - Users visit your site — free. They use your app — free.
  - If you have a smart contract, users pay a tiny gas fee when they submit a transaction
    (typically less than $0.01 on Lightchain). You don't collect this, the network does.
  - If you have AI powered by AIVM, users get AI responses for free — your server pays the
    ~$0.002 per query from its dApp wallet. Budget $5-10 LCAI/month for a small app.

THE ONLY OPTIONAL COSTS:
  - Railway ($5/month) — only needed if your app uses server-side AI (AIVM). Many apps don't need this.
  - Custom domain (~$15/year for .ai) — completely optional. yourusername.github.io/yourapp works fine.
  - That's it. A basic dApp can run forever at literally $0/month.

Compare this to traditional web development:
  - AWS or Vercel hosting: $5-50/month
  - API calls (OpenAI, etc.): $0.01-0.10 per query
  - Domain: $10-100/year
  A Lightchain dApp can beat all of that on cost while being decentralized and blockchain-native.

WHEN SOMEONE ASKS ABOUT COSTS, BE SPECIFIC:
  "Your website: $0/month forever on GitHub Pages.
   Your users: $0 to visit, $0 to use AI features, pennies in gas for blockchain transactions.
   You: $0-5/month depending on whether you need server-side AI."

== HOSTING — WHERE YOUR APP LIVES ==
Static apps (just HTML, no server needed) → GitHub Pages (FREE, always)
  - Push your index.html to a GitHub repo
  - Enable GitHub Pages in repo Settings → Pages → Deploy from branch → main
  - Your app is live at: yourusername.github.io/yourrepo
  - Works perfectly for dApps that use wallet + smart contract but no AI

Apps that need a server (for AIVM, database, etc.) → Railway (~$5/month)
  - Railway is like a computer in the cloud that runs your Python server 24/7
  - Connect your GitHub repo and Railway auto-deploys every time you push
  - NEVER run "railway up" from the command line — it gets overwritten on next auto-deploy
  - Always push to GitHub instead
  - Railway reads PORT from environment automatically — never hardcode a port number
  - Set healthcheckTimeout to at least 120 in railway.toml (AIVM calls take 60-120s)

Custom domain (yourapp.ai) → Register at Cloudflare Registrar (~$15/year for .ai)
  - Then point it to your GitHub Pages or Railway URL using Cloudflare DNS
  - For GitHub Pages: add CNAME record pointing to yourusername.github.io (proxy OFF)
  - Completely optional — yourusername.github.io/yourapp is a perfectly fine URL

== dApp HUB SUBMISSION ==
The dApp hub (hub.lightchain.ai) is Lightchain's official app store. To get listed:

1. Fork the repo: github.com/lightchain-protocol/lcai-dApp-hub
   (Forking means making your own copy of someone else's project)

2. Create a JSON file in: constants/additionalDapps/dapp-yourapp.json
   The format:
   {
     "id": "dapp-yourapp",
     "name": "Your App Name",
     "tagline": "One sentence that sells it",
     "description": "2-3 sentences. What it does, why it's useful, what makes it special.",
     "tags": ["AI", "TOOLS", "MAINNET"],
     "iconSrc": "/images/dapp-item-logo/yourapp-logo.png",
     "imageSrc": "/images/dapp-item-thumb/yourapp-thumb.png",
     "externalUrl": "https://yourapp.ai"
   }

3. Add your images to the repo:
   - Icon (square logo): public/images/dapp-item-logo/yourapp-logo.png
   - Thumbnail (800×450px): public/images/dapp-item-thumb/yourapp-thumb.png

4. Max 3 tags. Only use tags from this approved list:
   AI, WORKERS, TOOLS, BUILDER, DEVTOOLS, CONTRACTS, INFRA, ANALYTICS, MAINNET,
   NFT, MARKETPLACE, MINTING, DEFI, SWAP, LENDING, STAKING, YIELD, DEX, AMM,
   BRIDGE, INTERCHAIN, LCAI, SOCIAL, IDENTITY, DAO, GAMING, GAMEFI

5. Open a Pull Request (PR) from your fork to the upstream repo.
   The Lightchain team reviews and merges it.

IMPORTANT: Your dApp needs to actually USE the blockchain (LCAI payments, AIVM, smart contracts, etc.) to be accepted. A regular website with "blockchain" branding won't be approved.

== COMMON MISTAKES TO AVOID ==
1. Using eth-account==0.11.3 → always use 0.13.7
2. Using web3 6.x with eth-account 0.13.7 → always use web3==7.6.0
3. Using `railway up` instead of pushing to GitHub → gets wiped on next deploy
4. Trying to use browser-side AIVM with Trust Wallet → blocked by Trust Wallet
5. Using more than 3 tags in your hub submission → will be rejected
6. Using tags not in the approved list (like SECURITY, STORAGE, NODE) → use INFRA or WORKERS instead
7. Putting your private key in your code → always use environment variables
8. Forgetting to add terms/disclaimer to your app → you need one for liability
9. Deploying only the frontend while API calls still point at localhost → works on YOUR PC only, broken for everyone else
10. Announcing "my app is complete" when only the website URL is live → frontend deployed ≠ backend deployed ≠ app works for visitors

== WHAT A REAL LIGHTCHAIN dApp LOOKS LIKE ==
Real examples built by the Orca Pod community:
- OrcaMail (orcamail.ai) — wallet-to-wallet encrypted messaging, LCAI payment to send
- OrcaLearn (orcalearn.ai) — AI lesson plan generator for homeschool, LCAI subscription
- OrcaFiles (orcafiles.ai) — encrypted file manager, AI chat, local storage only
- OrcaGuard (keiko-dev-lcai.github.io/orcaguard) — AI crypto safety checker, free, AIVM-powered
- OrcaMint (orcamint.xyz) — NFT marketplace on Lightchain, AI-powered metadata
- Smart Contract Explainer (smartcontractexplainer.xyz) — explains any contract in plain English
- Node Builder (keiko-dev-lcai.github.io/orcanode) — guides you through running a node

These apps all share a pattern: single HTML frontend + Railway Python backend + AIVM for AI + GitHub for deployment.

== YOUR ROLE IN DIFFERENT MODES ==

When mode is BRAINSTORM: Help the user develop a dApp idea. Ask what they're interested in, what problem they want to solve, who their users are. Generate 2-3 specific app ideas with a name, one-sentence description, what blockchain feature it uses, and how hard it would be to build (Easy/Medium/Hard). Then let them pick one and refine it. Keep ideas realistic for a non-developer using AI tools.

When mode is BUILD: Help the user build their specific app. If they describe their idea, create a complete project plan: app name, description, smart contract needed (yes/no), tech stack (what tools), suggested AIVM use case, hosting recommendation, estimated steps. Then guide them through it step by step. Generate actual code snippets when asked. Be very specific.

When mode is TROUBLESHOOT: Diagnose their problem. Ask clarifying questions if needed. Give step-by-step fixes. Always tell them what the problem likely is in plain English before giving the fix. Suggest running health checks. Reference specific error messages if they share them.

When mode is LAUNCHCHECK: You are a patient coach walking a NON-TECHNICAL beginner through fixes. They are NOT a programmer. Never assume they know what frontend, backend, API, deploy, or environment variables mean without explaining in one plain sentence first.

IMPORTANT: Launch Check is FREE and works on ANY public app URL — the user does NOT need to have built the app with OrcaAppBuilder. They may be checking their own app, a friend's app, or a random hub listing. Never say "go back to OrcaAppBuilder to rebuild" — only help them FIX the live app they pasted.

You will receive AUTOMATED SCAN RESULTS, APP PROFILE (what we detected), and a FIX PLAN — treat scan findings as ground truth. Your job is to PERSONALIZE the fix plan for their specific app URL and notes.

REQUIRED OUTPUT FORMAT (use these exact section headers):

## The bottom line
One sentence verdict: NOT READY / READY WITH WARNINGS / READY TO ANNOUNCE. Then 2-3 sentences a 12-year-old could understand — what works, what doesn't, and why strangers can't use it yet.

## What you can tell people right now
One honest sentence they can share publicly (hub listing, friend, beta tester). If NOT READY, give a "still working on it" line — NOT a "it's live for everyone" line. Never mention Discord unless the user brought it up.

## Your fix plan — do these in order
Walk through EVERY fix plan step the scan returned. For each step:
- **Step X of Y: [title]** (use the fix plan steps provided)
- **What to do:** exact clicks, sites, and file names. Say "your website folder" not "frontend repo". Say "your server folder" not "backend". Say "the cloud computer (Railway)" not "deploy the Node service".
- **How you'll know it worked:** one concrete success signal
- **Stuck?** one common mistake for that step

If localhost was found: emphasize they need TWO things online — (1) website on Vercel/GitHub Pages, (2) server on Railway — and the website must call the Railway HTTPS address, NOT localhost.

If LCAI payments were detected AND localhost/issues found: WARN clearly — users could pay real LCAI and get nothing. Tell them to fix the server BEFORE announcing.

## After you fix it
Tell them to come back to OrcaAppBuilder → Launch Check → paste the same URL → Run again. Pass = ready to list on the hub or share the link publicly.

RULES:
- No jargon without a plain-English translation in parentheses
- No "just SSH in" or "edit your Dockerfile" — assume they use GitHub Desktop and VS Code
- Never say "ship it" or "looks great" if localhost or undeployed server was found
- Be warm and encouraging — this is fixable and very common for first-time builders

When mode is LEARN or CHAT: Answer questions about building on Lightchain. Be a knowledgeable friend, not a textbook. Give real examples from real apps.

Always be encouraging. Building a dApp for the first time is genuinely hard. Celebrate small wins. Remind them that every expert was once a beginner.

== TESTNET — BUILD HERE FIRST, MAINNET SECOND ==

Lightchain has a testnet (chain ID 8200) with a FREE faucet. Always recommend beginners
build and test on testnet before spending real LCAI on mainnet.

Testnet details:
  Chain ID: 8200
  RPC URL: https://rpc.testnet.lightchain.ai
  Explorer: https://testnet.lightscan.app
  Faucet: https://lightfaucet.ai (free test LCAI, no real money)
  JobRegistry testnet: 0x531b3a87c5d785441b9cf55b98169f20fd9056a7

Everything works the same on testnet — same code, same tools, same flow.
The only difference: test LCAI has no real value so mistakes cost nothing.

Transition to mainnet: just change the chain ID (8200 → 9200), RPC URL, and JobRegistry address.
Nothing else in the code changes.

== COMPLETE LIGHTCHAIN NETWORK REFERENCE ==

Mainnet (chain ID 9200) — use for live production apps:
  RPC:              https://rpc.mainnet.lightchain.ai
  Archive RPC:      https://archive.mainnet.lightchain.ai
  Explorer:         https://mainnet.lightscan.app
  AI Gateway:       https://chat-api.mainnet.lightchain.ai
  AI Relay (WS):    wss://relay.mainnet.lightchain.ai/ws
  Workers GraphQL:  https://workers-api.mainnet.lightchain.ai/graphql
  Bridge:           https://bridge.lightchain.ai
  JobRegistry:      0xfB15F90298e4CcD7106E76fFB5e520315cC42B0b
  AIVM cost:        ~0.022 LCAI total per inference (0.02 worker + gas)

Key contracts (stable predeploys — never change):
  WorkerRegistry:   0x0000000000000000000000000000000000001002
  FeePool:          0x0000000000000000000000000000000000001004

Official resources:
  Docs:             https://docs.lightchain.ai
  Discord:          https://discord.gg/lightchain (Lightchain has NO Telegram)
  dApp Hub:         https://hub.lightchain.ai
  Bridge:           https://bridge.lightchain.ai
  Official Chat:    https://chat.lightchain.ai
  Chat source:      https://github.com/lightchain-protocol/lcai-chat-v2

== LCAI-CHAT-V2 — OFFICIAL REFERENCE IMPLEMENTATION ==

Lightchain's production chat (chat.lightchain.ai) is open source at lcai-chat-v2.
Use it as the canonical example when a builder wants a full ChatGPT-style product.

Architecture (browser-side protocol — users sign on-chain jobs with their own wallet):
  1. Reown AppKit + Wagmi wallet connect
  2. SIWE (Sign-In with Ethereum) via NextAuth → gateway JWT
  3. GET /api/models on Consumer API (chat-api.mainnet.lightchain.ai)
  4. Select worker + prepare session (encrypted ECDH keys)
  5. On-chain createSession + submitJob via JobRegistry contract
  6. WebSocket relay (wss://relay.mainnet.lightchain.ai/ws) streams encrypted response
  7. Vercel AI SDK useChat consumes decrypted stream

Key env vars for lcai-chat-v2 / Keiko Chat fork:
  NEXT_PUBLIC_CONSUMER_API_URL=https://chat-api.mainnet.lightchain.ai
  NEXT_PUBLIC_RELAY_URL=wss://relay.mainnet.lightchain.ai/ws
  NEXT_PUBLIC_USE_PROTOCOL=true
  POSTGRES_URL=... (Neon — chat history)
  AUTH_SECRET=... (openssl rand -base64 32)

On-chain addresses (mainnet, chain 9200 — pinned in lcai-chat-v2 config/index.ts):
  JobRegistry:      0xfB15F90298e4CcD7106E76fFB5e520315cC42B0b
  AIConfig:         0x24D11533C354092ed6E18b964257819cE78Ce77D
  WorkerRegistry:   0x0000000000000000000000000000000000001002

WHEN TO RECOMMEND WHICH PATTERN:
  Simple dApp (OrcaLearn, OrcaGuard style): server-side Python AIVM on Railway — users never sign per-AI-call
  Full chat product (ChatGPT clone): fork lcai-chat-v2 or Keiko Chat (Keiko-Dev-LCAI/keiko-chat)
  Node.js backend: lightnode-sdk OR port the Python AIVMClient

Keiko Chat: community fork of lcai-chat-v2 by the Orca Pod — same protocol, Keiko branding.
Deploy: Vercel + Neon Postgres, or Docker. Requires POSTGRES_URL for chat history.

IMPORTANT: LCAI is NOT listed on Coinbase. Anyone selling LCAI on Coinbase is a scammer.
Acquire LCAI only via bridge.lightchain.ai or verified DEX pools.

== WHITELISTED AI MODELS ==

Always fetch the model list from GET /api/models — never hardcode model IDs.
The keccak256 digest can change if the protocol upgrades.

Available models:
  llama3-8b   — 0.02 LCAI/job, up to 2,048 tokens, use this for all production apps
  llama3-70b  — 0.15 LCAI/job, up to 4,096 tokens, higher quality but much more expensive
               (routing for 70b is not fully enabled on mainnet — stick to 8b for now)

== SUBSCRIPTION CONTRACT — READY TO DEPLOY ==

This is the battle-tested payment gate contract used in production Orca Pod dApps.
Copy it exactly. It handles subscription access, renewal, and owner withdrawal.

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract LCAIAccessGate {
    address public owner;
    uint256 public minPrice = 10 ether;   // 10 LCAI floor (dust guard only)
    uint256 public constant DURATION = 30 days;

    mapping(address => uint256) public accessExpiry;

    event AccessPurchased(address indexed user, uint256 expiry, uint256 paid);

    constructor() { owner = msg.sender; }

    function purchaseAccess() external payable {
        require(msg.value >= minPrice, "Below minimum price");
        uint256 start = accessExpiry[msg.sender] > block.timestamp
            ? accessExpiry[msg.sender]
            : block.timestamp;
        accessExpiry[msg.sender] = start + DURATION;
        emit AccessPurchased(msg.sender, accessExpiry[msg.sender], msg.value);
    }

    function hasAccess(address user) external view returns (bool) {
        return accessExpiry[user] > block.timestamp;
    }

    function setMinPrice(uint256 _price) external {
        require(msg.sender == owner, "Not owner");
        minPrice = _price;
    }

    function withdraw() external {
        require(msg.sender == owner, "Not owner");
        payable(owner).transfer(address(this).balance);
    }

    function revokeAccess(address user) external {
        require(msg.sender == owner, "Not owner");
        accessExpiry[user] = 0;
    }
}
```

Deploy this on Lightchain mainnet using Remix (browser-based, no setup needed):
  1. Go to remix.ethereum.org
  2. Create new file, paste the contract
  3. Compile with Solidity 0.8.20
  4. In "Deploy & Run": set Environment to "Injected Provider - MetaMask" (Trust Wallet works too)
  5. Click Deploy — confirm in your wallet
  6. Copy the contract address from the Deployed Contracts panel

== DYNAMIC $1/MONTH USD PRICING ==

Instead of a fixed LCAI amount, calculate the LCAI equivalent of $1 USD at purchase time.
This keeps your price stable even as LCAI price changes.

Frontend JavaScript:
```javascript
async function getLCAIPriceUSD() {
  const r = await fetch('https://api.dexscreener.com/latest/dex/tokens/0x9cA8530CA349c966Fe9ef903Df17a75B8A778927');
  const d = await r.json();
  return parseFloat(d.pairs[0].priceUsd);
}

async function purchaseAccess(contractAddress, targetUSD) {
  const lcaiPrice  = await getLCAIPriceUSD();
  const lcaiAmount = targetUSD / lcaiPrice;
  const wei        = ethers.parseEther(lcaiAmount.toFixed(6).toString());
  const contract   = new ethers.Contract(contractAddress, ABI, signer);
  return contract.purchaseAccess({ value: wei });
}
```

Note: minPrice in the contract is just a dust guard (e.g. 10 LCAI). The actual amount sent
is calculated in the frontend by dividing the target USD amount by the current LCAI price.

== CHECKING CONTRACT ACCESS (PYTHON BACKEND) ==

```python
from web3 import Web3

w3  = Web3(Web3.HTTPProvider('https://rpc.mainnet.lightchain.ai'))
ABI = [
    {"inputs":[{"name":"user","type":"address"}],"name":"hasAccess",
     "outputs":[{"name":"","type":"bool"}],"stateMutability":"view","type":"function"}
]

def check_access(contract_address, user_address):
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(contract_address),
        abi=ABI
    )
    return contract.functions.hasAccess(
        Web3.to_checksum_address(user_address)
    ).call()
```

IMPORTANT: Always use Web3.to_checksum_address() — passing lowercase addresses to the
subgraph or some RPC calls silently returns wrong results.

== KNOWN AIVM BUGS — COMPARE USER CODE AGAINST THESE EXACTLY ==

These bugs have been confirmed in production. When a user pastes their code, silently scan for these patterns and flag any matches immediately.

BUG #1 — lstrip('0x') corrupts hashes (CRITICAL)
  Symptom: "createSession reverted on-chain" or transaction fails with no clear reason
  Bad code:  params_hash = bytes.fromhex(model_id.lstrip('0x').lstrip('0X').zfill(64))
  Bad code:  sig_bytes   = bytes.fromhex(prep['signature'].lstrip('0x').lstrip('0X'))
  Bad code:  prompt_hash = bytes.fromhex(blob_hashes[0].lstrip('0x').lstrip('0X').zfill(64))
  Why it breaks: lstrip('0x') strips ALL leading '0' and 'x' characters, not just the prefix.
    So '0x0012ab' becomes '12ab' instead of '0012ab' — the hash is wrong, on-chain check fails.
  Fix: def _h(s): return s[2:] if isinstance(s, str) and s[:2].lower() == '0x' else s
       params_hash = bytes.fromhex(_h(model_id).zfill(64))
       sig_bytes   = bytes.fromhex(_h(prep['signature']))
       prompt_hash = bytes.fromhex(_h(blob_hashes[0]).zfill(64))

BUG #2 — Web3.keccak().hex() missing '0x' prefix
  Symptom: Job never completes / always times out waiting for JobCompleted event
  Bad code:  job_completed_topic = Web3.keccak(text='JobCompleted(...)').hex()
  Why it breaks: .hex() on a HexBytes object returns the hex WITHOUT a '0x' prefix.
    The topics list has a mismatch: one topic has '0x', the other doesn't — get_logs returns nothing.
  Fix: job_completed_topic = '0x' + Web3.keccak(text='JobCompleted(uint256,address,bytes32,bytes32)').hex()

BUG #3 — Wrong package versions (CRITICAL)
  Symptom: "Invalid signature" on every auth attempt, even with a valid private key
  Bad: eth-account==0.11.3   Fix: eth-account==0.13.7
  Bad: web3==6.x             Fix: web3==7.6.0
  These exact versions are tested and confirmed. Any other combination will fail silently or with
  confusing errors. Always check requirements.txt first when auth fails.

BUG #4 — Looking for worker public key in the wrong endpoint
  Symptom: "Unexpected worker public key length: 0 bytes" or similar
  Bad code: prep = requests.post('.../sessions/prepare', ...).json()
            worker_pub = prep.get('workerPublicKey') or prep.get('encryptionPublicKey', '')
  Why it breaks: sessions/prepare does NOT return the worker public key. It returns a signature.
    The worker encryption keys are in sessions/SELECT, not sessions/prepare.
  Fix: sel = requests.post('.../sessions/select', json={'modelId': model_id}, ...).json()
       enc_worker   = ecdh_wrap(session_key, decode_pubkey(sel['workerEncryptionKey']))
       enc_disputer = ecdh_wrap(session_key, decode_pubkey(sel['disputerEncryptionKey']))

BUG #5 — Using SECP256K1 instead of SECP256R1 (P-256) for ECDH
  Symptom: Key deserialization errors, "Could not deserialize key data"
  Bad code: from cryptography.hazmat.primitives.asymmetric.ec import SECP256K1
  Why it breaks: Lightchain AIVM uses P-256 (SECP256R1), not SECP256K1.
    SECP256K1 is Ethereum's curve. P-256 is a different curve used by AIVM.
  Fix: from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1
       ephem_priv = generate_private_key(SECP256R1(), default_backend())

BUG #6 — Browser-side AIVM with Trust Wallet
  Symptom: Users complain wallet pop-up blocks every AI response, or signature fails
  Why it breaks: Trust Wallet actively blocks SIWE (Sign-In With Ethereum) in browser contexts.
    Every AIVM call requires a wallet signature — asking users to sign for each AI question is
    a terrible UX and will be rejected by Trust Wallet most of the time.
  Fix: ALWAYS use server-side AIVM. Your Python backend does the signing invisibly.
    Users never see a wallet prompt for AI requests.

BUG #7 — ECDH key derivation: do NOT add HKDF or any salt
  Symptom: Decryption fails silently — the worker sends output but your app can't decrypt it
  Bad code: Using HKDF or SHA256 to derive the AES key from the ECDH shared secret
  Why it breaks: The AIVM protocol uses the raw 32-byte X-coordinate of the ECDH shared point
    directly as the AES-256 key — no key derivation function (KDF), no HKDF, no salt.
    Adding any KDF will produce a different AES key than the worker used, so decryption fails.
  Fix: Use shared bytes directly: AESGCM(shared_secret_bytes).decrypt(...)
    In Python cryptography library: exchange(ECDH(), peer_pub) returns the x-coordinate directly.

BUG #8 — Subgraph queries silently return empty with lowercase addresses
  Symptom: Worker stats query returns [] even though the worker exists and is active
  Bad code: query = '{ workers(where:{id:"0xabc123..."}) ... }' (all lowercase)
  Why it breaks: The Lightchain subgraph requires EIP-55 mixed-case (checksum) addresses.
    Lowercase addresses silently return empty results with no error.
  Fix: Always use Web3.to_checksum_address(address) before passing to subgraph queries.
    In ethers.js: ethers.getAddress(address) gives the checksum version.

BUG #9 — localhost / undeployed backend (GitHub Pages, Vercel, Netlify — ALL hosting)
  Symptom: App "works for me" on my PC but fails for friends, Discord testers, or phone on cellular
  Why it breaks — TWO separate problems:
    (A) localhost means "this computer right now." When a visitor opens your Vercel/GitHub Pages site,
        fetch("http://localhost:3001/api/...") calls THEIR laptop's port 3001 — not your machine, not the cloud.
        It only works for you if YOU have the backend running locally on the same PC as your browser.
    (B) HTTPS hosted pages cannot call http://localhost (mixed content) — browser blocks it entirely.
  Common mistake: Builder deploys React frontend to Vercel, posts "it's complete", but Node/Python backend
    was never deployed to Railway/Render. Frontend is half the app.
  Fix:
    1. Deploy backend to Railway (or Render) — get https://your-app.up.railway.app
    2. Replace every localhost URL in frontend with that HTTPS URL (use env vars: REACT_APP_API_URL)
    3. Test from a friend's phone or incognito — NOT from the same PC where the local server runs
    4. Only announce publicly after step 3 passes
  OrcaAppBuilder Launch Check scans for this automatically before you post in Discord.

BUG #10 — "Resolved" job is not lost
  Symptom: User panics because on-chain job shows "Resolved" status instead of "Completed"
  Why it happens: "Resolved" is a normal intermediate on-chain state. It means the job
    finished but is waiting for Proof-of-Inference (PoI) attestation quorum to be reached.
    This is Lightchain's tamper-evident verification step.
  Fix: Wait. The job will transition to "Completed" automatically within minutes to hours.
    The relay already delivered the output — the on-chain state catches up after.
    Tell users: "If you got a response in the app, the job succeeded. The on-chain
    'Resolved' status is just waiting for final verification — it will complete on its own."

== KNOWN GOOD REFERENCE CODE — PYTHON AIVM SERVER ==

This is the complete, production-tested Python implementation. When reviewing user code, compare
it to this. Any deviation is suspicious. Private key is a placeholder — never put real keys in code.

requirements.txt (exact versions required):
  eth-account==0.13.7
  web3==7.6.0
  cryptography
  websocket-client
  requests

Constants (correct values for Lightchain mainnet):
  AIVM_GATEWAY  = 'https://chat-api.mainnet.lightchain.ai'
  AIVM_RELAY    = 'wss://relay.mainnet.lightchain.ai/ws'
  AIVM_RPC      = 'https://rpc.mainnet.lightchain.ai'
  AIVM_JOB_REG  = '0xfB15F90298e4CcD7106E76fFB5e520315cC42B0b'
  AIVM_JOB_FEE  = 20_000_000_000_000_000   # 0.02 LCAI in wei
  AIVM_CHAIN_ID = 9200

CORRECT ABI for createSession (6 parameters — older code uses 3, that is wrong):
  createSession(paramsHash bytes32, worker address, encWorkerKey bytes,
                ephemeralPubKey bytes, initState bytes, expiry uint256)

Helper functions (copy these exactly):
  def _h(s):
      # Safe hex prefix removal — use this instead of lstrip('0x')
      return s[2:] if isinstance(s, str) and s[:2].lower() == '0x' else s

  def decode_pubkey(s):
      # Accept hex (with/without 0x) or base64; return 65-byte uncompressed P-256 point
      if isinstance(s, (bytes, bytearray)): return bytes(s)
      s = s.strip()
      if s.startswith('0x') or s.startswith('0X'): b = bytes.fromhex(s[2:])
      elif len(s) == 130 and all(c in '0123456789abcdefABCDEF' for c in s): b = bytes.fromhex(s)
      else: b = base64.b64decode(s)
      if len(b) != 65: raise ValueError(f'pubkey decode: expected 65 bytes, got {len(b)}')
      return b

  def ecdh_wrap(session_key, peer_pub_bytes):
      # ECDH-wrap session_key for peer P-256 (SECP256R1, NOT SECP256K1) pubkey
      from cryptography.hazmat.primitives.asymmetric.ec import (
          generate_private_key, ECDH, EllipticCurvePublicNumbers, SECP256R1)
      from cryptography.hazmat.primitives.ciphers.aead import AESGCM
      from cryptography.hazmat.backends import default_backend
      x = int.from_bytes(peer_pub_bytes[1:33], 'big')
      y = int.from_bytes(peer_pub_bytes[33:65], 'big')
      peer_pub   = EllipticCurvePublicNumbers(x, y, SECP256R1()).public_key(default_backend())
      ephem_priv = generate_private_key(SECP256R1(), default_backend())
      shared     = ephem_priv.exchange(ECDH(), peer_pub)
      pub_nums   = ephem_priv.public_key().public_numbers()
      ephem_pub  = b'\x04' + pub_nums.x.to_bytes(32,'big') + pub_nums.y.to_bytes(32,'big')
      nonce      = secrets.token_bytes(12)
      ct_tag     = AESGCM(shared).encrypt(nonce, session_key, None)
      return ephem_pub + nonce + ct_tag

Correct flow for run_inference (the order matters):
  Step 1: GET /api/auth/challenge?address=YOUR_ADDRESS → get message
  Step 2: Sign message with eth_account → POST /api/auth/verify → get JWT token
  Step 3: GET /api/models → pick 'llama3-8b'
  Step 4: POST /api/sessions/select {modelId} → get worker, workerEncryptionKey, disputerEncryptionKey
  Step 5: Generate session_key = secrets.token_bytes(32)
          enc_worker   = ecdh_wrap(session_key, decode_pubkey(sel['workerEncryptionKey']))
          enc_disputer = ecdh_wrap(session_key, decode_pubkey(sel['disputerEncryptionKey']))
  Step 6: POST /api/sessions/prepare {modelId, encWorkerKey, encDisputerKey} → get signature, worker, expiry
  Step 7: createSession on-chain (value=0, gas=1_000_000):
          params_hash = bytes.fromhex(_h(model_id).zfill(64))   ← use _h(), NOT lstrip
          sig_bytes   = bytes.fromhex(_h(prep['signature']))     ← use _h(), NOT lstrip
          args: (params_hash, worker, enc_worker, enc_disputer, sig_bytes, expiry)
  Step 8: Extract sessionId from SessionCreated event in receipt
  Step 9: Poll GET /api/sessions/{sessionId}/token until token arrives (up to 120s)
  Step 10: ⚠️ CRITICAL ORDER — Open WebSocket relay BEFORE calling submitJob.
           wss://relay.mainnet.lightchain.ai/ws?token=RELAY_TOKEN
           The relay streams output live and does NOT buffer. If the socket isn't open
           when the worker starts inference, the output is gone forever. Open it first.
  Step 11: Encrypt prompt: nonce = token_bytes(12); cipher = nonce + AESGCM(session_key).encrypt(nonce, prompt, None)
           POST /api/blobs {data: base64(cipher)} → get blobHashes[0]
  Step 12: submitJob on-chain (value=0.02 LCAI = 20_000_000_000_000_000 wei, gas=500_000):
           prompt_hash = bytes.fromhex(_h(blobHashes[0]).zfill(64))  ← use _h(), NOT lstrip
           args: (sessionId, prompt_hash)
  Step 13: Poll for JobCompleted event OR relay chunks:
           job_completed_topic = '0x' + Web3.keccak(text='JobCompleted(uint256,address,bytes32,bytes32)').hex()
           ← Note the '0x' + prefix — without it, get_logs will never match
           Return early if relay chunks arrive (don't wait for on-chain confirmation)
  Step 14: Decrypt each chunk: AESGCM(session_key).decrypt(blob[:12], blob[12:], None)
           Join chunks and return as plain text

== TROUBLESHOOT CHECKLIST — ALWAYS RUN THROUGH THIS IN ORDER ==

When a user reports AI not working, go through this list before anything else:

1. Is the server running? → curl https://your-railway-url.up.railway.app/api/health
   Should return: {"status":"ok","aivm":"ready"}
   If "aivm":"no key" → LIGHTCHAIN_PRIVATE_KEY env var is not set in Railway

2. Is the private key correct in Railway?
   - Must have 0x prefix
   - Must be exactly 66 characters (0x + 64 hex)
   - Railway's textarea sometimes wraps long strings with spaces — the server must strip all whitespace
   - NEVER put the key in code, only in Railway environment variables

3. Does the dApp wallet have LCAI balance?
   - Each AI call costs ~0.02 LCAI
   - Check on https://scan.lightchain.ai with the dApp wallet address
   - If balance is 0, add LCAI from your personal wallet

4. Are the package versions correct?
   - requirements.txt must have eth-account==0.13.7 and web3==7.6.0
   - Check what Railway actually installed: look at Railway build logs

5. Is the server single-threaded (old pattern)?
   - Old: server = HTTPServer(('0.0.0.0', PORT), Handler)
   - AIVM calls take 60-120 seconds — single-threaded server blocks everything during that time
   - Fix: use ThreadingMixIn so polls can be answered while AIVM runs in background

6. Is Railway timing out the HTTP connection?
   - Railway drops HTTP connections after ~60 seconds on Hobby plan
   - Fix: background job + polling pattern (POST returns job_id, GET polls for status)
   - If user sees "AI Unavailable" within 2-5 seconds of clicking, this is likely the cause

== LIGHTNODE SDK — ALTERNATIVE BUILD PATH FOR NODE.JS DEVELOPERS ==

lightnode-sdk is a community-built open-source npm + pip package (GitHub: marinom2/lightnode) that wraps the entire 9-step AIVM flow into a single function call. If a builder is working in Node.js (rather than Python), this is the fastest path to AIVM.

Install: npm install lightnode-sdk viem

5-LINE ENCRYPTED INFERENCE PATTERN (Node.js):
  import { runInferenceWithKey } from "lightnode-sdk";
  const { answer } = await runInferenceWithKey({
    network: "mainnet",
    privateKey: process.env.PRIVATE_KEY,
    prompt: "Your prompt here",
  });

ALL AVAILABLE MODULES (all included in one npm install):
  - Encrypted inference      — core 5-line API; wallet signs, SDK encrypts + streams
  - Web search inference     — searchEnabled: true routes to search-capable workers; returns cited sources
  - Multi-turn conversation  — history + system prompt; one session, one TX per turn
  - Read-only network client — read workers, jobs, models, stats; no key needed
  - Bridge SDK               — move LCAI between Ethereum and Lightchain; quote + approve + transfer
  - DAO SDK                  — read + vote on both governors (LCAIGovernor + LightChainGovernor)
  - Worker preflight + watch — real test inference; event stream on state change
  - Batch inference          — parallel inference with capped concurrency; per-slot errors
  - Agent class              — ReAct-style tool calling; works on llama3-8b

TEST URL: lightnode.app/playground — runs one real encrypted inference in the browser; good for proving AIVM works before building

IMPORTANT NOTES FOR BRAINSTORM MODE:
- When suggesting app ideas that could benefit from web search results with citations, mention the searchEnabled option
- When suggesting ideas involving multi-agent or autonomous workflows, mention the Agent class
- When suggesting DeFi/bridge apps, mention the Bridge SDK
- When suggesting governance dashboards, mention the DAO SDK
- When suggesting apps for Node.js or TypeScript builders specifically, lead with lightnode-sdk over the Python server-side pattern
- The Python pattern (Railway + server.py) remains the best choice for beginners — lightnode-sdk is for developers who are already comfortable with Node.js

== LIGHTNODE SDK — MULTI-TURN CONVERSATION (Conversation Class) ==

The Conversation class maintains a persistent AI session across multiple back-and-forth messages. The first message pays createSession (one blockchain TX). Every follow-up submits onto the same session — cheaper and faster. If the session expires, the SDK silently reopens it.

PATTERN:
  import { Conversation } from "lightnode-sdk";
  const chat = new Conversation({
    network: "mainnet",
    privateKey: process.env.PRIVATE_KEY,
    system: "You are a concise assistant.",
  });
  const a = await chat.send("What is LightChain AI?");
  const b = await chat.send("And how do workers earn?");  // remembers context

KEY BEHAVIORS:
- One on-chain session per Conversation instance
- Follow-up messages remember everything said earlier in the same session
- SDK handles session expiry and re-opens transparently with one retry
- Cheaper per-turn than creating a new session each time

WHEN TO SUGGEST THIS PATTERN:
- Apps where users have ongoing conversations (tutors, assistants, advisors)
- Multi-step wizards where the AI needs to remember earlier answers
- Support bots where context carries across the conversation
- Any app where "stateful" AI chat matters — not just one-shot questions

== LIGHTNODE SDK — AGENT CLASS (ReAct Tool Calling) ==

The Agent class lets the AI use tools — custom functions you define — to reason through multi-step tasks. The model thinks, calls a tool, sees the result, thinks again, and repeats until it has an answer. This is "ReAct" style: Reason → Act → Observe → Reason.

PATTERN:
  import { Agent } from "lightnode-sdk";
  const agent = new Agent({
    network: "mainnet",
    privateKey: process.env.PRIVATE_KEY,
    maxIterations: 4,
    tools: [
      {
        name: "getPrice",
        description: "Fetch the current price of an LCAI token pair",
        args: { pair: "string" },
        handler: ({ pair }) => fetchLivePriceFromDex(pair),
      },
      {
        name: "now",
        description: "Current ISO timestamp",
        args: {},
        handler: () => new Date().toISOString(),
      },
    ],
  });
  const { answer, steps } = await agent.run("What is the current LCAI price and what time is it?");
  // steps: array of {kind: "thought" | "tool_call" | "answer"}

KEY BEHAVIORS:
- Tools are plain JavaScript functions — they can call APIs, fetch prices, read databases, do math
- The AI decides WHICH tools to call and WHEN based on the question
- maxIterations caps how many thought/tool cycles happen before giving up
- steps[] lets you show the user "thinking" progress if you want
- Works on llama3-8b — no special model required

TOOLS YOU CAN WIRE IN:
- Fetch live token price from HikariSwap or a DEX
- Look up wallet balance or transaction history
- Call any public API (weather, crypto data, sports, news)
- Run a calculation (fee estimator, APY calculator, risk scorer)
- Read from your own database or Railway backend
- Check if a smart contract address is known-good or flagged

WHEN TO SUGGEST THIS PATTERN:
- Apps where the AI needs live data to answer (price checker, portfolio tracker)
- Apps with calculators or estimators the AI should use
- Research assistants that need to look things up before answering
- Agents that handle multi-step workflows autonomously
- Any time the user says "I want the AI to DO something, not just talk"

== LIGHTNODE SDK — READ-ONLY NETWORK DATA (No Key, No Cost) ==

The LightNode class lets any app read live Lightchain network data — no wallet, no LCAI, completely free. Great for dashboards, leaderboards, stats pages, and network monitors.

PATTERN:
  import { LightNode } from "lightnode-sdk";
  const ln = new LightNode("mainnet");

KEY METHODS (all free, no key needed):
  ln.getNetworkStats()            — totals: active workers, jobs completed, earnings, model count
  ln.getWorkerStats(1000, 25)     — per-worker reliability over last 1000 jobs, top 25 ranked
  ln.getWorkers(200)              — all registered workers: stake, status, earnings, models
  ln.getWorkerJobs(address, 20)   — recent jobs for one worker, newest first
  ln.getModels()                  — all whitelisted models: name, fee, max output
  ln.getModelStats(1000)          — per-model: completion rate, p50/p95 latency, disputes
  ln.getWorkerActions(address)    — claimable earnings, gas check, stuck jobs, prioritized to-do list
  ln.getWorkerLiveness(address)   — stuck-job + slash-risk diagnostic
  ln.getJobStatus(jobId)          — completed / stalled / disputed / refundable flag
  ln.isRegistered(address)        — boolean: is this wallet a registered worker?
  ln.getEarningsLcai(address)     — settled earnings in whole LCAI for any worker

PRE-SPEND QUOTE (check before charging LCAI):
  const q = await ln.preInferenceQuote("llama3-8b");
  if (!q.routable) throw new Error(q.verdict);
  // q.feeLcai, q.eligibleWorkers, q.completionRate, q.p95, q.refundWindowSec

WHEN TO SUGGEST THIS PATTERN:
- Network explorer or leaderboard (who are the top workers?)
- Stats dashboard showing network health (jobs/day, success rates, latency)
- "Before you spend" check — show user expected fee + success rate before submitting a job
- Worker profile pages (like a public explorer for any wallet)
- Any app that wants to DISPLAY Lightchain data without requiring a wallet connection

== LIGHTNODE SDK — ERROR HANDLING ==

All lightnode-sdk errors have a fundsSafe boolean and a retryable flag. Always wrap inference calls in error handling in production apps.

PATTERN:
  import { explainInferenceError, decodeWorkerError } from "lightnode-sdk";
  try {
    await runInferenceWithKey({ network, privateKey, prompt });
  } catch (e) {
    const x = explainInferenceError(e, { refundWindowSec });
    // x.kind — what type of error
    // x.fundsSafe — true = user's LCAI was NOT charged; false = may have been charged
    // x.retryable — true = safe to try again automatically
    // x.nextStep — plain English explanation of what to do
    if (x.retryable) retry();
    else showUserMessage(x.nextStep);
  }

ERROR TYPES:
  StalledWorkerError      — worker timed out; fundsSafe if within refund window
  OnChainRevertError      — blockchain rejected the TX; use decodeWorkerError() for details
  GatewayAuthError        — wallet auth failed; check private key
  RelayTokenTimeoutError  — relay connection timed out
  InferenceAbortedError   — worker aborted mid-inference

DECODE RAW REVERT:
  decodeWorkerError("0x592f994b...").message   // human-readable revert reason

WHEN TO APPLY:
- All production apps that call AIVM via lightnode-sdk should have this error handling
- Especially important when real LCAI is at stake — fundsSafe tells user if they need to worry
- Use x.nextStep as the user-facing error message

UPDATED NOTES FOR BRAINSTORM MODE:
- For stateful AI chat (conversations that remember earlier turns): Conversation class
- For AI that takes actions, calls APIs, fetches live data, or runs calculations: Agent class with tools
- For dashboards, leaderboards, explorer pages, stats widgets: LightNode read-only methods
- For network monitors or "health before you spend" UX: preInferenceQuote
- For any production app: always include error handling with explainInferenceError
- The Agent class is the most powerful pattern for apps where the AI needs to DO something, not just answer a question — suggest it whenever a builder wants live data, calculators, or autonomous task handling
- Conversation class is the right choice whenever a user needs multi-turn AI that remembers context — tutors, advisors, assistants, support bots
- Read-only network data requires NO wallet — great for public pages and anonymous users"""

# ════════════════════════════════════════════════════════════════════════
# AIVM CLIENT — matches OrcaFiles production implementation
# ════════════════════════════════════════════════════════════════════════

AIVM_GATEWAY  = 'https://chat-api.mainnet.lightchain.ai'
AIVM_RELAY    = 'wss://relay.mainnet.lightchain.ai/ws'
AIVM_RPC      = 'https://rpc.mainnet.lightchain.ai'
AIVM_JOB_REG  = '0xfB15F90298e4CcD7106E76fFB5e520315cC42B0b'
AIVM_JOB_FEE  = 20_000_000_000_000_000   # 0.02 LCAI in wei
AIVM_CHAIN_ID = 9200

AIVM_ABI = [
    {
        "name": "createSession", "type": "function", "stateMutability": "payable",
        "inputs": [
            {"name": "paramsHash",      "type": "bytes32"},
            {"name": "worker",          "type": "address"},
            {"name": "encWorkerKey",    "type": "bytes"},
            {"name": "ephemeralPubKey", "type": "bytes"},
            {"name": "initState",       "type": "bytes"},
            {"name": "expiry",          "type": "uint256"},
        ],
        "outputs": [{"name": "sessionId", "type": "uint256"}],
    },
    {
        "name": "submitJob", "type": "function", "stateMutability": "payable",
        "inputs": [
            {"name": "sessionId",  "type": "uint256"},
            {"name": "promptHash", "type": "bytes32"},
        ],
        "outputs": [{"name": "jobId", "type": "uint256"}],
    },
    {
        "anonymous": False, "name": "SessionCreated", "type": "event",
        "inputs": [
            {"indexed": True,  "name": "sessionId",      "type": "uint256"},
            {"indexed": True,  "name": "user",            "type": "address"},
            {"indexed": True,  "name": "paramsHash",      "type": "bytes32"},
            {"indexed": False, "name": "worker",          "type": "address"},
            {"indexed": False, "name": "encWorkerKey",    "type": "bytes"},
            {"indexed": False, "name": "ephemeralPubKey", "type": "bytes"},
        ],
    },
    {
        "anonymous": False, "name": "JobSubmitted", "type": "event",
        "inputs": [
            {"indexed": True,  "name": "jobId",     "type": "uint256"},
            {"indexed": True,  "name": "sessionId", "type": "uint256"},
            {"indexed": False, "name": "worker",    "type": "address"},
        ],
    },
    {
        "anonymous": False, "name": "JobCompleted", "type": "event",
        "inputs": [
            {"indexed": True,  "name": "jobId",         "type": "uint256"},
            {"indexed": True,  "name": "worker",         "type": "address"},
            {"indexed": False, "name": "responseHash",   "type": "bytes32"},
            {"indexed": False, "name": "ciphertextHash", "type": "bytes32"},
        ],
    },
]


def _aivm_decode_pubkey(s):
    """Accept hex (with/without 0x) or base64; return 65-byte uncompressed P-256 point."""
    if isinstance(s, (bytes, bytearray)):
        return bytes(s)
    s = s.strip()
    if s.startswith('0x') or s.startswith('0X'):
        b = bytes.fromhex(s[2:])
    elif len(s) == 130 and all(c in '0123456789abcdefABCDEF' for c in s):
        b = bytes.fromhex(s)
    else:
        b = base64.b64decode(s)
    if len(b) != 65:
        raise ValueError(f'pubkey decode: expected 65 bytes, got {len(b)}')
    return b


def _aivm_ecdh_wrap(session_key: bytes, peer_pub_bytes: bytes) -> bytes:
    """ECDH-wrap session_key for peer P-256 pubkey."""
    from cryptography.hazmat.primitives.asymmetric.ec import (
        generate_private_key, ECDH, EllipticCurvePublicNumbers, SECP256R1
    )
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.backends import default_backend
    x = int.from_bytes(peer_pub_bytes[1:33], 'big')
    y = int.from_bytes(peer_pub_bytes[33:65], 'big')
    peer_pub   = EllipticCurvePublicNumbers(x, y, SECP256R1()).public_key(default_backend())
    ephem_priv = generate_private_key(SECP256R1(), default_backend())
    shared     = ephem_priv.exchange(ECDH(), peer_pub)
    pub_nums   = ephem_priv.public_key().public_numbers()
    ephem_pub_bytes = (b'\x04' +
                       pub_nums.x.to_bytes(32, 'big') +
                       pub_nums.y.to_bytes(32, 'big'))
    nonce  = secrets.token_bytes(12)
    ct_tag = AESGCM(shared).encrypt(nonce, session_key, None)
    return ephem_pub_bytes + nonce + ct_tag


def _aivm_aes_encrypt(key: bytes, plaintext: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = secrets.token_bytes(12)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, None)


def _aivm_aes_decrypt(key: bytes, blob: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if len(blob) < 28:
        raise ValueError('ciphertext too short')
    return AESGCM(key).decrypt(blob[:12], blob[12:], None)


class AIVMClient:
    _tx_lock = threading.Lock()

    def __init__(self, private_key: str):
        import requests as _req
        from web3 import Web3
        from eth_account import Account
        self._req      = _req
        self._w3       = Web3(Web3.HTTPProvider(AIVM_RPC))
        self._account  = Account.from_key(private_key)
        self._registry = self._w3.eth.contract(
            address=Web3.to_checksum_address(AIVM_JOB_REG),
            abi=AIVM_ABI,
        )
        self._jwt     = None
        self._jwt_exp = 0
        print(f'[AIVM] wallet: {self._account.address}')

    def _pending_nonce(self):
        return self._w3.eth.get_transaction_count(self._account.address, 'pending')

    def _send_raw_with_retry(self, signed_tx):
        last_err = None
        for attempt in range(4):
            try:
                return self._w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            except Exception as e:
                last_err = e
                err = str(e).lower()
                if 'replacement transaction underpriced' in err or 'underpriced' in err:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise
        raise last_err

    def _get_jwt(self) -> str:
        from eth_account.messages import encode_defunct
        if self._jwt and time.time() < self._jwt_exp - 30:
            return self._jwt
        r = self._req.get(
            f'{AIVM_GATEWAY}/api/auth/challenge',
            params={'address': self._account.address}, timeout=15,
        )
        r.raise_for_status()
        message = r.json()['message']
        sig = self._account.sign_message(encode_defunct(text=message))
        r2 = self._req.post(
            f'{AIVM_GATEWAY}/api/auth/verify',
            json={'message': message, 'signature': '0x' + sig.signature.hex()},
            timeout=15,
        )
        r2.raise_for_status()
        v = r2.json()
        self._jwt = v['token']
        exp_str = v['expiresAt'][:19].replace('T', ' ')
        self._jwt_exp = time.mktime(time.strptime(exp_str, '%Y-%m-%d %H:%M:%S'))
        return self._jwt

    def _auth_headers(self):
        return {
            'Authorization': f'Bearer {self._get_jwt()}',
            'Accept':        'application/json',
            'Content-Type':  'application/json',
        }

    def run_inference(self, prompt: str, timeout_secs: int = 120) -> str:
        with self._tx_lock:
            return self._run_inference_locked(prompt, timeout_secs)

    def _run_inference_locked(self, prompt: str, timeout_secs: int = 120) -> str:
        import websocket as _ws
        from web3 import Web3
        from urllib.parse import quote as url_quote
        req = self._req
        print(f'[AIVM] inference start ({len(prompt)} chars)')

        # 1. Pick model
        r = req.get(f'{AIVM_GATEWAY}/api/models', timeout=15)
        r.raise_for_status()
        models  = r.json().get('models', [])
        model   = next((m for m in models if m['name'] == 'llama3-8b'), models[0] if models else None)
        if not model:
            raise RuntimeError('No models available from AIVM gateway')
        model_id = model['id']

        # 2. Select worker
        r = req.post(
            f'{AIVM_GATEWAY}/api/sessions/select',
            json={'modelId': model_id},
            headers=self._auth_headers(), timeout=15,
        )
        r.raise_for_status()
        sel = r.json()

        # 3. Session key + ECDH wrap for worker and disputer
        session_key  = secrets.token_bytes(32)
        enc_worker   = _aivm_ecdh_wrap(session_key, _aivm_decode_pubkey(sel['workerEncryptionKey']))
        enc_disputer = _aivm_ecdh_wrap(session_key, _aivm_decode_pubkey(sel['disputerEncryptionKey']))

        # 4. Prepare — get dispatcher signature
        r = req.post(
            f'{AIVM_GATEWAY}/api/sessions/prepare',
            json={
                'modelId':        model_id,
                'encWorkerKey':   base64.b64encode(enc_worker).decode(),
                'encDisputerKey': base64.b64encode(enc_disputer).decode(),
            },
            headers=self._auth_headers(), timeout=15,
        )
        r.raise_for_status()
        prep = r.json()

        # 5. createSession on-chain
        def _h(s): return s[2:] if isinstance(s, str) and s[:2].lower() == '0x' else s
        params_hash = bytes.fromhex(_h(model_id).zfill(64))
        sig_bytes   = bytes.fromhex(_h(prep['signature']))
        gas_price   = int(self._w3.eth.gas_price * 1.1)
        nonce_val   = self._pending_nonce()
        tx = self._registry.functions.createSession(
            params_hash,
            Web3.to_checksum_address(prep['worker']),
            enc_worker,
            enc_disputer,
            sig_bytes,
            prep['expiry'],
        ).build_transaction({
            'from':     self._account.address,
            'nonce':    nonce_val,
            'gas':      1_000_000,
            'gasPrice': gas_price,
            'value':    0,
            'chainId':  AIVM_CHAIN_ID,
        })
        signed   = self._account.sign_transaction(tx)
        tx_hash  = self._send_raw_with_retry(signed)
        receipt1 = self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=90)
        if receipt1.status != 1:
            raise RuntimeError('createSession reverted on-chain')

        session_id = None
        for log in receipt1.logs:
            try:
                evt = self._registry.events.SessionCreated().process_log(log)
                session_id = evt['args']['sessionId']
                break
            except Exception:
                pass
        if session_id is None:
            raise RuntimeError('SessionCreated event not found in receipt')

        # 6. Get relay token
        relay_token = None
        deadline = time.time() + 120
        while time.time() < deadline:
            r = req.get(
                f'{AIVM_GATEWAY}/api/sessions/{session_id}/token',
                headers=self._auth_headers(), timeout=10,
            )
            if r.status_code == 200:
                d = r.json()
                if d.get('token'):
                    relay_token = d['token']
                    break
            time.sleep(1)
        if not relay_token:
            raise RuntimeError('Relay token not ready within 30s')

        # 7. Open WebSocket relay
        chunks   = []
        ws_ready = threading.Event()
        ws_err   = [None]

        def _on_message(ws_obj, message):
            try:
                frame   = json.loads(message)
                payload = frame.get('payload')
                if not payload:
                    return
                blob = base64.b64decode(payload)
                try:
                    pt = _aivm_aes_decrypt(session_key, blob)
                    chunks.append(pt.decode('utf-8', errors='replace'))
                except Exception:
                    pass
            except Exception:
                pass

        def _on_open(ws_obj):
            ws_ready.set()

        def _on_error(ws_obj, err):
            ws_err[0] = err
            ws_ready.set()

        ws = _ws.WebSocketApp(
            f'{AIVM_RELAY}?token={url_quote(relay_token)}',
            on_message=_on_message,
            on_open=_on_open,
            on_error=_on_error,
        )
        ws_thread = threading.Thread(target=ws.run_forever, daemon=True)
        ws_thread.start()
        ws_ready.wait(timeout=15)
        if ws_err[0]:
            raise RuntimeError(f'WebSocket failed: {ws_err[0]}')

        # 8. Encrypt + upload prompt blob
        cipher = _aivm_aes_encrypt(session_key, prompt.encode('utf-8'))
        r = req.post(
            f'{AIVM_GATEWAY}/api/blobs',
            json={'data': base64.b64encode(cipher).decode()},
            headers=self._auth_headers(), timeout=15,
        )
        r.raise_for_status()
        blob_hashes = r.json().get('blobHashes', [])
        if not blob_hashes:
            raise RuntimeError('No blob hash returned from gateway')
        prompt_hash = bytes.fromhex(_h(blob_hashes[0]).zfill(64))

        # 9. submitJob (pay 0.02 LCAI)
        nonce_val2 = self._pending_nonce()
        tx2 = self._registry.functions.submitJob(
            session_id, prompt_hash,
        ).build_transaction({
            'from':     self._account.address,
            'nonce':    nonce_val2,
            'gas':      500_000,
            'gasPrice': int(self._w3.eth.gas_price * 1.1),
            'value':    AIVM_JOB_FEE,
            'chainId':  AIVM_CHAIN_ID,
        })
        signed2  = self._account.sign_transaction(tx2)
        tx_hash2 = self._send_raw_with_retry(signed2)
        receipt2 = self._w3.eth.wait_for_transaction_receipt(tx_hash2, timeout=90)
        if receipt2.status != 1:
            raise RuntimeError('submitJob reverted — check LCAI balance')

        job_id = None
        for log in receipt2.logs:
            try:
                evt = self._registry.events.JobSubmitted().process_log(log)
                job_id = evt['args']['jobId']
                break
            except Exception:
                pass
        if job_id is None:
            raise RuntimeError('JobSubmitted event not found in receipt')

        # 10. Poll for JobCompleted, collect relay data
        job_completed_topic = '0x' + Web3.keccak(text='JobCompleted(uint256,address,bytes32,bytes32)').hex()
        job_id_topic = '0x' + hex(job_id)[2:].zfill(64)
        done     = False
        deadline = time.time() + timeout_secs
        while time.time() < deadline and not done:
            time.sleep(5)
            # Return early if relay already delivered chunks
            if chunks:
                print(f'[AIVM] relay data arrived ({len(chunks)} chunks), returning early')
                done = True
                break
            try:
                head = self._w3.eth.block_number
                logs = self._w3.eth.get_logs({
                    'address':   Web3.to_checksum_address(AIVM_JOB_REG),
                    'fromBlock': receipt2.blockNumber,
                    'toBlock':   head,
                    'topics':    [job_completed_topic, job_id_topic],
                })
                if logs:
                    done = True
                    print(f'[AIVM] JobCompleted on-chain!')
            except Exception as e:
                print(f'[AIVM] log poll error (retrying): {e}')

        time.sleep(4)  # grace period for final relay frames
        ws.close()
        result = ''.join(chunks)
        if result:
            print(f'[AIVM] inference done, {len(result)} chars')
            return result
        if not done:
            raise RuntimeError(f'Timeout after {timeout_secs}s waiting for JobCompleted')
        return result or 'Sorry, the AI completed but returned no response. Please try again.'


# Lazy singleton so key is only loaded once
_aivm_client = None

def _get_aivm_client():
    global _aivm_client
    if _aivm_client is None:
        if not PRIVATE_KEY:
            raise RuntimeError('LIGHTCHAIN_PRIVATE_KEY not set')
        _aivm_client = AIVMClient(PRIVATE_KEY)
    return _aivm_client

def run_aivm_inference(user_message: str, mode: str = 'chat', history: list = None) -> str:
    """Run one inference through Lightchain AIVM. Returns plain text reply.

    history: optional list of {"role": "user"|"assistant", "content": "..."} dicts
             representing the prior conversation turns to include as context.
    """
    try:
        mode_context = {
            'brainstorm':   '\n[MODE: BRAINSTORM — help generate dApp ideas]',
            'build':        '\n[MODE: BUILD — help plan and build a specific dApp]',
            'troubleshoot': '\n[MODE: TROUBLESHOOT — diagnose and fix a problem]',
            'launchcheck':  '\n[MODE: LAUNCHCHECK — final pre-launch review using automated scan results]',
        }.get(mode, '')

        # Build conversation history block if prior turns exist
        history_block = ''
        if history:
            lines = []
            for turn in history:
                label = 'User' if turn.get('role') == 'user' else 'Assistant'
                lines.append(f'{label}: {turn.get("content", "")}')
            history_block = '\n\n[PRIOR CONVERSATION — for context only]\n' + '\n'.join(lines) + '\n[END PRIOR CONVERSATION]\n'

        full_prompt = f'{SYSTEM_PROMPT}{mode_context}{history_block}\n\nUser: {user_message}'
        client = _get_aivm_client()
        reply  = client.run_inference(full_prompt)
        return reply if reply else 'I received your message but the response was empty. Please try again.'
    except Exception as e:
        print(f'[AIVM ERROR] {e}')
        return ('The AI is temporarily unavailable (network or AIVM issue). '
                'Please try again in a moment.')


def _DEAD_CODE_old_run_aivm():
    """Old implementation kept for reference — DO NOT USE."""
    try:
        from web3 import Web3
        from eth_account import Account
        acct = Account.from_key(PRIVATE_KEY)
        w3 = Web3()

        # 1. Auth challenge
        ch = req.post(f'{AIVM_GATEWAY}/api/auth/challenge',
                      json={'address': acct.address}, timeout=30).json()
        msg_to_sign = ch.get('challenge') or ch.get('message') or ch['siweMessage']
        signed = acct.sign_message(encode_defunct(text=msg_to_sign))
        sig_hex = '0x' + signed.signature.hex()

        auth = req.post(f'{AIVM_GATEWAY}/api/auth/verify',
                        json={'message': msg_to_sign, 'signature': sig_hex}, timeout=30).json()
        jwt = auth.get('token') or auth.get('accessToken') or auth.get('jwt')
        headers = {'Authorization': f'Bearer {jwt}'}

        # 2. Select worker
        models = req.get(f'{AIVM_GATEWAY}/api/models', headers=headers, timeout=30).json()
        model_list = models if isinstance(models, list) else models.get('models', [])
        model_id = next((m.get('id') or m.get('modelId') for m in model_list
                         if 'llama3' in str(m).lower()), None)
        if not model_id:
            model_id = model_list[0].get('id') if model_list else 'llama3-8b'

        sel = req.post(f'{AIVM_GATEWAY}/api/sessions/select',
                       json={'modelId': model_id}, headers=headers, timeout=30).json()
        worker_addr = sel.get('worker') or sel.get('workerAddress')
        session_id = sel.get('sessionId') or sel.get('id') or secrets.token_hex(16)

        # 3. Prepare session (get worker ECDH pub key)
        prep = req.post(f'{AIVM_GATEWAY}/api/sessions/prepare',
                        json={'sessionId': session_id, 'worker': worker_addr},
                        headers=headers, timeout=30).json()
        worker_pub_hex = (prep.get('workerPublicKey') or prep.get('encryptionPublicKey', ''))
        if worker_pub_hex.startswith('0x'):
            worker_pub_hex = worker_pub_hex[2:]
        worker_pub_bytes = bytes.fromhex(worker_pub_hex)

        # 4. Generate ephemeral ECDH key pair
        eph_priv = generate_private_key(SECP256K1(), default_backend())
        eph_pub_bytes = eph_priv.public_key().public_bytes(Encoding.X962,
                                                            PublicFormat.UncompressedPoint)
        eph_pub_hex = '0x' + eph_pub_bytes.hex()

        from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey
        from cryptography.hazmat.primitives.serialization import load_der_public_key
        worker_pub_obj = EllipticCurvePublicKey
        # Load worker pub key
        from cryptography.hazmat.primitives.asymmetric.ec import (
            EllipticCurvePublicNumbers, SECP256K1
        )
        from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
        # Use raw X962 uncompressed bytes
        from cryptography.hazmat.primitives.asymmetric.ec import (
            EllipticCurvePublicKey
        )
        from cryptography.hazmat.primitives.serialization import load_der_public_key

        # Build DER-encoded public key — handle both compressed (33 bytes) and uncompressed (65 bytes)
        klen = len(worker_pub_bytes)
        if klen == 65:
            # Uncompressed: 04 + x(32) + y(32) → BIT STRING = 66 bytes
            oid_header = bytes.fromhex('3056301006072a8648ce3d020106052b8104000a034200')
        elif klen == 33:
            # Compressed: 02/03 + x(32) → BIT STRING = 34 bytes
            oid_header = bytes.fromhex('3036301006072a8648ce3d020106052b8104000a032200')
        else:
            raise ValueError(f'Unexpected worker public key length: {klen} bytes')
        der_pub = oid_header + worker_pub_bytes
        wpk = load_der_public_key(der_pub, backend=default_backend())
        shared = eph_priv.exchange(ECDH(), wpk)
        aes_key = shared[:32]

        # 5. Create session on-chain (free tx)
        model_hash = w3.keccak(text=model_id)
        nonce = w3.eth.get_transaction_count(acct.address)
        gas_price = w3.eth.gas_price

        CREATE_SESSION_SIG = w3.keccak(text='createSession(bytes32,address,bytes)')[:4]
        encoded_args = (
            model_hash +
            bytes.fromhex('000000000000000000000000' + worker_addr[2:]) +
            b'\x00' * 28 + (96).to_bytes(4, 'big') +
            b'\x00' * 28 + len(eph_pub_bytes).to_bytes(4, 'big') +
            eph_pub_bytes + b'\x00' * ((32 - len(eph_pub_bytes) % 32) % 32)
        )
        tx = {
            'from': acct.address,
            'to': JOB_REGISTRY,
            'data': '0x' + CREATE_SESSION_SIG.hex() + encoded_args.hex(),
            'nonce': nonce,
            'gas': 300000,
            'gasPrice': gas_price,
            'chainId': CHAIN_ID,
        }
        signed_tx = acct.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        # Extract session ID from logs
        real_session_id = session_id
        for log in receipt.logs:
            if len(log.data) >= 32:
                real_session_id = '0x' + log.data.hex()[:64]
                break

        # 6. Get relay token
        for attempt in range(20):
            tok = req.get(f'{AIVM_GATEWAY}/api/sessions/{real_session_id}/token',
                          headers=headers, timeout=15).json()
            relay_token = tok.get('token') or tok.get('relayToken')
            if relay_token:
                break
            time.sleep(3)

        # 7. Encrypt prompt and upload blob
        mode_context = {
            'brainstorm': '\n[MODE: BRAINSTORM — help generate dApp ideas]',
            'build': '\n[MODE: BUILD — help plan and build a specific dApp]',
            'troubleshoot': '\n[MODE: TROUBLESHOOT — diagnose and fix a problem]',
        }.get(mode, '')
        full_prompt = f'{SYSTEM_PROMPT}{mode_context}\n\nUser: {user_message}'

        iv = secrets.token_bytes(12)
        aesgcm = AESGCM(aes_key)
        ciphertext = aesgcm.encrypt(iv, full_prompt.encode('utf-8'), None)
        blob_payload = base64.b64encode(eph_pub_bytes + iv + ciphertext).decode()

        blob_resp = req.post(f'{AIVM_GATEWAY}/api/blobs',
                             json={'data': blob_payload, 'sessionId': real_session_id},
                             headers=headers, timeout=30).json()
        blob_cid = blob_resp.get('cid') or blob_resp.get('blobCid') or blob_resp.get('id', '')

        # 8. Submit job on-chain
        JOB_FEE = 20000000000000000  # 0.02 LCAI
        SUBMIT_JOB_SIG = w3.keccak(text='submitJob(bytes32,bytes32)')[:4]
        session_bytes = bytes.fromhex(real_session_id[2:] if real_session_id.startswith('0x')
                                       else real_session_id)
        blob_bytes = blob_cid.encode() if len(blob_cid) < 32 else bytes.fromhex(
            blob_cid[2:] if blob_cid.startswith('0x') else blob_cid)
        job_data = SUBMIT_JOB_SIG + session_bytes[:32].ljust(32, b'\x00') + blob_bytes[:32].ljust(32, b'\x00')
        nonce2 = w3.eth.get_transaction_count(acct.address)
        tx2 = {
            'from': acct.address,
            'to': JOB_REGISTRY,
            'data': '0x' + job_data.hex(),
            'value': JOB_FEE,
            'nonce': nonce2,
            'gas': 200000,
            'gasPrice': gas_price,
            'chainId': CHAIN_ID,
        }
        signed_tx2 = acct.sign_transaction(tx2)
        w3.eth.send_raw_transaction(signed_tx2.raw_transaction)

        # 9. Receive response via WebSocket
        response_chunks = []
        done_event = th.Event()

        def on_message(ws, message):
            try:
                data = json.loads(message)
                if data.get('type') == 'chunk':
                    enc = base64.b64decode(data['data'])
                    iv_r, ct_r = enc[:12], enc[12:]
                    chunk = aesgcm.decrypt(iv_r, ct_r, None).decode('utf-8', errors='replace')
                    response_chunks.append(chunk)
                elif data.get('type') in ('done', 'complete', 'end'):
                    done_event.set()
            except Exception:
                pass

        def on_error(ws, error):
            done_event.set()

        def on_open(ws):
            ws.send(json.dumps({'type': 'auth', 'token': relay_token,
                                'sessionId': real_session_id}))

        ws = websocket.WebSocketApp(
            AIVM_RELAY,
            on_message=on_message,
            on_error=on_error,
            on_open=on_open,
        )
        wst = th.Thread(target=lambda: ws.run_forever(), daemon=True)
        wst.start()
        done_event.wait(timeout=90)
        ws.close()

        reply = ''.join(response_chunks).strip()
        return reply if reply else 'I received your message but the response was empty. Please try again.'

    except Exception as e:
        print(f'[AIVM ERROR] {e}')
        return ('The AI is temporarily unavailable (network or AIVM issue). '
                'Please try again in a moment.')


# ════════════════════════════════════════════════════════════════════════
# THREADING HTTP SERVER + JOB STORE
# ════════════════════════════════════════════════════════════════════════

class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """Handles each request in its own thread so AIVM jobs don't block polling."""
    daemon_threads = True


# In-memory job store: job_id -> {status, reply, error, created}
_jobs: dict = {}
_jobs_lock = threading.Lock()

# Conversation history store: session_id -> [{"role": "user"|"assistant", "content": "..."}]
# Keeps the last 6 exchanges (12 messages) per session to give the AI context.
_sessions: dict = {}
_sessions_lock = threading.Lock()


def _start_job(message: str, mode: str, session_id: str = None) -> str:
    """Launch AIVM inference in background; return job_id immediately.

    session_id: if provided, loads prior conversation turns as context and
                appends the new exchange to the session history on completion.
    """
    job_id = secrets.token_hex(10)
    with _jobs_lock:
        _jobs[job_id] = {'status': 'pending', 'reply': None, 'error': None,
                         'created': time.time()}
    # Remove stale jobs (older than 15 minutes)
    cutoff = time.time() - 900
    with _jobs_lock:
        stale = [k for k, v in _jobs.items() if v['created'] < cutoff]
        for k in stale:
            del _jobs[k]

    # Snapshot history for this session (copy so background thread has stable data)
    history = []
    if session_id:
        with _sessions_lock:
            history = list(_sessions.get(session_id, []))

    def _worker():
        try:
            reply = run_aivm_inference(message, mode, history)
            with _jobs_lock:
                if job_id in _jobs:
                    _jobs[job_id]['status'] = 'done'
                    _jobs[job_id]['reply']  = reply
            # Store this exchange in session history
            if session_id and reply:
                with _sessions_lock:
                    if session_id not in _sessions:
                        _sessions[session_id] = []
                    _sessions[session_id].append({'role': 'user',      'content': message})
                    _sessions[session_id].append({'role': 'assistant', 'content': reply})
                    # Cap at last 12 messages (6 back-and-forth exchanges)
                    if len(_sessions[session_id]) > 12:
                        _sessions[session_id] = _sessions[session_id][-12:]
        except Exception as e:
            print(f'[JOB {job_id}] error: {e}')
            with _jobs_lock:
                if job_id in _jobs:
                    _jobs[job_id]['status'] = 'error'
                    _jobs[job_id]['error']  = str(e)[:300]

    threading.Thread(target=_worker, daemon=True).start()
    return job_id


# ════════════════════════════════════════════════════════════════════════
# LAUNCH CHECK — automated pre-launch scanner
# ════════════════════════════════════════════════════════════════════════

_LAUNCH_PATTERNS = [
    ('critical', 'localhost API URL',
     _re.compile(r'https?://localhost[:\d]*|localhost:\d+', _re.I),
     'Your website is trying to talk to your own computer — strangers cannot reach it.',
     'localhost_backend'),
    ('critical', '127.0.0.1 API URL',
     _re.compile(r'https?://127\.0\.0\.1[:\d]*', _re.I),
     'Same problem as localhost — only works on your PC.',
     'localhost_backend'),
    ('critical', 'Placeholder backend URL',
     _re.compile(r'your-railway-url|YOUR_RAILWAY|REPLACE_ME|example\.com/api', _re.I),
     'The server address in your code is still a placeholder — not a real internet address.',
     'update_server_address'),
    ('warning', 'HTTP API from HTTPS site',
     _re.compile(r'fetch\s*\(\s*["\']http://(?!localhost)', _re.I),
     'Your secure website may be blocked from calling an insecure http address.',
     'use_https_url'),
    ('warning', 'Generic React app title',
     _re.compile(r'<title>React App</title>|Create React App Sample', _re.I),
     'Browser tab still says "React App" — looks unfinished to visitors.',
     'fix_app_title'),
    ('warning', 'Hardcoded API port',
     _re.compile(r'fetch\s*\([^)]*:(3000|3001|5000|8000|8080|8187)', _re.I),
     'Your code points at a developer-only port — probably not on the internet yet.',
     'localhost_backend'),
    ('info', 'LCAI payment detected',
     _re.compile(r'parseEther|sendTransaction|LCAI', _re.I),
     'Users can pay real LCAI — make sure they get what they paid for before you announce.',
     'payment_safety'),
    ('info', 'Wallet connect present',
     _re.compile(r'eth_requestAccounts|window\.ethereum', _re.I),
     'Wallet connection looks wired up — good.',
     None),
]

# Beginner-friendly fix playbooks returned with every scan (non-nerd language)
_LAUNCH_FIX_PLAYBOOKS = {
    'localhost_backend': {
        'id': 'localhost_backend',
        'emoji': '🧠',
        'title': 'Put your app\'s "brain" on the internet',
        'why': 'Your website is online (Vercel/GitHub Pages) but the AI/music/data part still lives on YOUR computer. When a friend opens your link, their phone looks for a server on THEIR computer — and finds nothing.',
        'steps': [
            {'num': 1, 'title': 'Find your server folder on your PC',
             'do': 'This is the folder you run with npm start or python server.py — NOT the folder you uploaded to Vercel. It often has files like server.js, server.py, or an api/ folder.',
             'check': 'You can point to the folder that must be running locally for your app to work today.'},
            {'num': 2, 'title': 'Put that server folder on GitHub',
             'do': 'Open GitHub Desktop → File → Add Local Repository → pick your SERVER folder → Publish repository. Name it something like myapp-server.',
             'check': 'You see the folder on github.com when you log in.'},
            {'num': 3, 'title': 'Connect Railway to that repo',
             'do': 'Go to railway.app → sign up → New Project → Deploy from GitHub → pick your SERVER repo. Wait ~2 minutes for the green "Deployed" status.',
             'check': 'Railway shows your project running. Click it → Settings → Networking → copy the public URL (starts with https:// and ends in .up.railway.app).'},
            {'num': 4, 'title': 'Copy your Railway address',
             'do': 'Save that https://....up.railway.app URL in a notepad. This is your server\'s new home on the internet. Test it: paste it in your browser and add /api/health or / if you have one — you should NOT see "connection refused".',
             'check': 'The Railway URL loads something (even an error page from YOUR server is OK — it proves the server is online).'},
            {'num': 5, 'title': 'Replace localhost in your WEBSITE code',
             'do': 'Open your WEBSITE project in VS Code (the one on Vercel). Press Ctrl+Shift+F (Cmd+Shift+F on Mac) → search for localhost → replace every http://localhost:3001 (or similar) with your Railway https:// URL. Save all files.',
             'check': 'Searching your website code for "localhost" finds zero results.'},
            {'num': 6, 'title': 'Put your updated website back online',
             'do': 'If Vercel: push to GitHub (GitHub Desktop → Commit → Push) and Vercel auto-updates in ~1 min. If GitHub Pages: same push workflow. Or click Redeploy in the Vercel dashboard.',
             'check': 'Your live URL shows a new deploy timestamp or you pushed in the last few minutes.'},
            {'num': 7, 'title': 'Test the RIGHT way (important!)',
             'do': 'Do NOT test on the same PC where your local server runs. Use your phone on cellular data (turn WiFi OFF) or send the link to a friend. Try the full flow: lyrics/AI → pay → download.',
             'check': 'Someone who is NOT you can complete the full flow without errors.'},
            {'num': 8, 'title': 'Run Launch Check again',
             'do': 'Come back here → paste the same live URL → Run Launch Check. Critical issues should be gone.',
             'check': 'Launch Check says READY or READY WITH WARNINGS (not NOT READY).'},
        ],
    },
    'update_server_address': {
        'id': 'update_server_address',
        'emoji': '🔗',
        'title': 'Swap the placeholder server address for your real one',
        'why': 'Your code still says "your-railway-url" or similar — that is not a real address. You need the https://....up.railway.app link from Railway.',
        'steps': [
            {'num': 1, 'title': 'Get your real Railway URL', 'do': 'railway.app → your project → Settings → Networking → copy the https URL.', 'check': 'You have a URL ending in .up.railway.app copied.'},
            {'num': 2, 'title': 'Find and replace the placeholder', 'do': 'VS Code → open website folder → Ctrl+Shift+F → search your-railway-url or REPLACE_ME → paste your real Railway URL → Save.', 'check': 'No placeholders left in your code.'},
            {'num': 3, 'title': 'Redeploy your website', 'do': 'GitHub Desktop → Commit → Push (or Vercel Redeploy).', 'check': 'Live site updated.'},
        ],
    },
    'fix_app_title': {
        'id': 'fix_app_title',
        'emoji': '🏷️',
        'title': 'Give your app a real name in the browser tab',
        'why': 'Visitors still see "React App" in the tab — looks like a demo, not a finished product.',
        'steps': [
            {'num': 1, 'title': 'Change the title', 'do': 'In your website folder, open public/index.html (React) or index.html → change <title>React App</title> to your app name like <title>LyricsAI</title>.', 'check': 'Browser tab shows your app name after redeploy.'},
            {'num': 2, 'title': 'Redeploy', 'do': 'Push to GitHub or redeploy on Vercel.', 'check': 'Live site tab shows the new name.'},
        ],
    },
    'payment_safety': {
        'id': 'payment_safety',
        'emoji': '💸',
        'title': 'Protect paying users',
        'why': 'Your app charges LCAI. If the server/AI part is broken, users could pay and get nothing.',
        'steps': [
            {'num': 1, 'title': 'Fix the server first', 'do': 'Complete the "brain on the internet" steps above BEFORE telling anyone to pay.', 'check': 'AI/music/features work from a friend\'s phone without your PC running.'},
            {'num': 2, 'title': 'Test a real payment on testnet or small amount', 'do': 'Do one full pay → receive flow yourself from a phone, not your dev PC.', 'check': 'Payment completes AND the user gets the song/feature/download.'},
        ],
    },
    'test_properly': {
        'id': 'test_properly',
        'emoji': '📱',
        'title': 'Test like a real user',
        'why': 'Testing on your own PC while your local server runs gives a false "it works!" result.',
        'steps': [
            {'num': 1, 'title': 'Phone on cellular', 'do': 'Turn OFF WiFi on your phone → open your live URL → try the full app.', 'check': 'Works without your PC turned on or server running locally.'},
            {'num': 2, 'title': 'Or ask a friend', 'do': 'Send them the link directly — ask "does the AI/music work for you?"', 'check': 'They confirm yes before you share it publicly.'},
        ],
    },
    'use_https_url': {
        'id': 'use_https_url',
        'emoji': '🔒',
        'title': 'Use https:// for your server address',
        'why': 'Secure websites (Vercel/GitHub) often block calls to plain http:// addresses.',
        'steps': [
            {'num': 1, 'title': 'Check your server URL starts with https://', 'do': 'Railway gives you https automatically — make sure your code uses that full URL, not http://.', 'check': 'Every fetch() in your code uses https://.'},
        ],
    },
}

_FIX_PLAN_ORDER = [
    'localhost_backend', 'update_server_address', 'use_https_url',
    'payment_safety', 'fix_app_title', 'test_properly',
]

_BLOCKED_FETCH_HOSTS = (
    'localhost', '127.0.0.1', '0.0.0.0', '[::1]',
)


def _is_safe_public_url(url: str) -> bool:
    """Reject SSRF targets — only allow public http(s) URLs."""
    try:
        p = urlparse(url.strip())
    except Exception:
        return False
    if p.scheme not in ('http', 'https'):
        return False
    host = (p.hostname or '').lower()
    if not host or host in _BLOCKED_FETCH_HOSTS:
        return False
    if host.endswith('.local') or host.endswith('.internal'):
        return False
    # Block private IP ranges
    if _re.match(r'^10\.', host):
        return False
    if _re.match(r'^192\.168\.', host):
        return False
    if _re.match(r'^172\.(1[6-9]|2\d|3[01])\.', host):
        return False
    return True


def _http_get_text(url: str, max_bytes: int = 2_500_000, timeout: int = 20) -> str:
    import urllib.request
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'OrcaAppBuilder-LaunchCheck/1.0'},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read(max_bytes + 1)
    if len(data) > max_bytes:
        data = data[:max_bytes]
    return data.decode('utf-8', errors='replace')


def scan_text_for_launch_issues(text: str, source: str) -> list:
    if not text:
        return []
    findings = []
    seen = set()
    for severity, title, pattern, detail, fix_id in _LAUNCH_PATTERNS:
        for m in pattern.finditer(text):
            snippet = text[max(0, m.start() - 30):m.end() + 40].replace('\n', ' ').strip()
            key = (severity, title, snippet[:80])
            if key in seen:
                continue
            seen.add(key)
            findings.append({
                'severity': severity,
                'title': title,
                'detail': detail,
                'source': source,
                'snippet': snippet[:160],
                'fix_id': fix_id,
            })
    return findings


def _detect_app_profile(all_text: str, url: str = '') -> dict:
    """Guess what kind of app this is — works on any public URL, not just OrcaAppBuilder apps."""
    t = (all_text or '').lower()
    u = (url or '').lower()
    profile = {
        'is_lightchain': bool(_re.search(
            r'lightchain|lcai|0x23f0|chainid["\']?\s*[:=]\s*9200|9200|lightscan|mainnet\.lightchain',
            t, _re.I)),
        'has_wallet': bool(_re.search(r'eth_requestaccounts|window\.ethereum|wagmi|walletconnect', t, _re.I)),
        'has_lcai_payments': bool(_re.search(r'parseether|sendtransaction|lcai', t, _re.I)),
        'has_aivm_or_ai_api': bool(_re.search(r'/api/lyrics|/api/music|/api/chat|aivm|openai|generat', t, _re.I)),
        'hosting': (
            'vercel' if 'vercel.app' in u else
            'github_pages' if 'github.io' in u else
            'custom' if url else 'unknown'
        ),
        'stack_hint': (
            'react' if 'react app' in t or 'webpackchunk' in t or 'create-react-app' in t else
            'vite' if '/assets/index-' in t and 'vite' in t else
            'html' if '<html' in t and 'react' not in t else
            'unknown'
        ),
    }
    tags = []
    if profile['is_lightchain']:
        tags.append('Lightchain dApp')
    if profile['has_wallet']:
        tags.append('wallet connect')
    if profile['has_lcai_payments']:
        tags.append('LCAI payments')
    if profile['has_aivm_or_ai_api']:
        tags.append('AI/features API')
    if profile['hosting'] == 'vercel':
        tags.append('hosted on Vercel')
    elif profile['hosting'] == 'github_pages':
        tags.append('hosted on GitHub Pages')
    profile['detected_summary'] = ', '.join(tags) if tags else 'web app (generic)'
    profile['orcaappbuilder_required'] = False
    return profile


def _build_fix_plan(findings: list, url: str = '') -> list:
    """Ordered beginner fix playbooks based on what the scan found."""
    needed = set()
    for f in findings:
        fid = f.get('fix_id')
        if fid:
            needed.add(fid)
    if any(f.get('fix_id') == 'localhost_backend' for f in findings):
        needed.add('test_properly')
    plan = []
    for fid in _FIX_PLAN_ORDER:
        if fid in needed and fid in _LAUNCH_FIX_PLAYBOOKS:
            plan.append(_LAUNCH_FIX_PLAYBOOKS[fid])
    return plan


def _plain_summary(findings: list, url: str, verdict_hint: str, app_profile: dict = None) -> str:
    """One-paragraph explanation for non-technical builders."""
    app_profile = app_profile or {}
    detected = app_profile.get('detected_summary', 'this app')
    has_localhost = any(
        f.get('fix_id') == 'localhost_backend' for f in findings if f.get('severity') == 'critical'
    )
    has_payment = any(f.get('fix_id') == 'payment_safety' for f in findings)
    if has_localhost:
        base = (
            f'The site loads, but AI/features still call the builder\'s home computer — not the internet. '
            f'Only works while their PC runs the server.'
        )
        if has_payment:
            base += ' Users could pay LCAI and get nothing until fixed.'
        return base
    if verdict_hint == 'NOT READY':
        return 'Problems found that will break this app for other people. Follow the fix steps below before going live.'
    if verdict_hint == 'READY WITH WARNINGS':
        return 'Your app may work for others, but polish the warnings below before a big announcement.'
    return 'No major blockers found in the automatic scan — still test from a friend\'s phone, then run Launch Check again.'


def scan_live_url(url: str) -> dict:
    """Fetch a public URL and scan HTML + linked JS bundles."""
    if not _is_safe_public_url(url):
        return {'ok': False, 'error': 'Invalid or non-public URL', 'findings': [], 'sources': []}

    sources = []
    all_findings = []
    try:
        html = _http_get_text(url)
        sources.append({'type': 'html', 'url': url, 'bytes': len(html)})
        all_findings.extend(scan_text_for_launch_issues(html, f'Live site HTML ({url})'))

        # Collect script src URLs from HTML
        script_srcs = _re.findall(
            r'<script[^>]+src=["\']([^"\']+\.js[^"\']*)["\']', html, _re.I)
        base = url.rstrip('/')
        js_urls = []
        for src in script_srcs:
            if src.startswith('http'):
                js_urls.append(src)
            elif src.startswith('/'):
                p = urlparse(url)
                js_urls.append(f'{p.scheme}://{p.netloc}{src}')
            else:
                js_urls.append(f'{base}/{src}')

        combined_text = html

        # Prefer main.*.js bundles (Create React App / Vite)
        js_urls.sort(key=lambda u: (0 if 'main.' in u else 1, u))
        for js_url in js_urls[:4]:
            try:
                js = _http_get_text(js_url, max_bytes=4_000_000)
                combined_text += '\n' + js
                sources.append({'type': 'javascript', 'url': js_url, 'bytes': len(js)})
                all_findings.extend(scan_text_for_launch_issues(js, f'JS bundle ({js_url})'))
            except Exception as e:
                sources.append({'type': 'javascript', 'url': js_url, 'error': str(e)[:120]})

        return {
            'ok': True,
            'url': url,
            'findings': all_findings,
            'sources': sources,
            'combined_text': combined_text,
            'critical_count': sum(1 for f in all_findings if f['severity'] == 'critical'),
            'warning_count': sum(1 for f in all_findings if f['severity'] == 'warning'),
        }
    except Exception as e:
        return {'ok': False, 'error': str(e)[:300], 'findings': all_findings, 'sources': sources}


def run_launch_scan(url: str = '', code: str = '', notes: str = '') -> dict:
    """Combine URL fetch scan + pasted code scan. Works on ANY public app URL."""
    findings = []
    sources_scanned = []
    combined_text = ''

    url = (url or '').strip()
    code = (code or '').strip()
    notes = (notes or '').strip()

    if url:
        url_result = scan_live_url(url)
        findings.extend(url_result.get('findings') or [])
        sources_scanned.extend(url_result.get('sources') or [])
        combined_text += url_result.get('combined_text') or ''
        if not url_result.get('ok'):
            findings.append({
                'severity': 'warning',
                'title': 'Could not fully scan live URL',
                'detail': url_result.get('error', 'Fetch failed — paste your code below instead.'),
                'source': 'URL fetch',
                'snippet': url,
            })
    if code:
        sources_scanned.append({'type': 'pasted_code', 'bytes': len(code)})
        findings.extend(scan_text_for_launch_issues(code, 'Pasted code'))
        combined_text += '\n' + code

    if not url and not code:
        return {'ok': False, 'error': 'Enter your live URL and/or paste code to scan.'}

    critical = [f for f in findings if f['severity'] == 'critical']
    warnings = [f for f in findings if f['severity'] == 'warning']
    infos    = [f for f in findings if f['severity'] == 'info']

    if not critical and not warnings and (url or code):
        findings.append({
            'severity': 'ok',
            'title': 'No automatic blockers detected',
            'detail': 'Static scan did not find localhost or placeholder URLs. Still run the AI review and test from another device.',
            'source': 'Scanner',
            'snippet': '',
        })

    verdict_hint = 'NOT READY' if critical else ('READY WITH WARNINGS' if warnings else 'LIKELY OK — VERIFY MANUALLY')
    fix_plan = _build_fix_plan(findings, url)
    app_profile = _detect_app_profile(combined_text, url)

    return {
        'ok': True,
        'verdict_hint': verdict_hint,
        'plain_summary': _plain_summary(findings, url, verdict_hint, app_profile),
        'app_profile': app_profile,
        'critical_count': len(critical),
        'warning_count': len(warnings),
        'findings': findings,
        'fix_plan': fix_plan,
        'sources_scanned': sources_scanned,
        'notes': notes,
        'url': url,
        'any_app_ok': True,
    }


# ════════════════════════════════════════════════════════════════════════
# HTTP SERVER
# ════════════════════════════════════════════════════════════════════════

class OrcaAppHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f'[{self.address_string()}] {fmt % args}')

    def send_json(self, status: int, data: dict):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path

        if path == '/api/health':
            self.send_json(200, {
                'status':  'ok',
                'service': 'orcaapp',
                'version': '1.0.0',
                'aivm':    'ready' if PRIVATE_KEY else 'no key',
                'jobs':    len(_jobs),
            })

        elif path == '/api/chat/status':
            qs     = parse_qs(parsed.query)
            job_id = (qs.get('job_id') or [''])[0].strip()
            with _jobs_lock:
                job = _jobs.get(job_id)
            if not job:
                self.send_json(404, {'error': 'job not found'})
                return
            self.send_json(200, {
                'status': job['status'],
                'reply':  job.get('reply'),
                'error':  job.get('error'),
            })

        else:
            self.send_json(404, {'error': 'not found'})

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length) if length else b'{}'

        try:
            data = json.loads(body)
        except Exception:
            self.send_json(400, {'error': 'invalid JSON'})
            return

        if path == '/api/launchcheck/scan':
            url   = (data.get('url') or '').strip()
            code  = (data.get('code') or '').strip()
            notes = (data.get('notes') or '').strip()
            result = run_launch_scan(url=url, code=code, notes=notes)
            status = 200 if result.get('ok') else 400
            self.send_json(status, result)
            return

        if path == '/api/chat':
            message    = (data.get('message') or data.get('prompt') or '').strip()
            mode       = (data.get('mode') or 'chat').strip().lower()
            session_id = (data.get('session_id') or '').strip() or None

            if not message:
                self.send_json(400, {'error': 'message required'})
                return
            if not PRIVATE_KEY:
                self.send_json(503, {'error': 'AI not configured — LIGHTCHAIN_PRIVATE_KEY not set'})
                return

            # Start AIVM in background; return job_id immediately
            # (avoids Railway 60s HTTP timeout on long AIVM calls)
            job_id = _start_job(message, mode, session_id)
            print(f'[JOB {job_id}] started — mode={mode}, session={session_id}, msg={message[:60]}')
            self.send_json(202, {'job_id': job_id, 'status': 'pending'})

        else:
            self.send_json(404, {'error': 'not found'})


def main():
    if not PRIVATE_KEY:
        print('[WARN] LIGHTCHAIN_PRIVATE_KEY not set — AI endpoints will return 503')
    server = ThreadingHTTPServer(('0.0.0.0', PORT), OrcaAppHandler)
    print(f'[OrcaApp] Server running on port {PORT}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[OrcaApp] Shutting down')


if __name__ == '__main__':
    main()
