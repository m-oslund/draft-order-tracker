import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Armchair Football League - Draft & Standings Tracker",
    page_icon="🏈",
    layout="wide",
)

LEAGUE_ID = "1314874337139904512"
BASE_URL = "https://api.sleeper.app/v1"

# ==========================================
# 🎯 EXACT TARGET DRAFT ORDER SEQUENCE
# ==========================================
TARGET_ORDER = [
    "Weediatrician",
    "tfugal",
    "OGGhostly",
    "davewalker124",
    "oslundd",
    "mandieoslund",
    "BrotherlyShove51",
    "moslund",
    "noelleflint",
    "taylordeforge",
]


@st.cache_data(ttl=240)
def fetch_sleeper_standings(league_id: str) -> pd.DataFrame:
  state_resp = requests.get(f"{BASE_URL}/state/nfl", timeout=10)
  state_resp.raise_for_status()
  current_week = state_resp.json().get("week", 1)

  league_resp = requests.get(f"{BASE_URL}/league/{league_id}", timeout=10)
  league_resp.raise_for_status()
  league_data = league_resp.json()
  playoff_week_start = league_data.get("settings", {}).get(
      "playoff_week_start", 15
  )
  last_reg_week = max(1, playoff_week_start - 1)

  users = requests.get(f"{BASE_URL}/league/{league_id}/users", timeout=10).json()
  rosters = requests.get(
      f"{BASE_URL}/league/{league_id}/rosters", timeout=10
  ).json()

  # Map user_id to display_name (username)
  user_map = {u["user_id"]: u.get("display_name", "Unknown") for u in users}

  teams = {}
  for r in rosters:
    r_id = r["roster_id"]
    settings = r.get("settings", {})
    max_pf = settings.get("ppts", 0) + (
        settings.get("ppts_decimal", 0) / 100.0
    )

    teams[r_id] = {
        "Roster ID": r_id,
        "Username": user_map.get(r.get("owner_id"), f"User {r_id}"),
        "Wins": settings.get("wins", 0),
        "Losses": settings.get("losses", 0),
        "Points For (Starters)": 0.0,
        "Full-Roster Total PF": 0.0,
        "Max PF": round(max_pf, 2),
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
  df["Points For (Starters)"] = df["Points
