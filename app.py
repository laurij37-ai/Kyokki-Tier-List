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
                st.caption(f"**English:** {item_a.get('name_en', '')}")
                st.caption(f"**Category:** {item_a.get('category', '')} | **Diet:** {item_a.get('diet', '')}")
                
                if st.button(f"Vote for {item_a['name_fi']}", key=f"vote_{item_a['id']}"):
                    # Update Elo
                    new_a_elo, new_b_elo = calculate_elo(item_a["elo"], item_b["elo"])
                    
                    # Update in main list
                    for item in st.session_state.foods:
                        if item["id"] == item_a["id"]:
                            item["elo"] = new_a_elo
                            item["matches"] = item.get("matches", 0) + 1
                        elif item["id"] == item_b["id"]:
                            item["elo"] = new_b_elo
                            item["matches"] = item.get("matches", 0) + 1

                    # Save to GitHub
                    if save_github_data(st.session_state.foods, st.session_state.sha):
                        st.success(f"Voted for {item_a['name_fi']}! Scores synced.")
                        # Refresh data & SHA
                        new_foods, new_sha = get_github_data()
                        if new_foods:
                            st.session_state.foods = new_foods
                            st.session_state.sha = new_sha
                        st.rerun()

            with col2:
                st.info(f"### {item_b['name_fi']}")
                st.caption(f"**English:** {item_b.get('name_en', '')}")
                st.caption(f"**Category:** {item_b.get('category', '')} | **Diet:** {item_b.get('diet', '')}")
                
                if st.button(f"Vote for {item_b['name_fi']}", key=f"vote_{item_b['id']}"):
                    # Update Elo
                    new_b_elo, new_a_elo = calculate_elo(item_b["elo"], item_a["elo"])
                    
                    # Update in main list
                    for item in st.session_state.foods:
                        if item["id"] == item_a["id"]:
                            item["elo"] = new_a_elo
                            item["matches"] = item.get("matches", 0) + 1
                        elif item["id"] == item_b["id"]:
                            item["elo"] = new_b_elo
                            item["matches"] = item.get("matches", 0) + 1

                    # Save to GitHub
                    if save_github_data(st.session_state.foods, st.session_state.sha):
                        st.success(f"Voted for {item_b['name_fi']}! Scores synced.")
                        # Refresh data & SHA
                        new_foods, new_sha = get_github_data()
                        if new_foods:
                            st.session_state.foods = new_foods
                            st.session_state.sha = new_sha
                        st.rerun()

    # --- TAB 2: LEADERBOARD ---
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
