

import streamlit as st
from agent import handle_chat  
from db import cars_collection, check_db_health
from dotenv import load_dotenv
import os

load_dotenv("api.env")

st.set_page_config(
    page_title="https://carFinder.com",
    layout="wide",
)

st.markdown("""
<style>
.stApp { background-color: #0E1117; color: #FAFAFA; }
.main-header { font-size: 2.8rem; color: #00D4B1; text-align: center; font-weight: 800; margin-bottom: 0.2rem; letter-spacing: -0.5px; }
.sub-header { text-align: center; color: #888; margin-bottom: 2.5rem; font-size: 1.1rem; }
.stButton>button { width: 100%; background-color: #555555; color: #FAFAFA; border: none; padding: 0.8rem 1rem; border-radius: 8px; font-weight: 600; font-size: 1rem; margin-top: 1rem; }
.stButton>button:hover { background-color: #777777; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
.stTextInput>div>div>input { background-color: #262730; color: #FAFAFA; border: 1px solid #393946; border-radius: 8px; padding: 0.8rem; }
.stTextInput>div>div>input:focus { border-color: #00D4B1; box-shadow: 0 0 0 2px rgba(0, 212, 177, 0.2); }
.css-1d391kg, .css-1d391kg>div { background-color: #0E1117 !important; border-right: 1px solid #262730; }
.css-1d391kg h1,h2,h3,h4,h5,h6,p,label { color: #FAFAFA !important; }
.stProgress > div > div > div > div { background-color: #00D4B1; }
.streamlit-expanderHeader { background-color: #262730; color: #FAFAFA; border-radius: 8px; font-weight: 600; }
.streamlit-expanderContent { background-color: #1A1D25; border-radius: 0 0 8px 8px; }
.card { background-color: #262730; padding: 1.5rem; border-radius: 12px; margin-bottom: 1rem; border-left: 4px solid #00D4B1; }
.stRadio > div { background-color: #262730; padding: 1rem; border-radius: 8px; }
label { font-weight: 600 !important; margin-bottom: 0.5rem; display: block; color: #CCC !important; }
.main-title { font-size: 40px; font-weight: bold; display: flex; align-items: center; }
.main-title img { height: 50px; margin-left: 20px; vertical-align: middle; }
.subtitle { font-size: 20px; color: #AAAAAA; }
</style>
<div class="header">
  <div class="main-title">
    Cars Finder Agent With
    <img src="https://scrapegraphai.com/scrapegraphai_logo.svg" alt="ScrapeGraphAI Logo">
    <span class="sep">×</span>
    <img src="https://registry.npmmirror.com/@lobehub/icons-static-png/latest/files/dark/crewai-brand-color.png" alt="CrewAI Logo">
  </div>
  <div class="subtitle">Smart recommendations for your next car</div>
</div>

<style>
.sep {
  margin: 0 20px;
  font-weight: 600;
  font-size: 20px;
  color: #444;
}
</style>

""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

st.markdown("---")


with st.sidebar:
    st.image("./assets/nebius.png", width="stretch")
    nebius_key = st.text_input(
        "Enter Nebius API Key",
        value=os.getenv("NEBIUS_API_KEY", ""),
        type="password",
    )
    scrapegraph_key = st.text_input(
        "Enter Scrapegraph API Key",
        value=os.getenv("SCRAPEGRAPH_API_KEY", ""),
        type="password",
    )

    if st.button("💾 Save Keys"):
        st.session_state["NEBIUS_API_KEY"] = nebius_key
        st.session_state["SMARTCRAWLER_API_KEY"] = scrapegraph_key

    if nebius_key or scrapegraph_key:
        st.success("Keys saved for this session")

    st.markdown("---")


with st.sidebar.status("User", expanded=True):
    user_id = st.text_input("User ID", value="user_1")


with st.sidebar.status("Storage", expanded=True):
    ok_db, msg_db = check_db_health()
    st.write("Database:", "Active" if ok_db else "Unavailable")
    st.caption(msg_db)

    total_records = cars_collection.count_documents({})
    st.write("Total Car Records:", total_records)


with st.sidebar.status("🔄 Workflow", expanded=True):
    st.markdown("""
- Enter your Nebius & Scrapegraph API keys  
- Set your **User ID**  
- Describe your car requirements in the main text box  
- Click **Enter**  
- The system will automatically use the database (and scrape in the background when needed)
    """)


user_query = st.chat_input(
    "Describe your requirements or questions (budget, type, city, brand, etc.):",
)




if user_query:
    st.chat_message("user").write(user_query)
    if not user_id.strip():
        st.error("User ID required (see sidebar).")
    elif not user_query.strip():
        st.error("Please type your question.")
    else:
        with st.spinner("Analyzing your request and fetching matching cars..."):
            answer, cars = handle_chat(
                user_id=user_id,
                user_query=user_query,
                max_price=None,
                city=None,
            )

        st.markdown("## Suggested for You")
        st.write(answer)

        st.markdown("---")
        st.markdown("### Cars Retrieved from Database")

        if cars:
            for i, car in enumerate(cars, start=1):
                title = car.get("title", "Unknown")
                with st.expander(f"{i}. {title}"):

                    image_url = car.get("image_url")
                    if image_url:
                        st.image(image_url, use_container_width=False)

                    st.write(f"**Price:** {car.get('price')}")
                    st.write(f"**Mileage:** {car.get('mileage')}")
                    st.write(f"**Location:** {car.get('location')}")

                    url = car.get("details_url")
                    if url:
                        st.markdown(f"[View Listing]({url})")
        else:
            st.info("No matching cars found right now. Try adjusting your requirements.")