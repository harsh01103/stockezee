import asyncio
import json
import base64
from loguru import logger
from google.protobuf.json_format import MessageToJson

from auth.auth_manager import AuthManager
from market.feed_provider import UpstoxProvider
from market.proto import MarketDataFeedV3_pb2 as pb
from dotenv import load_dotenv

async def print_live_stream():
    load_dotenv(override=True)
    auth_manager = AuthManager()
    provider = UpstoxProvider(auth_manager)
    await provider.connect()
    
    # Subscribe to Nifty 50 and one active NIFTY option
    instruments = ["NSE_INDEX|Nifty 50", "NSE_FO|56300", "NSE_FO|56304"]
    provider.subscribe(instruments)
    
    msg_count = 0
    async for message in provider.receive():
        if isinstance(message, bytes) and not message.startswith(b'{'):
            feed_response = pb.FeedResponse()
            feed_response.ParseFromString(message)
            print(f"--- MESSAGE {msg_count} ---")
            print(MessageToJson(feed_response, preserving_proto_field_name=True))
            msg_count += 1
            if msg_count > 5:
                break
        else:
            print("Received JSON string:", message)
            
    provider.close()

if __name__ == "__main__":
    asyncio.run(print_live_stream())
