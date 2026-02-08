import streamlit as st
import requests
import json
import os
import pandas as pd
import plotly.express as px
from streamlit_lottie import st_lottie
from datetime import datetime

# Configuration
API_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")

# Page Config
st.set_page_config(
    page_title="OpsPilot AI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for "Unique" feel
st.markdown("""
<style>
    /* Global Styles */
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }
    
    /* Custom Sidebar */
    [data-testid="stSidebar"] {
        background-color: #262730;
        border-right: 1px solid #333;
    }
    
    /* Headers */
    h1, h2, h3 {
        font-family: 'Inter', sans-serif;
        color: #FFFFFF;
    }
    
    /* Buttons */
    .stButton > button {
        background-color: #4CAF50;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.5rem 1rem;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        background-color: #45a049;
        transform: scale(1.02);
    }
    
    /* Metrics */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        color: #4CAF50;
    }
    
    /* Table */
    [data-testid="stDataFrame"] {
        border: 1px solid #333;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# Helper: Load Lottie Animations
def load_lottieurl(url: str):
    try:
        r = requests.get(url)
        if r.status_code != 200:
            return None
        return r.json()
    except:
        return None

# Load Assets
lottie_robot = load_lottieurl("https://lottie.host/80cf309e-3158-4503-91ee-483584759685/u7W1gK3yX3.json") # Example robot animation
lottie_loading = load_lottieurl("https://lottie.host/95296062-811c-42cb-8167-2782b1c85022/Zt2u0A4C4S.json") # Example loading

# Sidebar
with st.sidebar:
    if lottie_robot:
        st_lottie(lottie_robot, height=150, key="sidebar_anim")
    else:
        st.image("https://img.icons8.com/color/96/000000/bot.png", width=100)
        
    st.title("OpsPilot AI")
    st.markdown("Your autonomous incident response companion.")
    
    st.markdown("---")
    page = st.radio("Navigation", ["New Analysis", "Dashboard & History"], index=0)
    
    st.markdown("---")
    st.markdown("### System Status")
    
    # Live Status Check with visual indicator
    try:
        # Hack to verify backend connectivity
        root_url = API_URL.replace("/api/v1", "")
        health = requests.get(f"{root_url}/health", timeout=1)
        if health.status_code == 200:
            st.markdown('<span style="color: #4CAF50;">●</span> Backend Online', unsafe_allow_html=True)
            st.caption(f"v{health.json().get('version', '0.0.0')}")
        else:
            st.markdown('<span style="color: #FF5252;">●</span> Backend Error', unsafe_allow_html=True)
    except:
        st.markdown('<span style="color: #FF5252;">●</span> Backend Offline', unsafe_allow_html=True)

def show_incident_card(incident):
    """Render a beautiful card for incident details"""
    with st.container():
        st.markdown(f"## 🚨 {incident.get('title', 'Untitled Incident')}")
        
        # Metrics Row
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("ID", f"#{incident.get('id')}")
        c2.metric("Status", incident.get("status"))
        
        severity = incident.get("severity", "Medium")
        color = "orange" if severity == "Medium" else "red" if severity == "High" or severity == "Critical" else "green"
        c3.markdown(f"**Severity**")
        c3.markdown(f"<span style='color:{color}; font-weight:bold; font-size:1.2rem'>{severity}</span>", unsafe_allow_html=True)
        
        created_at = incident.get("created_at")
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at)
                formatted_date = dt.strftime("%Y-%m-%d %H:%M")
            except:
                formatted_date = created_at
        else:
            formatted_date = "Now"
        c4.metric("Time", formatted_date)
        
        st.markdown("---")
        
        # Tabs for detailed view
        tab1, tab2 = st.tabs(["ROOT CAUSE ANALYSIS", "RAW DATA"])
        
        with tab1:
            st.markdown(incident.get("root_cause", "*Analysis pending or unavailable.*"))
            
        with tab2:
            st.json(incident)

# --- PAGE: NEW ANALYSIS ---
if page == "New Analysis":
    st.title("🛡️ Incident Analysis Center")
    st.markdown("Paste your application logs below. OpsPilot uses AI agents to detect anomalies, identify root causes, and suggest fixes.")
    
    with st.form("analysis_form"):
        logs_input = st.text_area("Application Logs", height=300, placeholder="[2024-02-12 10:00:01] ERROR: Connection refused...")
        submitted = st.form_submit_button("Analyze Logs", type="primary")
        
    if submitted:
        if not logs_input:
            st.warning("⚠️ Please provide logs to analyze.")
        else:
            # Interactive Status Container
            status_container = st.status("Initializing AI Agents...", expanded=True)
            
            try:
                status_container.write("🔍 parsing log structure...")
                # Simulate a little delay for effect if needed, but not strictly necessary
                
                status_container.write("🧠 Connecting to Gemini Pro...")
                payload = {"logs": logs_input}
                
                # Use spinner locally for the request
                response = requests.post(f"{API_URL}/incident/analyze", json=payload)
                
                if response.status_code == 200:
                    status_container.write("✅ Analysis complete!")
                    status_container.update(label="Analysis Complete", state="complete", expanded=False)
                    
                    incident = response.json()
                    st.toast("New incident analysis ready!", icon="🎉")
                    show_incident_card(incident)
                else:
                    status_container.update(label="Analysis Failed", state="error")
                    st.error(f"Error: {response.text}")
                    
            except Exception as e:
                status_container.update(label="Connection Failed", state="error")
                st.error(f"Connection Error: {e}")

# --- PAGE: DASHBOARD & HISTORY ---
elif page == "Dashboard & History":
    st.title("📊 Operational Dashboard")
    
    try:
        with st.spinner("Fetching fleet data..."):
            response = requests.get(f"{API_URL}/incident/")
            
        if response.status_code == 200:
            incidents = response.json()
            
            if incidents:
                df = pd.DataFrame(incidents)
                
                # --- METRICS ROW ---
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Incidents", len(df))
                
                open_incidents = len(df[df['status'] != 'Resolved']) # Assuming Resolved exists, otherwise just count
                m2.metric("Open Cases", open_incidents)
                
                critical_count = len(df[df['severity'] == 'Critical'])
                m3.metric("Critical Issues", critical_count, delta_color="inverse")
                
                st.markdown("---")
                
                # --- CHARTS ROW ---
                c1, c2 = st.columns(2)
                
                with c1:
                    st.subheader("Severity Distribution")
                    if 'severity' in df.columns:
                        fig_sev = px.pie(df, names='severity', title='Incidents by Severity', hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
                        st.plotly_chart(fig_sev, use_container_width=True)
                
                with c2:
                    st.subheader("Timeline")
                    if 'created_at' in df.columns:
                        df['created_at'] = pd.to_datetime(df['created_at'])
                        daily_counts = df.groupby(df['created_at'].dt.date).size().reset_index(name='count')
                        fig_time = px.line(daily_counts, x='created_at', y='count', title='Incident Volume Over Time', markers=True)
                        st.plotly_chart(fig_time, use_container_width=True)
                
                # --- DATA TABLE ---
                st.subheader("Incident Log")
                
                # Selection for details
                event = st.dataframe(
                    df[['id', 'title', 'severity', 'status', 'created_at']],
                    use_container_width=True,
                    hide_index=True,
                    selection_mode="single-row",
                    on_select="rerun"
                )
                  
                # Handling Selection (User asked for interactivity)
                # Streamlit's new dataframe selection API might not be available in v1.30 depending on minor version.
                # Let's stick to the ID input for guaranteed compatibility, or try the session state approach.
                
                st.info("💡 Tip: Use the ID lookup below to see full details of any incident.")
                
                col_lookup, col_btn = st.columns([3, 1])
                with col_lookup:
                    selected_id = st.number_input("View details for ID:", min_value=1, step=1)
                with col_btn:
                    st.markdown("<br>", unsafe_allow_html=True) # Spacer
                    load_btn = st.button("Load Full Report")
                
                if load_btn:
                    detail_res = requests.get(f"{API_URL}/incident/{selected_id}")
                    if detail_res.status_code == 200:
                        show_incident_card(detail_res.json())
                    else:
                        st.error("Incident not found.")
                
            else:
                st.info("No incidents recorded yet. Start by analyzing some logs!")
                if lottie_loading:
                    st_lottie(lottie_loading, height=200)
        else:
            st.error(f"Failed to fetch data: {response.status_code}")
            
    except Exception as e:
        st.error(f"Connection Error: {e}")
