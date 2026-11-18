import requests
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Armchair Football League - Draft & Standings Tracker",
    page_icon="🏈",
    layout="wide",
)

LEAGUE_ID = "YOUR_LEAGUE_ID"  # <-- Make sure your actual League ID is pasted here
BASE_URL = "https://api.sleeper.app/v1"


@st.cache_data(ttl=240)
def fetch_sleeper_standings(league_id: str) -> pd.DataFrame:
    state_resp = requests.get(f"{BASE_URL}/state/nfl", timeout=10)
    state_resp.raise_for_status()
    current_week = state_resp.json().get("week", 1)

    league_resp = requests.get(f"{BASE_URL}/league/{league_id}", timeout=10)
    league_resp.raise_for_status()
    league_data = league_resp.json()
    playoff_week_start = league_data.get("settings", {}).get("playoff_week_start", 15)
    last_reg_week = max(1, playoff_week_start - 1)

    users = requests.get(f"{BASE_URL}/league/{league_id}/users", timeout=10).json()
    rosters = requests.get(f"{BASE_URL}/league/{league_id}/rosters", timeout=10).json()

    user_map = {
        u["user_id"]: u.get("metadata", {}).get("team_name") or u["display_name"]
        for u in users
    }

    teams = {}
    for r in rosters:
        r_id = r["roster_id"]
        settings = r.get("settings", {})
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

    weeks_to_fetch = min(current_week, last_reg_week)
    for week in range(1, weeks_to_fetch + 1):
        matchups_resp = requests.get(
            f"{BASE_URL}/league/{league_id}/matchups/{week}", timeout=10
        )
        if matchups_resp.status_code != 200:
            continue

        matchups = matchups_resp.json()
        if not matchups:
            continue

        for m in matchups:
            r_id = m.get("roster_id")
            if r_id not in teams:
                continue

            starter_pts = m.get("points") or 0.0
            players_pts_dict = m.get("players_points") or {}
            full_roster_pts = sum(players_pts_dict.values())

            teams[r_id]["Points For (Starters)"] += starter_pts
            teams[r_id]["Full-Roster Total PF"] += full_roster_pts

    df = pd.DataFrame(teams.values())
    df["Points For (Starters)"] = df["Points For (Starters)"].round(2)
    df["Full-Roster Total PF"] = df["Full-Roster Total PF"].round(2)
    df["Bench Points Only"] = (
        df["Full-Roster Total PF"] - df["Points For (Starters)"]
    ).round(2)

    return df


# --- Main UI ---
st.title("🏈 Armchair Football League — Draft Order Tracker")

col1, col2 = st.columns([4, 1])
with col1:
    st.subheader("Live Standings & Rookie Draft Order")
    st.caption("Data refreshes from Sleeper every 4 minutes or on manual sync.")
with col2:
    if st.button("Force Sync Now", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

if LEAGUE_ID == "YOUR_LEAGUE_ID":
    st.warning("Replace `YOUR_LEAGUE_ID` in `app.py` with your Sleeper League ID.")
    st.stop()

try:
    with st.spinner("Fetching Sleeper API data..."):
        df = fetch_sleeper_standings(LEAGUE_ID)
except Exception as e:
    st.error(f"Error connecting to Sleeper API: {e}")
    st.stop()

sort_metric = st.radio(
    "Sort Draft Order By (Lowest Score = 1.01):",
    options=[
        "Full-Roster Total PF",
        "Max PF (Sleeper)",
        "Points For (Starters)",
    ],
    horizontal=True,
)

df_sorted = df.sort_values(by=sort_metric, ascending=True).reset_index(drop=True)
df_sorted.insert(
    0, "Proj. Pick", [f"1.{i + 1:02d}" for i in range(len(df_sorted))]
)

display_cols = [
    "Proj. Pick",
    "Team",
    "Wins",
    "Losses",
    "Full-Roster Total PF",
    "Max PF (Sleeper)",
    "Points For (Starters)",
    "Bench Points Only",
]

st.dataframe(
    df_sorted[display_cols],
    use_container_width=True,
    hide_index=True,
)
