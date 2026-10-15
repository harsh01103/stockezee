import argparse
import asyncio
from loguru import logger
from dotenv import load_dotenv

from auth.auth_manager import AuthManager
from market.recorder import MarketRecorder

def main():
    # Load environment variables, overriding system ones to ensure .env is prioritized
    load_dotenv(override=True)
    
    parser = argparse.ArgumentParser(description="Phase 1: Resilient Market Recorder")
    parser.add_argument("--auth", action="store_true", help="Run interactive auth flow and save token")
    parser.add_argument("--dry-run", action="store_true", help="Run recorder without saving data")
    parser.add_argument("--resume", action="store_true", help="Resume recorder session")
    args = parser.parse_args()
    
    auth_manager = AuthManager()
    
    # 1. Handle Auth-Only flow
    if args.auth:
        logger.info("Starting Auth Flow...")
        try:
            asyncio.run(auth_manager.interactive_login())
            logger.info("Auth flow complete. You can now run `python recorder.py`.")
        except Exception as e:
            logger.error(f"Auth flow failed: {e}")
        return

    # 2. Start Recorder flow
    if not auth_manager.is_token_valid():
        logger.error("No valid Upstox token found. Please run `python recorder.py --auth` first.")
        return
        
    logger.info(f"Initializing Market Recorder (dry_run={args.dry_run})...")
    recorder = MarketRecorder(auth_manager, dry_run=args.dry_run)
    
    try:
        asyncio.run(recorder.start())
    except KeyboardInterrupt:
        logger.info("Recorder stopped by user via KeyboardInterrupt.")
    except Exception as e:
        logger.exception(f"Recorder crashed: {e}")
        import sys
        sys.exit(1)

if __name__ == "__main__":
    main()
