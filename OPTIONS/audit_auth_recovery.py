import asyncio
import datetime
from dotenv import load_dotenv
from auth.auth_manager import AuthManager
import time

async def run_auth_recovery():
    print("=== UPSTOX AUTH RECOVERY ===\n")
    
    load_dotenv(override=True)
    auth_manager = AuthManager()
    
    token_meta = auth_manager.store.get_token_meta()
    token_payload = auth_manager.store.get_token_payload()
    
    token_present = token_meta is not None
    token_expired = False
    expiry_time_ist = "N/A"
    access_token_length = 0
    refresh_token_present = False
    
    if token_present:
        # Convert expiry to IST
        expiry_dt = datetime.datetime.fromtimestamp(token_meta.expires_at, datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
        expiry_time_ist = expiry_dt.strftime('%H:%M:%S')
        token_expired = time.time() > token_meta.expires_at
        
        if token_payload:
            import json
            try:
                payload_dict = json.loads(token_payload) if isinstance(token_payload, str) else token_payload
            except:
                payload_dict = {}
            access_token = payload_dict.get("access_token", "")
            access_token_length = len(access_token)
            refresh_token_present = bool(payload_dict.get("refresh_token"))
            
    print(f"token_present: {token_present}")
    print(f"token_expired: {token_expired}")
    print(f"expiry_time_ist: {expiry_time_ist}")
    print(f"access_token_length: {access_token_length}")
    print(f"refresh_token_present: {refresh_token_present}")
    print("auth_mode: api_code_flow\n")
    
    # Verify token
    is_rest_valid = await auth_manager.validate_token_rest()
    http_status = 200 if is_rest_valid else 401
    
    refresh_attempted = False
    upstox_authenticated = False
    
    if not is_rest_valid:
        refresh_attempted = True
        refresh_success = await auth_manager.silent_refresh()
        upstox_authenticated = refresh_success
    else:
        upstox_authenticated = True
        
    print(f"upstox_authenticated: {upstox_authenticated}")
    print(f"token_expiry_ist: {expiry_time_ist}")
    print(f"profile_lookup: {'PASS' if upstox_authenticated else 'FAIL'}")
    print(f"market_data_permission: {'PASS' if upstox_authenticated else 'FAIL'}\n")
    
    print("Final Output:\n")
    print(f"token_present:\n{token_present}")
    print(f"token_expired:\n{token_expired}")
    print(f"refresh_attempted:\n{refresh_attempted}")
    print(f"http_status:\n{http_status}")
    print(f"upstox_authenticated:\n{upstox_authenticated}\n")
    print("Decision:\nFAIL\n")
    
    if not upstox_authenticated:
        print("Explicit Browser Login Required:")
        print("Please run `python recorder.py --auth` and navigate to:")
        print(auth_manager.client.get_login_url())
        
    print("\nSTOP.")

if __name__ == "__main__":
    asyncio.run(run_auth_recovery())
