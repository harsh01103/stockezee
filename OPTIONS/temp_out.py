def send_telegram_alert(idea):
    """Send instant Telegram push notification for a trade signal."""
    try:
        contract = f"{idea['underlying']} {idea['expiry']} {idea['strike']} {idea['option_type']}"
        lot = LOT_SIZE.get(idea['underlying'], 65)
        lot_cost = round(idea['entry'] * lot)
        last_seen = idea.get('last_seen_price', idea['entry'])
        max_entry = idea.get('max_entry', idea['entry'])
        hedge_str = ''
        if idea.get('action') == 'SELL' and idea.get('hedge_strike'):
            hedge_str = f"🛡️ HEDGE LEG: Buy {idea['underlying']} {idea['expiry']} {idea['hedge_strike']} {idea['option_type']}\n"
        msg = f"🚨 *TRADE SIGNAL*\n━━━━━━━━━━━━━━━━━━━━━\n📌 *{contract}*\n{hedge_str}📊 Direction: *{idea['direction']}*\n⚙️ Strategy: *{idea.get('strategy', 'Momentum Breakout')}*\n━━━━━━━━━━━━━━━━━━━━━\n👁 Last Seen: ₹{last_seen}\n✅ *LIMIT ORDER: ₹{idea['entry']}*\n🚫 Don't Chase: ₹{max_entry}\n💰 Lot Cost: ₹{lot_cost:,}\n━━━━━━━━━━━━━━━━━━━━━\n🛑 Stop Loss: ₹{idea['stop']}\n🎯 Target 1: ₹{idea['target1']}\n🎯 Target 2: ₹{idea['target2']}\n━━━━━━━━━━━━━━━━━━━━━\n📈 Confidence: {idea['confidence']}\n⏰ Enter Before: {idea['entry_window_end']}\n⏳ Hold: {idea['expected_hold_minutes']}"
        try:
            url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
            resp = httpx.post(url, json={'chat_id': TELEGRAM_CHAT_ID, 'text': msg, 'parse_mode': 'Markdown'}, timeout=5)
            if resp.status_code == 200:
                log.info('Telegram alert sent for %s', contract)
            else:
                log.warning('Telegram alert failed: %s', resp.text)
        except Exception as e:
            log.warning('Telegram HTTP error: %s', e)
        try:
            url = 'http://localhost:4000/api/signals/webhook'
            webhook_payload = {'message': msg, 'features': {'size_multiplier': idea.get('size_multiplier', 1), 'confidence': idea.get('confidence', 0), 'regime': idea.get('regime', ''), 'execution_score': idea.get('execution_score', 0), 'timeout_seconds': idea.get('timeout_seconds', 180), 'quantity': idea.get('quantity', 0)}, 'model_version': idea.get('telemetry_version', ''), 'strategy_name': idea.get('strategy', '')}
            resp = httpx.post(url, json=webhook_payload, timeout=5.0)
            if resp.status_code == 200:
                log.info('Webhook alert sent for %s', contract)
            else:
                log.warning('Webhook alert failed: %s', resp.text)
        except Exception as e:
            log.warning('Webhook HTTP error: %s', e)
    except Exception as e:
        log.warning('Alert/Execution formatting error: %s', e)