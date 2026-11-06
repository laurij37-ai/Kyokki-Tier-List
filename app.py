import streamlit as st
import pandas as pd
import requests
import json
import base64
import random

# ==========================================
# 1. GITHUB INTEGRATION HELPERS
# ==========================================
GITHUB_REPO = st.secrets.get("GITHUB_REPO", "laurij37-ai/Kyokki-Tier-List")
GITHUB_FILE_PATH = "foods.json"
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")

def get_github_data():
    """Fetch the latest foods.json and its file SHA from GitHub."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    } if GITHUB_TOKEN else {}
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return json.loads(content), data["sha"]
    else:
        st.error(f"Failed to fetch data from GitHub: {response.status_code}")
        return None, None

def save_github_data(foods_list, sha):
    """Commit updated Elo scores back to GitHub repository."""
    if not GITHUB_TOKEN:
        st.warning("No GitHub token configured. Changes will only persist in local session.")
        return True
        
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    updated_content = json.dumps(foods_list, indent=2, ensure_ascii=False)
    encoded_content = base64.b64encode(updated_content.encode("utf-8")).decode("utf-8")
    
    payload = {
        "message": "Update food Elo scores [auto-vote]",
        "content": encoded_content,
        "sha": sha
    }
    
    response = requests.put(url, headers=headers, json=payload)
    return response.status_code in [200, 201]

# Helper to record a vote and push to GitHub
def process_vote(winner_item, loser_item):
    # 1. Fetch latest state from GitHub first so we don't overwrite others' votes
    latest_foods, latest_sha = get_github_data()
    if not latest_foods:
        st.error("Could not fetch latest data from GitHub.")
        return

    # 2. Find winner and loser in the fresh data
    w_node = next((item for item in latest_foods if item["id"] == winner_item["id"]), None)
    l_node = next((item for item in latest_foods if item["id"] == loser_item["id"]), None)

    if w_node and l_node:
        # 3. Calculate new Elo ratings
        new_w_elo, new_l_elo = calculate_elo(w_node["elo"], l_node["elo"])
        w_node["elo"] = new_w_elo
        w_node["matches"] = w_node.get("matches", 0) + 1
        l_node["elo"] = new_l_elo
        l_node["matches"] = l_node.get("matches", 0) + 1

        # 4. Save updated data back to GitHub
        if save_github_data(latest_foods, latest_sha):
            # Update session state with the fresh result
            st.session_state.foods = latest_foods
            st.session_state.sha = latest_sha
            st.success("Vote recorded & live scores updated!")
            st.rerun()

# ==========================================
# 2. ELO RATING CALCULATION
# ==========================================
def calculate_elo(r_winner, r_loser, k=32):
    expected_winner = 1 / (1 + 10 ** ((r_loser - r_winner) / 400))
    expected_loser = 1 / (1 + 10 ** ((r_winner - r_loser) / 400))
    
    new_winner = round(r_winner + k * (1 - expected_winner))
    new_loser = round(r_loser + k * (0 - expected_loser))
    return new_winner, new_loser

# ==========================================
# 3. STREAMLIT APPLICATION
# ==========================================
st.set_page_config(page_title="Finnish Food Ranker", page_icon="🇫🇮", layout="wide")

st.title("🇫🇮 Finnish Food Preference Ranker")
st.markdown("Compare two dishes and help determine the ultimate rank of Finnish menu items!")

# Initialize Session State
if "foods" not in st.session_state or "sha" not in st.session_state:
    foods, sha = get_github_data()
    if foods:
        st.session_state.foods = foods
        st.session_state.sha = sha

if "foods" in st.session_state and st.session_state.foods:
    foods = st.session_state.foods
    df = pd.DataFrame(foods)

    # Sidebar Filter
    categories = ["All Categories"] + sorted(list(set(item["category"] for item in foods)))
    selected_category = st.sidebar.selectbox("Filter Category:", categories)

    tab_vote, tab_rankings = st.tabs(["⚔️ Pairwise Vote", "🏆 Leaderboard"])

    # --- TAB 1: PAIRWISE VOTING ---
    with tab_vote:
        st.subheader("Which food do you prefer?")

        # Filter items
        filtered_items = foods if selected_category == "All Categories" else [item for item in foods if item["category"] == selected_category]

        if len(filtered_items) >= 2:
            # Matchmaking: Select 2 items randomly
            item_a, item_b = random.sample(filtered_items, 2)

            col1, col2 = st.columns(2)

            with col1:
                st.info(f"### {item_a['name_fi']}")
                if st.button(f"Vote for {item_a['name_fi']}", key=f"vote_{item_a['id']}"):
                    process_vote(item_a, item_b)


            with col2:
                st.info(f"### {item_b['name_fi']}")
                if st.button(f"Vote for {item_b['name_fi']}", key=f"vote_{item_b['id']}"):
                    process_vote(item_b, item_a)
            


    # --- TAB 2: LEADERBOARD ---
    # Add an optional auto-refresh toggle in the Leaderboard tab
    if st.checkbox("Auto-refresh leaderboard every 10s"):
        import time
        time.sleep(10)
        st.session_state.foods, st.session_state.sha = get_github_data()
        st.rerun()
    
    
    with tab_rankings:
        st.subheader("Global Leaderboard")
        
        display_df = df.sort_values(by="elo", ascending=False).reset_index(drop=True)
        display_df.index += 1
        display_df = display_df.rename(columns={
            "name_fi": "Finnish Name",
            "name_en": "English Name",
            "category": "Category",
            "diet": "Dietary Flags",
            "elo": "Elo Rating",
            "matches": "Total Matches"
        })
        
        st.dataframe(display_df[["Finnish Name", "English Name", "Category", "Elo Rating", "Total Matches"]], use_container_width=True)

        if st.button("🔄 Sync Latest Scores from GitHub"):
            new_foods, new_sha = get_github_data()
            if new_foods:
                st.session_state.foods = new_foods
                st.session_state.sha = new_sha
                st.rerun()
