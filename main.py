import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import os
import glob
import hashlib
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def fetch_trades(limit=12):
    url = "https://www.capitoltrades.com/trades"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }
    
    try:
        print("🔄 Loading HTML...")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        print(f"✅ Loaded! Status: {response.status_code}")

        soup = BeautifulSoup(response.text, 'html.parser')
        
        tbody = soup.find('tbody')
        if not tbody:
            print("❌ Not found tbody")
            return []
        
        rows = tbody.find_all('tr')
        print(f"📊 Found {len(rows)} rows")
        
        trades = []
        
        for i, row in enumerate(rows[:limit], 1):
            try:
                cells = row.find_all('td')
                
                if len(cells) < 9:
                    continue
                
                # Cell 0: Politician|||Party|||Chamber|||State
                cell0 = cells[0].get_text(separator='|||', strip=True)
                parts0 = [p.strip() for p in cell0.split('|||') if p.strip()]
                
                politician = parts0[0] if len(parts0) > 0 else 'N/A'
                party = parts0[1].capitalize() if len(parts0) > 1 else 'N/A'
                chamber = parts0[2].capitalize() if len(parts0) > 2 else 'N/A'
                state = parts0[3].upper() if len(parts0) > 3 else 'N/A'
                
                # Cell 1: Issuer|||Ticker
                cell1 = cells[1].get_text(separator='|||', strip=True)
                parts1 = [p.strip() for p in cell1.split('|||') if p.strip()]
                
                traded_issuer = parts1[0] if len(parts1) > 0 else 'N/A'
                ticker_raw = parts1[1] if len(parts1) > 1 else 'N/A'
                ticker = ticker_raw.split(':')[0] if ':' in ticker_raw else ticker_raw
                
                # Cell 2: Published
                published = cells[2].get_text(strip=True)
                
                # Cell 3: Traded
                traded = cells[3].get_text(strip=True)
                
                # Cell 4: Filed after
                cell4 = cells[4].get_text(separator='|||', strip=True)
                parts4 = [p.strip() for p in cell4.split('|||') if p.strip()]
                
                if len(parts4) == 2 and parts4[0] == 'days':
                    filed_after = f"{parts4[1]} days"
                else:
                    filed_after = cells[4].get_text(strip=True)
                
                # Cell 5: Owner
                owner = cells[5].get_text(strip=True)
                
                # Cell 6: Type
                trade_type = cells[6].get_text(strip=True).capitalize()
                
                # Cell 7: Size
                size = cells[7].get_text(strip=True)
                
                # Cell 8: Price
                price = cells[8].get_text(strip=True)
                
                # Estimate value
                value = estimate_value(size)
                
                trade = {
                    'politician': politician,
                    'party': party,
                    'chamber': chamber,
                    'state': state,
                    'traded_issuer': traded_issuer,
                    'ticker': ticker,
                    'sector': 'N/A',
                    'published': published,
                    'traded': traded,
                    'filed_after': filed_after,
                    'owner': owner,
                    'type': trade_type,
                    'size': size,
                    'value': value,
                    'price': price
                }
                
                trades.append(trade)
                
            except Exception as e:
                continue
        
        return trades
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def estimate_value(size_str):
    """Estimate value from size"""
    if not size_str or size_str == 'N/A':
        return 0
    
    try:
        if '–' in size_str or '-' in size_str:
            parts = size_str.replace('–', '-').split('-')
            if len(parts) == 2:
                low = parse_money(parts[0].strip())
                high = parse_money(parts[1].strip())
                return (low + high) // 2
        else:
            return parse_money(size_str)
    except:
        return 0

def parse_money(s):
    """Parse money string"""
    s = s.replace('$', '').replace(',', '').strip().upper()
    
    if 'K' in s:
        return int(float(s.replace('K', '')) * 1000)
    elif 'M' in s:
        return int(float(s.replace('M', '')) * 1000000)
    elif 'B' in s:
        return int(float(s.replace('B', '')) * 1000000000)
    else:
        try:
            return int(float(s))
        except:
            return 0

