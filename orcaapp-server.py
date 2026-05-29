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

from http.server import HTTPServer, BaseHTTPRequestHandler
import json, threading, time, secrets, base64, struct
from urllib.parse import urlparse

PORT = int(os.environ.get('PORT', 8187))
PRIVATE_KEY = os.environ.get('LIGHTCHAIN_PRIVATE_KEY', '')

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
# AIVM CLIENT — identical pattern to orcanode-server.py
# ════════════════════════════════════════════════════════════════════════

AIVM_GATEWAY    = 'https://chat-api.mainnet.lightchain.ai'
AIVM_RELAY      = 'wss://relay.mainnet.lightchain.ai/ws'
JOB_REGISTRY    = '0xfB15F90298e4CcD7106E76fFB5e520315cC42B0b'
CHAIN_ID        = 9200
RPC_URL         = 'https://rpc.mainnet.lightchain.ai'

def run_aivm_inference(user_message: str, mode: str = 'chat') -> str:
    """Run one inference through Lightchain AIVM. Returns plain text reply."""
    try:
        from web3 import Web3
        from eth_account import Account
        from eth_account.messages import encode_defunct
        from cryptography.hazmat.primitives.asymmetric.ec import (
            generate_private_key, SECP256K1, ECDH
        )
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PublicFormat, NoEncryption, PrivateFormat
        )
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        import requests as req
        import websocket
        import threading as th

        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        acct = Account.from_key(PRIVATE_KEY)

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

        # Build DER-encoded public key from raw bytes
        SECP256K1_OID = bytes.fromhex('3056301006072a8648ce3d020106052b8104000a034200')
        der_pub = SECP256K1_OID + worker_pub_bytes
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
        path = urlparse(self.path).path
        if path == '/api/health':
            self.send_json(200, {
                'status': 'ok',
                'service': 'orcaapp',
                'version': '1.0.0',
                'aivm': 'ready' if PRIVATE_KEY else 'no key'
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
            mode = (data.get('mode') or 'chat').strip().lower()

            if not message:
                self.send_json(400, {'error': 'message required'})
                return
            if not PRIVATE_KEY:
                self.send_json(503, {'error': 'AI not configured — LIGHTCHAIN_PRIVATE_KEY not set'})
                return

            reply = run_aivm_inference(message, mode)
            self.send_json(200, {'reply': reply})

        else:
            self.send_json(404, {'error': 'not found'})


def main():
    if not PRIVATE_KEY:
        print('[WARN] LIGHTCHAIN_PRIVATE_KEY not set — AI endpoints will return 503')
    server = HTTPServer(('0.0.0.0', PORT), OrcaAppHandler)
    print(f'[OrcaApp] Server running on port {PORT}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[OrcaApp] Shutting down')


if __name__ == '__main__':
    main()
