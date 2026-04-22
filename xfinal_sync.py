import os
import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
from supabase import create_client

# --- Config ---
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(URL, KEY)

SPORT_IDS = [1, 2, 3, 4, 10]  # soccer, ice-hockey, basketball, tennis, table-tennis

ALLOWED_GROUPS = {
    1,      # 1X2
    2,      # European Handicap
    8,      # Double Chance
    17,     # Total Goals O/U
    19,     # Asian Handicap
    100,    # Both Teams To Score
    11212,  # Draw No Bet
    99,     # Individual Total Home
    2854,   # Individual Total Away
    15,     # 1st Half Total
    8427,   # 1st Half Asian Handicap
    62,     # 1st Half Result + Total
    8429,   # 2nd Half Asian Handicap
    8863,   # Correct Score
    136,    # Exact Goals
}

SEMAPHORE = asyncio.Semaphore(5)
STALE_AFTER_HOURS = 2

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Flag to debug first response only
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

        response = query.limit(200).execute()
        return response.data

    except Exception as e:
        print(f"🚨 Supabase Fetch Error: {e}")
        return []


async def fetch_match(session, match):
    global _debug_done

    m_id = match['match_id']
    d_id = match['deep_game_id']
    sport_id = match['sport_id']
    teams = f"{match['home_team']} vs {match['away_team']}"

    # FIX: Removed restrictive gr=657 filter, use grMode=0 to get all markets
    api_url = (
        f"https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents?"
        f"cfView=3&countEvents=500&country=87&gameId={d_id}"
        f"&grMode=0&lng=en&marketType=1&ref=61"
    )

    async with SEMAPHORE:
        try:
            async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:

                if resp.status == 429:
                    print(f"⏳ Rate limited — sleeping 5s...")
                    await asyncio.sleep(5)
                    return

                if resp.status == 529:
                    print(f"🔥 Server overloaded (529) for {teams} — skipping")
                    return

                if resp.status != 200:
                    print(f"❌ HTTP {resp.status} for {teams}")
                    return

                json_data = await resp.json(content_type=None)

                # --- DEBUG: print structure of first response ---
                if not _debug_done:
                    _debug_done = True
                    top_keys = list(json_data.keys())
                    val = json_data.get("Value", {})
                    val_keys = list(val.keys())[:15] if val else []
                    ge = val.get("GE", [])
                    print(f"\n🔍 DEBUG first response:")
                    print(f"   Top keys: {top_keys}")
                    print(f"   Value keys: {val_keys}")
                    print(f"   GE length: {len(ge)}")
                    if ge:
                        print(f"   First group keys: {list(ge[0].keys())}")
                        print(f"   First group G: {ge[0].get('G')}")
                    print()
                # ------------------------------------------------

                val = json_data.get("Value", {})
                all_groups = val.get('GE', [])

                if not all_groups:
                    print(f"⚠️  No markets for {teams}")
                    return

                filtered = [g for g in all_groups if g.get('G') in ALLOWED_GROUPS]

                if not filtered:
                    available = [g.get('G') for g in all_groups]
                    print(f"⚠️  No matching groups for {teams} — available: {available[:10]}")
                    return

                normalised_groups = []
                for g in filtered:
                    normalised_groups.append({
                        "groupId": g.get("G"),
                        "shortGroupId": g.get("GS"),
                        "events": [
                            [
                                {
                                    "cf": e.get("C"),
                                    "type": e.get("T"),
                                    "cfView": e.get("CV"),
                                    **({"parameter": e["P"]} if "P" in e else {}),
                                    **({"isCenter": True} if e.get("CE") else {}),
                                }
                                for e in outcome
                            ]
                            for outcome in g.get("E", [])
                        ]
                    })

                payload = {
                    "match_id": m_id,
                    "deep_game_id": d_id,
                    "raw_json": {"eventGroups": normalised_groups},
                    "last_sync": datetime.now(timezone.utc).isoformat(),
                }

                supabase.table("xmatch_odds_deep").upsert(
                    payload, on_conflict="match_id"
                ).execute()

                sport_label = {1: "⚽", 2: "🏒", 3: "🏀", 4: "🎾", 10: "🏓"}.get(sport_id, "🎯")
                print(f"✅ {sport_label} {teams} — {len(normalised_groups)} groups")

        except asyncio.TimeoutError:
            print(f"⏰ Timeout: {teams}")
        except Exception as e:
            print(f"🚨 Error on {teams}: {e}")


async def run():
    matches = get_pending_matches()

    if not matches:
        print("✅ All matches are fresh — nothing to sync.")
        return

    by_sport = {}
    for m in matches:
        by_sport.setdefault(m['sport_id'], []).append(m)

    sport_names = {1: "Soccer", 2: "Ice Hockey", 3: "Basketball", 4: "Tennis", 10: "Table Tennis"}
    print("📊 Pending matches:")
    for sid, ms in by_sport.items():
        print(f"  {sport_names.get(sid, sid)}: {len(ms)}")

    print(f"\n🚀 Syncing {len(matches)} matches across {len(by_sport)} sports...\n")

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        tasks = [fetch_match(session, m) for m in matches]
        await asyncio.gather(*tasks)

    print(f"\n✨ Done at {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    asyncio.run(run())
