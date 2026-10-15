import asyncio
import datetime
import os
import json
import httpx
import threading
import websocket
from dotenv import load_dotenv
from auth.auth_manager import AuthManager

class WSTest:
    def __init__(self):
        self.ws = None
        self.frames_received = 0
        self.close_code = "None"
        self.disconnect_reason = "None"
        self.market_status_message_received = False
        self.decoded_messages = []
        self.is_connected = False
        
    def on_message(self, ws, message):
        self.frames_received += 1
        if isinstance(message, bytes):
            # In a real scenario, this is protobuf. For the test output we'll just log length
            if self.frames_received <= 5:
                self.decoded_messages.append(f"<binary frame length={len(message)}>")
        else:
            try:
                data = json.loads(message)
                if data.get("type") == "market_status":
                    self.market_status_message_received = True
            except:
                pass
            if self.frames_received <= 5:
                self.decoded_messages.append(message)

    def on_error(self, ws, error):
        self.disconnect_reason = str(error)

    def on_close(self, ws, close_status_code, close_msg):
        self.is_connected = False
        self.close_code = str(close_status_code)
        self.disconnect_reason = str(close_msg)

    def on_open(self, ws):
        self.is_connected = True
        
        # Subscribe
        payload = {
            "guid": "sub_1",
            "method": "sub",
            "data": {
                "mode": "ltpc",
                "instrumentKeys": ["NSE_INDEX|Nifty 50"]
            }
        }
        self.ws.send(json.dumps(payload).encode('utf-8'))

async def run_audit():
    print("=== STRICT UPSTOX REAL CONNECTION AUDIT ===\n")
    
    # STEP 1
    load_dotenv(override=True)
    auth_manager = AuthManager()
    
    token_payload = auth_manager.store.get_token_payload()
    token_meta = auth_manager.store.get_token_meta()
    
    token_loaded = token_payload is not None
    token_expiry = "None"
    token_length = 0
    
    if token_loaded:
        import json
        try:
            payload_dict = json.loads(token_payload) if isinstance(token_payload, str) else token_payload
        except:
            payload_dict = {}
            
        access_token = payload_dict.get("access_token", "")
        token_length = len(access_token)
        if token_meta:
            expiry_dt = datetime.datetime.fromtimestamp(token_meta.expires_at, datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
            token_expiry = expiry_dt.strftime('%H:%M:%S')
            
    print("STEP 1")
    print(f"token_loaded: {token_loaded}")
    print(f"token_expiry: {token_expiry}")
    print(f"token_length: {token_length}\n")
    
    # STEP 2
    print("STEP 2")
    authorize_http = 401
    redirect_uri = "None"
    
    if token_loaded:
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {access_token}"}
            # Actually, the V3 authorize endpoint is v3/feed/market-data-feed/authorize
            resp = await client.get("https://api.upstox.com/v3/feed/market-data-feed/authorize", headers=headers)
            authorize_http = resp.status_code
            if resp.status_code == 200:
                data = resp.json()
                redirect_uri = data.get("data", {}).get("authorizedRedirectUri", "None")
                
    print(f"http_status: {authorize_http}")
    print(f"authorized_redirect_uri_received: {redirect_uri != 'None'}\n")
    
    # STEP 3, 4, 5
    test = WSTest()
    
    if redirect_uri != "None":
        print("STEP 3")
        test.ws = websocket.WebSocketApp(
            redirect_uri,
            on_open=test.on_open,
            on_message=test.on_message,
            on_error=test.on_error,
            on_close=test.on_close
        )
        
        ws_thread = threading.Thread(target=test.ws.run_forever)
        ws_thread.start()
        
        # Wait up to 5s for connection
        start_wait = time.time()
        while not test.is_connected and time.time() - start_wait < 5:
            await asyncio.sleep(0.1)
            
        print(f"connected: {test.is_connected}")
        
        if test.is_connected:
            print("STEP 4: Subscribed to NSE_INDEX|Nifty 50 (ltpc)")
            print("STEP 5: Observing for 30 seconds...")
            await asyncio.sleep(30)
            
            test.ws.close()
            ws_thread.join(timeout=2)
            
            print(f"market_status_message_received: {test.market_status_message_received}")
            print(f"frames_received: {test.frames_received}")
            print(f"disconnect_reason: {test.disconnect_reason}")
            print(f"close_code: {test.close_code}\n")
            
            # STEP 6
            if test.frames_received > 20:
                print("STEP 6: Decoded messages:")
                for m in test.decoded_messages:
                    print(m)
                print("")
    else:
        print("STEP 3: Skipped (no redirect_uri)")
        print("STEP 4: Skipped")
        print("STEP 5: Skipped")
        
    print("STEP 7")
    passed = (test.frames_received > 20 and test.is_connected)
    decision = "PASS" if passed else "FAIL"
    print(f"{decision}\n")
    
    print("Final Output:\n")
    print(f"token_loaded:\n{token_loaded}")
    print(f"authorize_http:\n{authorize_http}")
    print(f"redirect_uri:\n{redirect_uri[:50] + '...' if redirect_uri != 'None' else 'None'}")
    print(f"ws_connected:\n{test.is_connected}")
    print(f"frames_received:\n{test.frames_received}")
    print(f"close_code:\n{test.close_code}")
    print(f"disconnect_reason:\n{test.disconnect_reason}\n")
    print("STOP")

if __name__ == "__main__":
    import time
    asyncio.run(run_audit())
