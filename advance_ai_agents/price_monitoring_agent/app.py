import json
import os

from agents.crewai_agents import run_agents
from datetime import datetime
from dotenv import load_dotenv
import base64
import streamlit as st
load_dotenv("api.env")

# Page config
st.set_page_config(
    page_title="Price Monitoring Agent",
    page_icon="💲",
    layout="wide",
    initial_sidebar_state="expanded"
)

with open("./assets/scrapegraph.png", "rb") as scrapegraph_file:
    scrapegraph_base64 = base64.b64encode(scrapegraph_file.read()).decode()

with open("./assets/twilio.png", "rb") as twilio_file:
    twilio_base64 = base64.b64encode(twilio_file.read()).decode()

    # Create title with embedded images
    title_html = f"""
    <div style="display: flex;  width: 100%; ">
        <h1 style="margin: 0; padding: 0; font-size: 2.5rem; font-weight: bold;">
            <span style="font-size:2.5rem;">💲</span> Price Monitoring Agent with
            <img src="data:image/png;base64,{scrapegraph_base64}" style="height: 60px; vertical-align: middle;"/>
            <span style="color: #8564ff;">Scrapegraph</span> &
            <img src="data:image/png;base64,{twilio_base64}" style="height: 60px; vertical-align: middle;"/>
        </h1>
    </div>
    """
    st.markdown(title_html, unsafe_allow_html=True)
st.markdown("**Track product prices from Amazon, Flipkart, and more with AI-powered monitoring and notifications**")

# Sidebar configuration
with st.sidebar:

    st.image("./assets/nebius.png", width=150)
    nebius_key = st.text_input("Enter your Nebius API key", value=os.getenv("NEBIUS_API_KEY", ""), type="password")

    scrapegraph_key = st.text_input("ScrapeGraph Key", type="password", value=os.getenv("SCRAPHGRAPH_API_KEY", ""), help="ScrapeGraph API key")

    if st.button("Save Keys", use_container_width=True):
        st.session_state["NEBIUS_API_KEY"] = nebius_key
        st.session_state["SCRAPEGRAPH_API_KEY"] = scrapegraph_key
        st.session_state["TWILIO_ACCOUNT_SID"] = os.getenv("TWILIO_ACCOUNT_SID","")
        st.session_state["TWILIO_AUTH_TOKEN"] = os.getenv("TWILIO_AUTH_TOKEN","")
        st.session_state["TWILIO_PHONE_NUMBER"] = os.getenv("TWILIO_PHONE_NUMBER","")
        st.session_state["TWILIO_WHATSAPP_NUMBER"] = os.getenv("TWILIO_WHATSAPP_NUMBER","")
        st.success("Keys saved for this session")

    st.markdown("#### ⚙️ Configuration")
    max_products = st.slider("Max Products to Track", min_value=1, max_value=10, value=5, help="Maximum number of products you can track")
    notification_method = st.selectbox("Notification Method", ["None", "Twilio SMS", "Twilio WhatsApp"], help="How to receive price alerts")
    output_format = st.radio("Output Format", ["Detailed", "JSON", "Markdown"], horizontal=True)
    st.markdown("---")

# Always initialize session state variables if missing
if "history" not in st.session_state:
    st.session_state["history"] = {}
if "selected_urls" not in st.session_state:
    st.session_state["selected_urls"] = set()

st.markdown("#### Quick Product Tracking")
col1, col2 = st.columns([3, 1])
with col1:
    new_url = st.text_input("Enter product URL", placeholder="https://www.amazon.com/product-url", help="Paste the product URL to track")
with col2:
    if st.button("Add Product", use_container_width=True, key="add_quick") and new_url.strip():
        if len(st.session_state["history"]) < max_products:
            st.session_state["history"][new_url.strip()] = {}
            st.success("Product added to tracking list")
        else:
            st.error(f"Maximum {max_products} products allowed")

