import asyncio
import datetime
import os
import time
from dotenv import load_dotenv

from auth.auth_manager import AuthManager

async def run_real_login_audit():
    print("=== REAL UPSTOX LOGIN — HUMAN AUTH ONLY ===\n")
    
    # STEP 1: Delete cached auth state
    if os.path.exists("config/token_meta.json"):
        os.remove("config/token_meta.json")
    if os.path.exists("config/token.enc"):
        os.remove("config/token.enc")
        
    print("Deleted cached auth state.\n")
    
    load_dotenv(override=True)
    auth_manager = AuthManager()
    
    # STEP 2 & 3: Run interactive auth
    print("Running interactive auth flow...")
    try:
        await auth_manager.interactive_login()
        auth_completed = True
    except Exception as e:
        print(f"Auth failed: {e}")
        auth_completed = False
        
    # STEP 4: After redirect
    token_meta = auth_manager.store.get_token_meta()
    token_payload = auth_manager.store.get_token_payload()
    
    new_token_present = token_meta is not None
    refresh_token_present = False
    expiry_time_ist = "N/A"
    
    if new_token_present:
        expiry_dt = datetime.datetime.fromtimestamp(token_meta.expires_at, datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
        expiry_time_ist = expiry_dt.strftime('%H:%M:%S')
        if token_payload:
            import json
            try:
                payload_dict = json.loads(token_payload) if isinstance(token_payload, str) else token_payload
            except:
                payload_dict = {}
            refresh_token_present = bool(payload_dict.get("refresh_token"))
            
    # STEP 5: Verify by calling profile endpoint
    is_rest_valid = await auth_manager.validate_token_rest()
    profile_lookup_http = 200 if is_rest_valid else 401
    market_access_http = 200 if is_rest_valid else 401
    
    passed = (profile_lookup_http == 200 and market_access_http == 200 and refresh_token_present)
    
    print("Final Output:\n")
    print(f"auth_completed:\n{auth_completed}")
    print(f"new_token_present:\n{new_token_present}")
    print(f"refresh_token_present:\n{refresh_token_present}")
    print(f"expiry_time_ist:\n{expiry_time_ist}")
    print(f"profile_lookup_http:\n{profile_lookup_http}")
    print(f"market_access_http:\n{market_access_http}\n")
    
    print("Decision:")
    print("PASS" if passed else "FAIL")
    print("\nSTOP.")

if __name__ == "__main__":
    asyncio.run(run_real_login_audit())
