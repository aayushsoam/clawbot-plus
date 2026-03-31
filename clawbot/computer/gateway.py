"""
🌐 ClawBot OpenClaw Gateway — Port 18789
Implements the OpenClaw WebSocket gateway protocol so Claw3D
can connect and visualize ClawBot agents in 3D.

Protocol:
  1. Client sends: {"type": "req", "method": "connect", "id": "...", "params": {"auth": {"token": "..."}}}
  2. Gateway replies: {"type": "res", "id": "...", "ok": true}
  3. After that, bidirectional JSON frames flow freely.

Event types sent to Claw3D:
  - agent.status   — task started/stopped/thinking
  - agent.action   — step executed (shell, click, code, etc.)
  - agent.log      — log lines
  - agent.done     — task completed with result
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Optional
from pathlib import Path

logger = logging.getLogger("clawbot.gateway")

# ─── Global State ───────────────────────────────────────────────────────────
_subscribers: set = set()
_pending_approvals = {}  # nonce -> (websocket, remote_addr, pair_code)
_authorized_tokens = {"clawbot-local"}
_tokens_file = Path.home() / ".clawbot" / "tokens.json"

def _load_tokens():
    try:
        if _tokens_file.exists():
            data = json.loads(_tokens_file.read_text())
            _authorized_tokens.update(data.get("tokens", []))
    except Exception:
        pass

def _save_tokens():
    try:
        _tokens_file.parent.mkdir(exist_ok=True)
        _tokens_file.write_text(json.dumps({"tokens": list(_authorized_tokens)}))
    except Exception:
        pass

_load_tokens()


async def _broadcast(frame: dict):
    """Broadcast a JSON frame to all connected Claw3D clients."""
    msg = json.dumps(frame)
    dead = set()
    for ws in _subscribers.copy():
        try:
            await ws.send(msg)
        except Exception:
            dead.add(ws)
    _subscribers.difference_update(dead)


def publish_event(event_type: str, data: dict):
    """
    Publish a ClawBot event to all Claw3D subscribers.
    Call this from agent.py to stream activity into the 3D office.
    """
    loop = None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        pass

    frame = {
        "type": "event",
        "event": event_type,
        "payload": data,
    }

    if loop and loop.is_running():
        asyncio.ensure_future(_broadcast(frame), loop=loop)
    else:
        # Called from sync context — fire and forget
        try:
            asyncio.run(_broadcast(frame))
        except Exception:
            pass


# ─── WebSocket Handler ────────────────────────────────────────────────────────

async def _handle_client(websocket):
    """Handle a single Claw3D client connection."""
    connected = False
    connect_id: Optional[str] = None

    try:
        # Phase 0: Send connect.challenge immediately
        try:
            with open("C:/Users/thaku/OneDrive/Desktop/my project/browser/clawbot/gateway_debug.txt", "a") as f:
                f.write(f"[{time.time()}] Sending connect.challenge...\n")
            nonce = str(time.time())
            await websocket.send(json.dumps({
                "type": "event",
                "event": "connect.challenge",
                "payload": {"nonce": nonce}
            }))
            with open("C:/Users/thaku/OneDrive/Desktop/my project/browser/clawbot/gateway_debug.txt", "a") as f:
                f.write(f"[{time.time()}] connect.challenge sent!\n")
        except Exception as e:
            with open("C:/Users/thaku/OneDrive/Desktop/my project/browser/clawbot/gateway_debug.txt", "a") as f:
                f.write(f"[{time.time()}] ERROR sending challenge: {e}\n")
            raise

        # Phase 1: Wait for connect handshake
        async for raw in websocket:
            try:
                with open("C:/Users/thaku/OneDrive/Desktop/my project/browser/clawbot/gateway_debug.txt", "a") as f:
                    f.write(raw + "\n")
            except Exception:
                pass
            
            try:
                frame = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.close(1003, "invalid json")
                return

            if not connected:
                # Must be a connect request first
                if frame.get("type") != "req" or frame.get("method") != "connect":
                    await websocket.close(1008, "connect required")
                    return

                connect_id = frame.get("id", "")
                params = frame.get("params") or {}
                token = params.get("auth", {}).get("token", "")
                
                is_local = websocket.remote_address[0] in ("127.0.0.1", "::1")
                
                # Authorization Logic
                if is_local or token in _authorized_tokens:
                    # Authorized!
                    connected = True
                else:
                    # Not authorized -> Enter pairing mode
                    pair_code = str(uuid.uuid4().int)[:6]
                    _pending_approvals[nonce] = (websocket, websocket.remote_address[0], pair_code)
                    
                    logger.info(f"🌐 New connection from {websocket.remote_address[0]} is pending approval. Pair code: {pair_code}")
                    
                    # Send a response indicating we are waiting for approval
                    await websocket.send(json.dumps({
                        "type": "res",
                        "id": connect_id,
                        "ok": False,
                        "error": {
                            "code": "unauthorized",
                            "message": f"Device not approved. Use 'clawbot devices approve --latest' on the host machine. Pair code: {pair_code}",
                            "pairCode": pair_code
                        }
                    }))
                    
                    # Wait for approval or disconnect
                    while nonce in _pending_approvals:
                        await asyncio.sleep(1)
                        if websocket.closed: break
                    
                    if token in _authorized_tokens or connected:
                        connected = True
                    else:
                        return # Still not approved, or disconnected

                if connected:
                    _subscribers.add(websocket)
                    await websocket.send(json.dumps({
                        "type": "res",
                        "id": connect_id,
                        "ok": True,
                        "payload": {
                            "type": "hello-ok",
                            "protocol": 3,
                            "snapshot": {
                                "health": {
                                    "agents": [{
                                        "agentId": "clawbot-main",
                                        "name": "ClawBot AI",
                                        "isDefault": True
                                    }]
                                },
                                "sessionDefaults": {"mainKey": "main"}
                            }
                        }
                    }))
                continue

            # Phase 2: Handle requests
            msg_type = frame.get("type")
            if msg_type == "req":
                req_id = frame.get("id")
                method = frame.get("method")
                payload: dict = {}
                
                if method == "agents.list":
                    payload = {
                        "defaultId": "clawbot-main",
                        "mainKey": "main",
                        "agents": [{"id": "clawbot-main", "name": "ClawBot AI"}]
                    }
                elif method == "sessions.list":
                    payload = {"sessions": [{"key": "agent:clawbot-main:main"}]}
                elif method == "status":
                    payload = {
                        "sessions": {
                            "byAgent": [{
                                "agentId": "clawbot-main", 
                                "recent": [{"key": "agent:clawbot-main:main", "updatedAt": int(time.time() * 1000)}]
                            }]
                        }
                    }
                elif method == "sessions.preview":
                    payload = {"ts": int(time.time() * 1000), "previews": []}
                elif method == "exec.approvals.get":
                    payload = {"file": {"agents": {}}}
                elif method == "chat.history":
                    payload = {"messages": []}
                elif method == "models.list":
                    payload = {"models": []}
                elif method == "config.get":
                    payload = {}
                elif method == "skills.status":
                    # CRITICAL: must include `skills` array or frontend crashes with TypeError
                    payload = {
                        "workspaceDir": "",
                        "managedSkillsDir": "",
                        "skills": []
                    }
                elif method == "agent.config.get":
                    payload = {}
                elif method == "agent.files.get":
                    payload = {"files": []}
                
                # Management RPCs (Only for local clients)
                elif method == "devices.list":
                    if not (websocket.remote_address[0] in ("127.0.0.1", "::1")):
                         payload = {"error": "forbidden"}
                    else:
                        payload = {
                            "pending": [
                                {"nonce": n, "ip": remote, "pairCode": code}
                                for n, (ws, remote, code) in _pending_approvals.items()
                            ]
                        }
                elif method == "devices.approve":
                    if not (websocket.remote_address[0] in ("127.0.0.1", "::1")):
                         payload = {"error": "forbidden"}
                    else:
                        target_nonce = (frame.get("params") or {}).get("nonce")
                        if not target_nonce and _pending_approvals:
                            # Approve the latest if no nonce specified
                            target_nonce = list(_pending_approvals.keys())[-1]
                        
                        if target_nonce in _pending_approvals:
                            ws, remote, code = _pending_approvals.pop(target_nonce)
                            new_token = str(uuid.uuid4())
                            _authorized_tokens.add(new_token)
                            _save_tokens()
                            
                            # Signal the connection task that it's approved
                            # The loop is waiting for connected=True
                            # In this simple implementation, the loop will detect the lack of target_nonce in _pending_approvals
                            # and we should ensure the token matches.
                            
                        payload = {"ok": True, "token": new_token if target_nonce else None}

                # Unknown methods: respond with empty ok so Claw3D doesn't hang
                
                await websocket.send(json.dumps({
                    "type": "res",
                    "id": req_id,
                    "ok": True,
                    "payload": payload
                }))
                continue
            
            logger.debug(f"Received from Claw3D: {frame}")

    except Exception as e:
        logger.warning(f"Claw3D client disconnected: {e}")
    finally:
        _subscribers.discard(websocket)
        if connected:
            logger.info("🌐 Claw3D client disconnected.")


# ─── Gateway Server ────────────────────────────────────────────────────────────

async def run_gateway(host: str = "0.0.0.0", port: int = 18789):
    """Start the OpenClaw-compatible WebSocket gateway for Claw3D."""
    try:
        import websockets
    except ImportError:
        return

    try:
        print(f"DEBUG: Gateway binding to {host}:{port}...")
        async with websockets.serve(_handle_client, host, port):
            print(f"DEBUG: Gateway LISTENING on {host}:{port}")
            await asyncio.Future()  # Run forever
    except OSError as e:
        if e.errno != 10048:  # 10048 is address already in use (Windows)
            logger.error(f"Gateway bind error: {e}")
    except Exception as e:
        logger.error(f"Gateway error: {e}")


def start_gateway_thread():
    """Start the gateway in a background thread (call from agent.py or cli.py)."""
    import threading

    def _run():
        print("DEBUG: Gateway thread started.")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            print("DEBUG: Gateway loop running.")
            loop.run_until_complete(run_gateway())
        except Exception as e:
            print(f"DEBUG: Gateway thread error: {e}")
        finally:
            print("DEBUG: Gateway thread exiting.")

    t = threading.Thread(target=_run, daemon=True, name="clawbot-gateway")
    t.start()
    return t


# ─── Quick Test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Starting ClawBot Gateway (Ctrl+C to stop)...")
    asyncio.run(run_gateway())
