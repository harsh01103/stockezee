# PHASE 1 ROOT CAUSE DIAGNOSTIC

## STEP 1: Trace Startup
- **Token load**: Successful (`token.enc` successfully decrypted when valid key is provided)
- **Token validate**: Executed via REST `/v2/user/profile`.
- **Token refresh**: Executed successfully if 401 encountered.
- **WS authorize**: `/v2/feed/market-data-feed/authorize` successful.
- **WS connect**: WebSocket established successfully.
- **Subscription create**: Execution passes through `strike_selector.py`.
- **Subscription send**: Sent successfully to WS.
- **Message receive**: 0 Option tick messages received.
- **Decode**: 0 decoded.
- **Storage**: 0 rows flushed.

## STEP 2: Verify Strike Universe
- **Spot**: Successfully acquired from NSE (if NSE available).
- **Expiry**: Successfully acquired (nearest weekly).
- **Subscription_count**: `0`
- **Selected strikes**: The strike list is populated by the NSE client (e.g., 15 strikes for ATM±7), BUT the conversion to Upstox instrument keys is not implemented.
- **REJECT**: `subscription_count=0` (The options subscription count is 0).

## STEP 3: Inspect NSE
- **Request URL**: `https://www.nseindia.com/api/option-chain-indices`
- **Status**: 200 (or 404/Empty if blocked)
- **Response body**: Contains strike data when successful.
- **Cache usage**: Used aggressively on failures.
- **Failure state**: If the initial fetch fails and the cache is empty, `strike_selector.py` currently returns an empty list `[]`. *Note: The requested static fallback template (ATM±7) has not been implemented yet.*
- **REJECT**: Empty universe on initial failure.

## STEP 4: Inspect WS
- **Authorize success**: Yes
- **WS uri**: Generated successfully
- **Subscription ack**: Acknowledged dummy index subscriptions (`["NSE_INDEX|Nifty 50", "NSE_INDEX|Nifty Bank"]`).
- **Message count**: 0 (or very few index ticks which may be ignored by downstream logic expecting option ticks).
- **REJECT**: Connected but zero options messages.

## STEP 5: Inspect Decoder
- **Raw_received**: 0
- **Decoded**: 0
- **Dropped**: 0
- **REJECT**: `decoded=0`

## STEP 6: Inspect Storage
- **Ticks_in**: 0
- **Ticks_flushed**: 0
- **Rows_written**: 0
- **REJECT**: `ticks_in>0 rows=0` (In this case, ticks_in is also 0).

---

## FINAL OUTPUT

**Root Cause**: 
The Upstox WebSocket is not being instructed to subscribe to any option strikes because the mapping logic inside `market/recorder.py` is incomplete. The `_manage_subscriptions` loop iterates over the selected NSE strikes but executes a `pass` statement, leaving the `new_subs` list empty. It then falls back to dummy index subscriptions (`NSE_INDEX|Nifty 50`), which do not generate the expected option rows.

**Primary blocker**: 
The `pass` statement in `recorder.py`'s `_manage_subscriptions` loop prevents NSE Option strikes from being converted into Upstox `instrumentKeys`.

**Secondary blocker**: 
If the NSE endpoint completely fails on the first run (empty cache), `strike_selector.py` returns an empty array `[]` instead of a static fallback universe, leading to 0 subscriptions.

**Files to change**: 
- `market/recorder.py`
- `market/strike_selector.py`

**Expected fix**: 
1. Implement the instrument key mapping in `recorder.py` (`NSE_FO|NIFTY{YY}{MMM}{STRIKE}{CE/PE}`).
2. Implement an `ATM±7` static template fallback in `strike_selector.py` when the NSE API fails and the cache is empty.
