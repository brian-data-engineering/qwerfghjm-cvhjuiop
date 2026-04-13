import os
import requests
import time
import random
from supabase import create_client
from datetime import datetime, timedelta

# --- CONFIG ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Sports to sync: 1=Football, 2=Basketball, 4=Rugby, 5=Tennis
SPORTS = [1, 2, 4, 5]

BASE_URL = "https://ke.sportpesa.com"
API_URL = f"{BASE_URL}/api/upcoming/games"

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "DNT": "1",
}


# --- UTILS ---

def clean_text(text):
    """Strip quotes to prevent SQL/JSON injection in Supabase."""
    if not text:
        return ""
    return str(text).replace('"', '').replace("'", "").strip()


def is_json_response(res):
    """Check that the response is actually JSON and not an HTML block page."""
    content_type = res.headers.get("Content-Type", "")
    return "application/json" in content_type


def create_session():
    """
    Build a warmed-up requests Session that looks like a real browser.
    Hits the homepage first to collect cookies before any API calls.
    """
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)

    try:
        print("🌐 Warming up session (hitting homepage for cookies)...")
        warmup_res = session.get(
            BASE_URL,
            headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
            timeout=15,
        )
        print(f"   Homepage status: {warmup_res.status_code} | Cookies: {dict(session.cookies)}")
        time.sleep(random.uniform(1.0, 2.5))
    except Exception as e:
        print(f"⚠️  Warmup failed (will still try API): {e}")

    return session


# --- CORE FETCH ---

def fetch_games(session, sport_id):
    """
    Fetch upcoming games for a single sport ID.
    Returns a list of raw game dicts, or [] on failure.
    """
    url = f"{API_URL}?sportId={sport_id}"

    api_headers = {
        "Accept": "application/json, text/plain, */*",
        "Referer": f"{BASE_URL}/",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Dest": "empty",
    }

    try:
        time.sleep(random.uniform(1.5, 3.5))
        res = session.get(url, headers=api_headers, timeout=30)

        print(f"\n📡 Sport ID {sport_id} → {url}")
        print(f"   Status: {res.status_code} | Length: {len(res.text)} | Content-Type: {res.headers.get('Content-Type', 'N/A')}")

        if res.status_code != 200:
            print(f"   ❌ Non-200 status. Skipping.")
            return []

        if not is_json_response(res):
            print(f"   🚫 Blocked or redirected — server returned non-JSON.")
            print(f"   🔍 Preview: {res.text[:300]}")
            return []

        content = res.text.strip()
        if not content:
            print(f"   ⚠️  Empty response body.")
            return []

        data = res.json()

        # API returns either a bare list or a dict with a 'games' key
        if isinstance(data, list):
            games = data
        elif isinstance(data, dict):
            games = data.get("games", [])
        else:
            print(f"   ⚠️  Unexpected response shape: {type(data)}")
            games = []

        print(f"   ✅ Got {len(games)} games.")
        return games

    except requests.exceptions.Timeout:
        print(f"   ⏱️  Timeout on sport ID {sport_id}.")
    except requests.exceptions.ConnectionError as e:
        print(f"   🔌 Connection error on sport ID {sport_id}: {e}")
    except ValueError as e:
        # JSON decode failure
        print(f"   ⚠️  JSON parse error on sport ID {sport_id}: {e}")
        print(f"   🔍 Raw preview: {res.text[:300]}")

    return []


# --- ODDS PARSING ---

def parse_odds(markets, sport_id):
    """
    Extract home / draw / away odds from the primary market.
    Football & Rugby use '3 Way'; Basketball & Tennis use '2 Way'.
    Returns (h_odd, d_odd, a_odd) as floats.
    """
    h_odd = d_odd = a_odd = 0.0

    if not markets:
        return h_odd, d_odd, a_odd

    main_market = markets[0]
    m_name = main_market.get("name", "")
    selections = main_market.get("selections", [])

    def get_odd(short_name):
        try:
            return float(next(s["odds"] for s in selections if s.get("shortName") == short_name))
        except (StopIteration, ValueError, KeyError):
            return 0.0

    if m_name == "3 Way":
        h_odd = get_odd("1")
        d_odd = get_odd("X")
        a_odd = get_odd("2")
    elif "2 Way" in m_name:
        h_odd = get_odd("1")
        a_odd = get_odd("2")
        d_odd = 0.0  # No draw in 2-way sports

    return h_odd, d_odd, a_odd


# --- RECORD BUILDER ---

def build_record(item, sport_id):
    """
    Convert a raw API game dict into a clean Supabase-ready record.
    Returns None if the game has no ID.
    """
    game_id = str(item.get("id", "")).strip()
    if not game_id:
        return None

    competitors = item.get("competitors", [{}, {}])
    home = competitors[0].get("name", "") if len(competitors) > 0 else ""
    away = competitors[1].get("name", "") if len(competitors) > 1 else ""

    markets = item.get("markets", [])
    h_odd, d_odd, a_odd = parse_odds(markets, sport_id)

    return {
        "game_id":      game_id,
        "sport_id":     sport_id,
        "competition":  clean_text(item.get("competition", {}).get("name")),
        "home_team":    clean_text(home),
        "away_team":    clean_text(away),
        "match_date":   item.get("date"),
        "market_1":     h_odd,
        "market_x":     d_odd,
        "market_2":     a_odd,
        "all_markets":  markets,
        "last_updated": datetime.now().isoformat(),
    }


# --- SUPABASE SYNC ---

def sync_to_supabase(batch):
    """Upsert batch into sp_prematch_master and prune expired records."""
    if not batch:
        print("\n🕵️  Scout report: No records to sync.")
        return

    try:
        supabase.table("sp_prematch_master").upsert(batch, on_conflict="game_id").execute()
        print(f"\n✅ Synced {len(batch)} records to Supabase.")
    except Exception as e:
        print(f"\n🚨 Supabase upsert error: {e}")
        return

    try:
        cutoff = (datetime.now() - timedelta(hours=5)).isoformat()
        supabase.table("sp_prematch_master").delete().lt("match_date", cutoff).execute()
        print("🧹 Pruned stale matches (older than 5 hours).")
    except Exception as e:
        print(f"⚠️  Supabase cleanup error: {e}")


# --- MAIN ---

def vibe_check():
    print("=" * 55)
    print("🚀 Lucra Scout — Starting sync")
    print("=" * 55)

    session = create_session()

    batch = []
    seen_ids = set()

    for sport_id in SPORTS:
        games = fetch_games(session, sport_id)

        for item in games:
            record = build_record(item, sport_id)
            if record is None:
                continue
            if record["game_id"] in seen_ids:
                continue

            batch.append(record)
            seen_ids.add(record["game_id"])

    sync_to_supabase(batch)

    print("\n" + "=" * 55)
    print(f"🏁 Done. Total records processed: {len(batch)}")
    print("=" * 55)


if __name__ == "__main__":
    vibe_check()
