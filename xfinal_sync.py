import os
import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
from supabase import create_client

# --- Config ---
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(URL, KEY)

# Soccer only
SPORT_IDS = [1]

# Exactly 9 markets from notes — nothing more, nothing less
ALLOWED_GROUPS = {
    1,    # 1X2 (T:1,2,3)
    2,    # European Handicap (T:7,8 + P line)
    8,    # Double Chance (T:4,5,6)
    15,   # Home Team Total Goals (T:11,12 + P line)
    17,   # Total Goals O/U (T:9,10 + P line)
    19,   # Both Teams To Score (T:180,181,11273,11274)
    62,   # Away Team Total Goals (T:13,14 + P line)
    136,  # Correct Score (T:731 P-encoded + T:3786)
    275,  # Victory Margin (T:4850,4851,4918,4919 + P:1,2,3)
}

SEMAPHORE = asyncio.Semaphore(6)
STALE_AFTER_HOURS = 2

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
}

_debug_done = False


def get_pending_matches():
    try:
        stale_cutoff = (datetime.now(timezone.utc) - timedelta(hours=STALE_AFTER_HOURS)).isoformat()

        fresh_res = supabase.table("xmatch_odds_deep") \
            .select("match_id") \
            .gt("last_sync", stale_cutoff) \
            .execute()
        fresh_ids = [r['match_id'] for r in fresh_res.data]

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
    """
    Save only essential E block data:
    G (groupId), GS (shortGroupId), and per outcome: T, C, P, CE
    Drops CV, eventParams and all other metadata.
    """
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
    global _debug_done

    m_id = match['match_id']
    d_id = match['deep_game_id']
    teams = f"{match['home_team']} vs {match['away_team']}"

    api_url = (
        f"https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents?"
        f"cfView=3&countEvents=250&country=87&gameId={d_id}"
        f"&gr=657&grMode=4&lng=en&marketType=1&ref=61"
    )

    async with SEMAPHORE:
        try:
            async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:

                if resp.status == 429:
                    print(f"⏳ Rate limited — sleeping 5s...")
                    await asyncio.sleep(5)
                    return
                if resp.status == 529:
                    print(f"🔥 Overloaded (529) — {teams}")
                    return
                if resp.status != 200:
                    print(f"❌ HTTP {resp.status} — {teams}")
                    return

                data = await resp.json(content_type=None)

                # Debug first response only
                if not _debug_done:
                    _debug_done = True
                    print(f"\n🔍 DEBUG first response:")
                    print(f"   Top keys: {list(data.keys())[:10]}")
                    print(f"   subGamesForMainGame: {'subGamesForMainGame' in data}")
                    groups = data.get('eventGroups', [])
                    print(f"   eventGroups count: {len(groups)}")
                    if groups:
                        available_g = [g.get('groupId') for g in groups]
                        print(f"   Available G values: {available_g}")
                    print()

                if "subGamesForMainGame" not in data:
                    print(f"⚠️  No deep data — {teams}")
                    return

                all_groups = data.get('eventGroups', [])
                if not all_groups:
                    print(f"⚠️  Empty eventGroups — {teams}")
                    return

                # Filter to exactly our 9 allowed groups and compress
                compressed = [
                    compress_group(g)
                    for g in all_groups
                    if g.get('groupId') in ALLOWED_GROUPS
                ]

                if not compressed:
                    available = [g.get('groupId') for g in all_groups]
                    print(f"⚠️  No matching groups — {teams} | available: {available}")
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

                saved_g = [c['G'] for c in compressed]
                print(f"✅ ⚽ {teams} — groups: {saved_g}")

        except asyncio.TimeoutError:
            print(f"⏰ Timeout — {teams}")
        except Exception as e:
            print(f"🚨 Error — {teams}: {e}")


async def run():
    matches = get_pending_matches()

    if not matches:
        print("✅ All soccer matches are fresh — nothing to sync.")
        return

    print(f"📊 Pending: {len(matches)} soccer matches")
    print(f"🚀 Syncing with {SEMAPHORE._value} concurrent workers...\n")

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        tasks = [fetch_match(session, m) for m in matches]
        await asyncio.gather(*tasks)

    print(f"\n✨ Done at {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    asyncio.run(run())
