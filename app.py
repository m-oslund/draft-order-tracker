import requests
import pandas as pd
import streamlit as st

LEAGUE_ID = "YOUR_LEAGUE_ID"  # Replace with your Armchair Football League ID
BASE_URL = "https://api.sleeper.app/v1"

# Cache expires every 4 minutes so the 5-minute fragment always gets fresh data
@st.cache_data(ttl=240)
def fetch_sleeper_standings(league_id: str) -> pd.DataFrame:
    # 1. Get current NFL state to know how many weeks have been played
    state = requests.get(f"{BASE_URL}/state/nfl").json()
    current_week = state.get("week", 1)

    # 2. Fetch users and rosters
    users = requests.get(f"{BASE_URL}/league/{league_id}/users").json()
    rosters = requests.get(f"{BASE_URL}/league/{league_id}/rosters").json()

    user_map = {
        u["user_id"]: u.get("metadata", {}).get("team_name") or u["display_name"]
        for u in users
    }

    # Initialize team tracking dictionary
    teams = {}
    for r in rosters:
        r_id = r["roster_id"]
        settings = r.get("settings", {})
        
        # Sleeper natively stores season Max PF in settings as ppts + ppts_decimal
        max_pf = settings.get("ppts", 0) + (settings.get("ppts_decimal", 0) / 100.0)
        
        teams[r_id] = {
            "Roster ID": r_id,
            "Team": user_map.get(r.get("owner_id"), f"Team {r_id}"),
            "Wins": settings.get("wins", 0),
            "Losses": settings.get("losses", 0),
            "Points For (Starters)": 0.0,
            "Full-Roster Total PF": 0.0,
            "Max PF (Sleeper)": round(max_pf, 2),
        }

    # 3. Loop through completed/active regular season weeks to sum Starters & Full-Roster PF
    # Adjust range if your regular season ends at Week 14
    max_reg_week = min(current_week, 14)
    for week in range(1, max_reg_week + 1):
        matchups = requests.get(f"{BASE_URL}/league/{league_id}/matchups/{week}").json()
        if not matchups:
            continue
            
        for m in matchups:
            r_id = m["roster_id"]
            if r_id not in teams:
                continue
            
            # Starters points for the week
            starter_pts = m.get("points") or 0.0
            
            # All rostered players (Starters + Bench) points for the week
            players_pts_dict = m.get("players_points") or {}
            full_roster_pts = sum(players_pts_dict.values())
            
            teams[r_id]["Points For (Starters)"] += starter_pts
            teams[r_id]["Full-Roster Total PF"] += full_roster_pts

    # 4. Format into a clean DataFrame
    df = pd.DataFrame(teams.values())
    df["Points For (Starters)"] = df["Points For (Starters)"].round(2)
    df["Full-Roster Total PF"] = df["Full-Roster Total PF"].round(2)
    df["Bench Points Only"] = (df["Full-Roster Total PF"] - df["Points For (Starters)"]).round(2)
    
    return df

# Auto-refresh this section every 5 minutes (300 seconds) without full page reload
@st.fragment(run_every="5m")
def render_live_standings():
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("Live Standings & Draft Order Metrics")
    with col2:
        if st.button("Force Sync Now"):
            st.cache_data.clear()
            st.rerun(scope="fragment")

    df = fetch_sleeper_standings(LEAGUE_ID)

    # Toggle which metric determines projected rookie draft order (lowest score = 1.01)
    sort_metric = st.radio(
        "Sort Draft Order By (Lowest = 1.01):",
        options=["Full-Roster Total PF", "Max PF (Sleeper)", "Points For (Starters)"],
        horizontal=True
    )

    df_sorted = df.sort_values(by=sort_metric, ascending=True).reset_index(
