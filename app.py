import requests
import pandas as pd
import streamlit as st

# Page configuration
st.set_page_config(
    page_title="Armchair Football League - Draft & Standings Tracker",
    page_icon="🏈",
    layout="wide"
)

LEAGUE_ID = "YOUR_LEAGUE_ID"  # Replace with your actual Sleeper League ID
BASE_URL = "https://api.sleeper.app/v1"


@st.cache_data(ttl=240)
def fetch_sleeper_standings(league_id: str) -> pd.DataFrame:
    """Fetches league users, rosters, and weekly matchups from Sleeper API."""
    # 1. Get current NFL state to know how many weeks have been played
    state_resp = requests.get(f"{BASE_URL}/state/nfl", timeout=10)
    state_resp.raise_for_status()
    current_week = state_resp.json().get("week", 1)

    # 2. Fetch league info (to check regular season length), users, and rosters
    league_resp = requests.get(f"{BASE_URL}/league/{league_id}", timeout=10)
    league_resp.raise_for_status()
    league_data = league_resp.json()
    playoff_week_start = league_data.get("settings", {}).get("playoff_week_start", 15)
    last_reg_week = max(1, playoff_week_start - 1)

    users = requests.get(f"{BASE_URL}/league/{league_id}/users", timeout=10).json()