st.markdown("---")
st.markdown("### 📦 Products to Track")
if st.session_state["history"]:
    selected_urls = list(st.session_state.get("selected_urls", set()))
    if st.checkbox("Select all products", value=False):
        selected_urls = list(st.session_state["history"].keys())
    for url in st.session_state["history"].keys():
        selected = st.checkbox(f"{url[:50]}...", value=url in selected_urls, key=f"select_{url}")
        if selected and url not in selected_urls:
            selected_urls.append(url)
        elif not selected and url in selected_urls:
            selected_urls.remove(url)
    st.session_state["selected_urls"] = set(selected_urls)

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        track_btn = st.button("🔍 Track Selected Products", use_container_width=True, disabled=not selected_urls)
    with col2:
        clear_btn = st.button("🗑️ Clear All", use_container_width=True)
    with col3:
        export_btn = st.button("📊 Export Results", use_container_width=True, disabled="tracking_results" not in st.session_state)

    if clear_btn:
        st.session_state["history"] = {}
        st.session_state["selected_urls"] = set()
        st.rerun()

    if track_btn and selected_urls:
        os.environ["NEBIUS_API_KEY"] = st.session_state.get("NEBIUS_API_KEY", "")
        os.environ["SCRAPEGRAPH_API_KEY"] = st.session_state.get("SCRAPEGRAPH_API_KEY", "")
        progress_bar = st.progress(0)
        total = len(selected_urls)
        results = {}
        for i, url in enumerate(selected_urls):
            progress_bar.progress((i + 1) / total, text=f"Tracking {i+1}/{total}: {url[:40]}...")
            old_data = st.session_state["history"].get(url, {})
            with st.spinner(f"Fetching data for {url[:40]}..."):
                try:
                    product_data = run_agents(url, old_data)
                    if not isinstance(product_data, dict):
                        try:
                            product_data = json.loads(product_data)
                        except:
                            product_data = {"raw": str(product_data)}
                    st.session_state["history"][url] = product_data
                    results[url] = product_data
                except Exception as e:
                    st.error(f"Failed to track {url[:40]}: {str(e)}")
        st.session_state["tracking_results"] = {
            "results": results,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "selected_urls": selected_urls
        }
        progress_bar.empty()
        st.success(f"Updated {len(selected_urls)} products")

    if export_btn and "tracking_results" in st.session_state:
        export_data = st.session_state["tracking_results"]
        st.download_button(
            label="📁 Download Results as JSON",
            data=json.dumps(export_data, indent=2),
            file_name=f"price_tracking_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

    if "tracking_results" in st.session_state and st.session_state["tracking_results"].get("results"):
        st.markdown("---")
        st.markdown("### 📊 Tracking Results")
        for url, product in st.session_state["tracking_results"]["results"].items():
            # Only show if product dict is not empty
            if product:
                title = product.get("title") or url[:60]
                price = product.get("price") or product.get("current_price") or "N/A"
                availability = product.get("availability", "Unknown")
                rating = product.get("rating", "N/A")
                image_url = product.get("image_url", "")
                description = product.get("description", "")
                store = product.get("store", "")
                with st.expander(f"{title}", expanded=False):
                    if output_format == "JSON":
                        st.json(product)
                    elif output_format == "Markdown":
                        md = f"### {title}\n\n"
                        if image_url: md += f"![Product Image]({image_url})\n\n"
                        md += f"**Price:** {price}\n\n"
                        md += f"**Availability:** {availability}\n\n"
                        md += f"**Rating:** {rating}\n\n"
                        if store: md += f"**Store:** {store}\n\n"
                        if description: md += f"**Description:** {description}\n\n"
                        # Optional fields
                        recommended_uses = product.get("recommended_uses") or product.get("recommended_uses_for_product")
                        brand = product.get("brand")
                        if brand: md += f"**Brand:** {brand}\n\n"
                        if recommended_uses: md += f"**Recommended Uses:** {recommended_uses}\n\n"
                        st.markdown(md)
                    else:
                        if image_url: st.image(image_url, width=200)
                        st.markdown(f'<div class="price">{price}</div>', unsafe_allow_html=True)
                        cols = st.columns(3)
                        cols[0].markdown(f"**Availability**  \n{availability}")
                        cols[1].markdown(f"**Rating**  \n{rating}")
                        if store: cols[2].markdown(f"**Store**  \n{store}")
                        # Optional fields
                        brand = product.get("brand")
                        recommended_uses = product.get("recommended_uses") or product.get("recommended_uses_for_product")
                        if brand:
                            st.markdown(f"**Brand:** {brand}")
                        if recommended_uses:
                            st.markdown(f"**Recommended Uses:** {recommended_uses}")
                        if description:
                            with st.expander("Description"):
                                st.write(description)
else:
    st.info("No products being tracked. Add products above.")