def create_trade_id(trade):
    """Create a unique ID for a trade"""
    id_string = f"{trade['politician']}|{trade['ticker']}|{trade['traded']}|{trade['type']}|{trade['size']}|{trade['price']}"
    return hashlib.md5(id_string.encode()).hexdigest()

def load_latest_trades():
    """Load trades from JSON file (if exists)"""
    try:
        if os.path.exists('trades.json'):
            print("📂 Loading previous trades from trades.json")
            with open('trades.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                old_trades = data.get('trades', [])
                print(f"✅ Loaded {len(old_trades)} previous trades")
                return old_trades
        else:
            print("📂 No previous trades file found")
            return []
    except Exception as e:
        print(f"❌ Error loading previous trades: {e}")
        return []

def find_new_trades(current_trades, old_trades):
    """Compare and find new trades"""
    if not old_trades:
        print("🆕 No previous trades - all trades are new!")
        return current_trades
    
    old_ids = set(create_trade_id(trade) for trade in old_trades)
    
    new_trades = []
    for trade in current_trades:
        trade_id = create_trade_id(trade)
        if trade_id not in old_ids:
            new_trades.append(trade)
    
    print(f"🆕 Found {len(new_trades)} new trades (out of {len(current_trades)} total)")
    
    return new_trades

def save_to_json(trades, filename='trades.json'):
    """Save to JSON - ONLY 1 FILE"""
    data = {
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_trades': len(trades),
        'trades': trades
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"💾 Saved {len(trades)} trades to {filename}")

def send_telegram_new_trades(new_trades):
    """Send Telegram only new trades"""
    if not new_trades:
        print("✅ No new trades to send")
        return

    message = f"🔔 <b>{len(new_trades)} NEW TRADE{'S' if len(new_trades) > 1 else ''} ALERT!</b>\n"
    message += f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
    
    for i, t in enumerate(new_trades[:10], 1):
        message += f"<b>#{i}. {t['politician']}</b>\n"
        message += f"🏛 {t['party']} | {t['chamber']} | {t['state']}\n"
        message += f"🏢 {t['traded_issuer']}"
        
        if t['ticker'] != 'N/A':
            message += f" ({t['ticker']})"
        
        message += f"\n💰 {t['type']} | {t['size']}"
        
        if t['price'] != 'N/A' and t['price']:
            message += f" @ {t['price']}"
        
        message += f"\n📅 {t['traded']} | ⏰ {t['filed_after']}\n"
        message += f"👤 {t['owner']}\n\n"
    
    if len(new_trades) > 10:
        message += f"... +{len(new_trades) - 10} more\n\n"
    
    message += "🔗 capitoltrades.com/trades"
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    try:
        resp = requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        })
        
        if resp.json().get('ok'):
            print(f"✅ Sent {len(new_trades)} new trades to Telegram")
        else:
            print(f"❌ Telegram Error: {resp.json()}")
    except Exception as e:
        print(f"❌ Error sending Telegram: {e}")

def main():
    print("=" * 100)
    print("🚀 CAPITOL TRADES MONITOR")
    print("=" * 100)
    
    # Step 1: Load previous trades
    print("\n📂 STEP 1: Loading previous trades...")
    old_trades = load_latest_trades()
    
    # Step 2: Fetch current trades
    print("\n🔄 STEP 2: Fetching current trades...")
    current_trades = fetch_trades(limit=20)
    
    if not current_trades:
        print("\n❌ No trades fetched!")
        return

    print(f"✅ Found {len(current_trades)} current trades")

    # Step 3: Compare and find new trades
    print("\n🔍 STEP 3: Comparing trades...")
    new_trades = find_new_trades(current_trades, old_trades)
    
    # Step 4: Send Telegram if new trades
    print("\n📱 STEP 4: Sending notifications...")
    if new_trades:
        print(f"🆕 NEW TRADES DETECTED:")
        for i, t in enumerate(new_trades, 1):
            print(f"   {i}. {t['politician']} - {t['ticker']} - {t['type']} - {t['size']}")
        
        send_telegram_new_trades(new_trades)
    else:
        print("✅ No new trades - no notification sent")
    
    # Step 5: Save current trades
    print("\n💾 STEP 5: Saving current trades...")
    save_to_json(current_trades, 'trades.json')

if __name__ == "__main__":
    main()