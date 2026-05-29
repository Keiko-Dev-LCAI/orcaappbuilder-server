#!/usr/bin/env python3
"""
OrcaApp — dApp Builder Companion for Lightchain AI
Port 8187 | AI wizards via Lightchain AIVM

Handles all 4 modes: learn, brainstorm, build, troubleshoot.
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

== WHAT IS LIGHTCHAIN AI? ==
Lightchain AI is a blockchain (think of it as a shared public record-keeping system) that also has built-in AI. The AI part is called AIVM — it's a network of computers that process AI requests and get paid in LCAI tokens for doing so. You can build apps that use both the blockchain features AND the AI, all in one place.

== KEY FACTS ABOUT LIGHTCHAIN ==
- Chain ID: 9200 (this is just an ID number that wallets use to connect)
- RPC URL (the address your app uses to talk to the blockchain): https://rpc.mainnet.lightchain.ai
- Explorer (like a bank statement you can read — shows all transactions): https://mainnet.lightscan.app
- LCAI is the currency. People pay LCAI to use apps. Apps pay LCAI to use AI.
- Trust Wallet is the recommended wallet. There is NO official Lightchain wallet app.
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

== HOSTING — WHERE YOUR APP LIVES ==
Static apps (just HTML, no server needed) → GitHub Pages (FREE)
  - Push your index.html to a GitHub repo
  - Enable GitHub Pages in repo Settings
  - Your app is live at: yourusername.github.io/yourrepo

Apps that need a server (for AIVM, database, etc.) → Railway ($5/month)
  - Railway is like a computer in the cloud that runs your Python server 24/7
  - Connect your GitHub repo and Railway auto-deploys every time you push
  - NEVER run "railway up" from the command line — it gets overwritten on next auto-deploy
  - Always push to GitHub instead

Custom domain (yourapp.ai) → Register at Cloudflare Registrar (~$15/year for .ai)
  - Then point it to your GitHub Pages or Railway URL using Cloudflare DNS

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

When mode is LEARN or CHAT: Answer questions about building on Lightchain. Be a knowledgeable friend, not a textbook. Give real examples from real apps.

Always be encouraging. Building a dApp for the first time is genuinely hard. Celebrate small wins. Remind them that every expert was once a beginner."""

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
        params_hash = bytes.fromhex(model_id.lstrip('0x').lstrip('0X').zfill(64))
        sig_bytes   = bytes.fromhex(prep['signature'].lstrip('0x').lstrip('0X'))
        gas_price   = self._w3.eth.gas_price
        nonce_val   = self._w3.eth.get_transaction_count(self._account.address)
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
        tx_hash  = self._w3.eth.send_raw_transaction(signed.raw_transaction)
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
        deadline = time.time() + 30
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
        prompt_hash = bytes.fromhex(blob_hashes[0].lstrip('0x').lstrip('0X').zfill(64))

        # 9. submitJob (pay 0.02 LCAI)
        nonce_val2 = self._w3.eth.get_transaction_count(self._account.address)
        tx2 = self._registry.functions.submitJob(
            session_id, prompt_hash,
        ).build_transaction({
            'from':     self._account.address,
            'nonce':    nonce_val2,
            'gas':      500_000,
            'gasPrice': gas_price,
            'value':    AIVM_JOB_FEE,
            'chainId':  AIVM_CHAIN_ID,
        })
        signed2  = self._account.sign_transaction(tx2)
        tx_hash2 = self._w3.eth.send_raw_transaction(signed2.raw_transaction)
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
        job_completed_topic = Web3.keccak(text='JobCompleted(uint256,address,bytes32,bytes32)').hex()
        job_id_topic = '0x' + hex(job_id)[2:].zfill(64)
        done     = False
        deadline = time.time() + timeout_secs
        while time.time() < deadline and not done:
            time.sleep(5)
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
            except Exception as e:
                print(f'[AIVM] log poll error: {e}')

        time.sleep(4)
        ws.close()
        result = ''.join(chunks)
        if result:
            return result
        if not done:
            raise RuntimeError(f'Timeout after {timeout_secs}s waiting for JobCompleted')
        return result


# Lazy singleton so key is only loaded once
_aivm_client = None

def _get_aivm_client():
    global _aivm_client
    if _aivm_client is None:
        if not PRIVATE_KEY:
            raise RuntimeError('LIGHTCHAIN_PRIVATE_KEY not set')
        _aivm_client = AIVMClient(PRIVATE_KEY)
    return _aivm_client

def run_aivm_inference(user_message: str, mode: str = 'chat') -> str:
    """Run one inference through Lightchain AIVM. Returns plain text reply."""
    try:
        mode_context = {
            'brainstorm': '\n[MODE: BRAINSTORM — help generate dApp ideas]',
            'build':      '\n[MODE: BUILD — help plan and build a specific dApp]',
            'troubleshoot': '\n[MODE: TROUBLESHOOT — diagnose and fix a problem]',
        }.get(mode, '')
        full_prompt = f'{SYSTEM_PROMPT}{mode_context}\n\nUser: {user_message}'
        client = _get_aivm_client()
        reply  = client.run_inference(full_prompt)
        return reply if reply else 'I received your message but the response was empty. Please try again.'
    except Exception as e:
        print(f'[AIVM ERROR] {e}')
        return (f'The AI is temporarily unavailable (network or AIVM issue). '
                f'Please try again in a moment. Error: {str(e)[:200]}')


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
        return (f'The AI is temporarily unavailable (network or AIVM issue). '
                f'Please try again in a moment. Error: {str(e)[:120]}')


# ════════════════════════════════════════════════════════════════════════
# THREADING HTTP SERVER + JOB STORE
# ════════════════════════════════════════════════════════════════════════

class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """Handles each request in its own thread so AIVM jobs don't block polling."""
    daemon_threads = True


# In-memory job store: job_id -> {status, reply, error, created}
_jobs: dict = {}
_jobs_lock = threading.Lock()


def _start_job(message: str, mode: str) -> str:
    """Launch AIVM inference in background; return job_id immediately."""
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

    def _worker():
        try:
            reply = run_aivm_inference(message, mode)
            with _jobs_lock:
                if job_id in _jobs:
                    _jobs[job_id]['status'] = 'done'
                    _jobs[job_id]['reply']  = reply
        except Exception as e:
            print(f'[JOB {job_id}] error: {e}')
            with _jobs_lock:
                if job_id in _jobs:
                    _jobs[job_id]['status'] = 'error'
                    _jobs[job_id]['error']  = str(e)[:300]

    threading.Thread(target=_worker, daemon=True).start()
    return job_id


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

        if path == '/api/chat':
            message = (data.get('message') or data.get('prompt') or '').strip()
            mode    = (data.get('mode') or 'chat').strip().lower()

            if not message:
                self.send_json(400, {'error': 'message required'})
                return
            if not PRIVATE_KEY:
                self.send_json(503, {'error': 'AI not configured — LIGHTCHAIN_PRIVATE_KEY not set'})
                return

            # Start AIVM in background; return job_id immediately
            # (avoids Railway 60s HTTP timeout on long AIVM calls)
            job_id = _start_job(message, mode)
            print(f'[JOB {job_id}] started — mode={mode}, msg={message[:60]}')
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
