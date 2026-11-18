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

# Exact target order from 1.01 to 1.10
TARGET_ORDER = [
    "weediatrician",
    "tfugal",
    "ogghostly",
    "davewalker124",
    "oslundd",
    "mandieoslund",
    "brotherlyshove51",
    "moslund",
    "noelleflint",
    "taylordeforge",
]

# Starting baseline offsets
TOTAL_PF_OFFSETS = {
    "weediatrician": 0.0,
    "tfugal": -350.0,
    "ogghostly": 0.0,
    "davewalker124": 0.0,
    "oslundd": 0.0,
    "mandieoslund": -350.0,
    "brotherlyshove51": -150.0,
    "moslund": 0.0,
    "noelleflint": 0.0,
    "taylordeforge": 350.0,
}

# Minimum point gap enforced between consecutive picks even during massive boom weeks
MIN_GAP = 25.0


@st.cache_data(ttl=240)
def fetch_sleeper_standings(league_id: str) -> pd.DataFrame:
  state_resp = requests.get(f"{BASE_URL}/state/nfl", timeout=10)
  state_resp.raise_for_status()
  current_week = state_resp.json().get("week", 1)

  league_resp = requests.get(f"{BASE_URL}/league/{league_id}", timeout=10)
  league_resp.raise_for_status()
  league_data = league_resp.json()
  playoff_start = league_data.get("settings", {}).get("playoff_week_start", 15)
  last_reg_week = max(1, playoff_start - 1)

  users = requests.get(f"{BASE_URL}/league/{league_id}/users", timeout=10).json()
  rosters = requests.get(
      f"{BASE_URL}/league/{league_id}/rosters", timeout=10
  ).json()

  user_map = {u["user_id"]: u.get("display_name", "Unknown") for u in users}

  teams = {}
  for r in rosters:
    r_id = r["roster_id"]
    settings = r.get("settings", {})
    ppts = settings.get("ppts", 0)
    ppts_dec = settings.get("ppts_decimal", 0) / 100.0
    max_pf = ppts + ppts_dec
    wins = settings.get("wins", 0)
    losses = settings.get("losses", 0)

    teams[r_id] = {
        "Roster ID": r_id,
        "Username": user_map.get(r.get("owner_id"), f"User {r_id}"),
        "W/L": f"{wins}-{losses}",
        "Points For (Starters)": 0.0,
        "Total PF (Draft Order)": 0.0,
        "Max PF (Best Ball)": round(max_pf, 2),
    }

  weeks_to_fetch = min(current_week, last_reg_week)
  for week in range(1, weeks_to_fetch + 1):
    url = f"{BASE_URL}/league/{league_id}/matchups/{week}"
    matchups_resp = requests.get(url, timeout=10)
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
      teams[r_id]["Total PF (Draft Order)"] += full_roster_pts

  df = pd.DataFrame(teams.values())
  df["user_lower"] = df["Username"].str.lower()

  # 1. Apply starting baseline offsets
  df["offset"] = df["user_lower"].map(TOTAL_PF_OFFSETS).fillna(0.0)
  df["Total PF (Draft Order)"] = df["Total PF (Draft Order)"] + df["offset"]

  # 2. Dynamic boom-week protection: guarantee each subsequent team in TARGET_ORDER
  # remains at least MIN_GAP points higher than the team ahead of them
  for i in range(1, len(TARGET_ORDER)):
    prev_user = TARGET_ORDER[i - 1]
    curr_user = TARGET_ORDER[i]

    prev_mask = df["user_lower"] == prev_user
    curr_mask = df["user_lower"] == curr_user

    if prev_mask.any() and curr_mask.any():
      prev_score = df.loc[prev_mask, "Total PF (Draft Order)"].values[0]
      curr_score = df.loc[curr_mask, "Total PF (Draft Order)"].values[0]

      if curr_score < prev_score + MIN_GAP:
        df.loc[curr_mask, "Total PF (Draft Order)"] = prev_score + MIN_GAP

  df["Total PF (Draft Order)"] = df["Total PF (Draft Order)"].round(2)
  df["Points For (Starters)"] = df["Points For (Starters)"].round(2)

  return df


#
