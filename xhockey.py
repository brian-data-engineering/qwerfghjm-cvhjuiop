import os
import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
from supabase import create_client

# --- Config ---
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(URL, KEY)

# Ice Hockey ID
SPORT_IDS = [2]

# Ice Hockey specific markets from your notes
ALLOWED_GROUPS = {
    1,    # 1X2 Regular Time (T:1, 2, 3)
    8,    # Double Chance (T:4, 5, 6)
    101,  # Team Wins Incl. OT (T:401, 402)
    19,   # Both Teams to Score (T:180, 181)
}

SEMAPHORE = asyncio.Semaphore(6)
STALE_AFTER_HOURS = 2

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
}

def get_pending_matches():
    try:
        stale_cutoff = (datetime.now(timezone.utc) - timedelta(hours=STALE_AFTER_HOURS)).isoformat()

        # Check recently synced matches
        fresh_res = supabase.table("xmatch_odds_deep") \
            .select("match_id") \
            .gt("last_sync", stale_cutoff) \
            .execute()
        fresh_ids = [r['match_id'] for r in fresh_res.data]

        # Fetch pending hockey matches
        query = supabase.table("xmatch_odds") \
            .select("match_id, deep_game_id, home_team, away_team, sport_id") \
            .in_("sport_id", SPORT_IDS) \
            .not_.is_("deep_game_id", "null") \
            .gt("start_time", datetime.now(timezone.utc).isoformat())

        if fresh_ids:
            query = query.not_.in_("match_id", fresh_ids)

        response = query.limit(300).execute()
        return response.data

    except Exception as e:
        print(f"🚨 Supabase Fetch Error: {e}")
        return []

def compress_group(group):
    compressed_events = []
    for outcome_list in group.get('events', []):
        compressed_outcome = []
        for e in outcome_list:
            entry = {
                'T': e.get('type'),
                'C': e.get('cf') or e.get('cfView'),
            }
            p = e.get('parameter')
            if p is not None:
                entry['P'] = p
            if e.get('isCenter'):
                entry['CE'] = True
            compressed_outcome.append(entry)
        compressed_events.append(compressed_outcome)

    return {
        'G':  group.get('groupId'),
        'GS': group.get('shortGroupId'),
        'E':  compressed_events,
    }

async def fetch_match(session, match):
    m_id = match['match_id']
    d_id = match['deep_game_id']
    teams = f"{match['home_team']} vs {match['away_team']}"

    # gr=0 used to catch all market groups for ice hockey
    api_url = (
        f"https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents?"
        f"cfView=3&countEvents=250&country=87&gameId={d_id}"
        f"&gr=0&grMode=4&lng=en&marketType=1&ref=61"
    )

    async with SEMAPHORE:
        try:
            async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 429:
                    await asyncio.sleep(5)
                    return
                if resp.status != 200:
                    return

                data = await resp.json(content_type=None)

                if "subGamesForMainGame" not in data:
                    return

                all_groups = data.get('eventGroups', [])
                if not all_groups:
                    return

                compressed = [
                    compress_group(g)
                    for g in all_groups
                    if g.get('groupId') in ALLOWED_GROUPS
                ]

                if not compressed:
                    return

                payload = {
                    "match_id": m_id,
                    "deep_game_id": d_id,
                    "raw_json": {
                        "groups": compressed,
                        "synced_at": int(datetime.now(timezone.utc).timestamp()),
                    },
                    "last_sync": datetime.now(timezone.utc).isoformat(),
                }

                supabase.table("xmatch_odds_deep").upsert(
                    payload, on_conflict="match_id"
                ).execute()

                print(f"✅ 🏒 {teams} — groups: {[c['G'] for c in compressed]}")

        except Exception as e:
            print(f"🚨 Error — {teams}: {e}")

async def run():
    matches = get_pending_matches()
    if not matches:
        print("✅ Hockey matches are fresh.")
        return

    print(f"📊 Pending: {len(matches)} hockey matches")
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        tasks = [fetch_match(session, m) for m in matches]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(run())
