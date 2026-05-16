import sys
import os
import time

# Add the root project directory to the Python path so it can find the 'src' module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
import plotly.graph_objects as go
import random
import logging
from src.core.graph import run_patient_flow
from src.db.queries import get_doctor_status, get_beds

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

st.set_page_config(page_title="AuraMed | AI Triage", layout="wide", page_icon="🏥")

# Minimalist Custom CSS with Pulse Animation
st.markdown(
    """
<style>
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.6; }
        100% { opacity: 1; }
    }
    /* Minimalist typography and background */
    .stApp {
        background-color: #f8fafc;
        color: #1e293b;
    }
    
    /* Clean, soft-shadow cards for custom HTML elements */
    .minimal-card {
        background-color: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        transition: all 0.2s ease;
    }
    .minimal-card:hover {
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border-color: #cbd5e1;
    }
    
    /* Status Indicators */
    .status-badge {
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.85em;
        font-weight: 600;
    }
    .badge-available { background-color: #dcfce7; color: #166534; }
    .badge-busy { background-color: #fee2e2; color: #991b1b; }
    
    /* Hide the default Streamlit header for a cleaner look */
    header {visibility: hidden;}
    
    /* Style the metric containers natively */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
        color: #0f172a;
    }
</style>
""",
    unsafe_allow_html=True,
)


def get_priority_icon(triage_level):
    if not triage_level:
        return "⚪"
    if triage_level >= 4:
        return "🔴 Critical"
    elif triage_level == 3:
        return "🟠 Urgent"
    elif triage_level == 2:
        return "🟡 Semi-Urgent"
    return "🟢 Routine"


def main():
    # Initialize state
    if "last_patient" not in st.session_state:
        st.session_state.last_patient = None
    if "logs" not in st.session_state:
        st.session_state.logs = []

    # Header
    st.markdown(
        "<h1 style='text-align: center; color: #0f172a; margin-bottom: 2rem;'>🏥 AuraMed Orchestration</h1>",
        unsafe_allow_html=True,
    )

    # Create Layout Tabs
    tab_intake, tab_dashboard, tab_logs = st.tabs(
        ["📝 Patient Intake", "📊 Operations Dashboard", "⚙️ System Logs"]
    )

    # --- TAB 1: PATIENT INTAKE ---
    with tab_intake:
        col_form, col_result = st.columns([1.2, 1], gap="large")

        with col_form:
            with st.container(border=True):
                st.markdown("### New Admission")
                with st.form("patient_form", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        name = st.text_input("Full Name", placeholder="e.g. Jane Doe")
                        age = st.number_input(
                            "Age", min_value=0, max_value=120, value=45
                        )
                        gender = st.selectbox("Gender", ["Female", "Male", "Other"])
                    with c2:
                        email = st.text_input("Email", placeholder="jane@example.com")
                        symptoms = st.text_input(
                            "Symptoms", placeholder="chest pain, dizzy"
                        )
                        duration = st.number_input(
                            "Duration (hrs)", min_value=0, value=2
                        )

                    st.markdown("##### Vitals")
                    v1, v2, v3 = st.columns(3)
                    with v1:
                        systolic = st.number_input("Sys BP", 60, 250, 120)
                    with v2:
                        diastolic = st.number_input("Dia BP", 40, 150, 80)
                    with v3:
                        hr = st.number_input("Heart Rate", 30, 200, 80)

                    submit = st.form_submit_button(
                        "Run AI Triage 🚀", use_container_width=True
                    )

                    if submit and name and symptoms:
                        vitals = {
                            "blood_pressure": {
                                "systolic": systolic,
                                "diastolic": diastolic,
                            },
                            "heart_rate": hr,
                        }
                        safe_email = (
                            f"{email.split('@')[0]}_{random.randint(100,9999)}@example.com"
                            if "@" in email
                            else f"user_{random.randint(100,9999)}@example.com"
                        )

                        with st.spinner("Agents are analyzing..."):
                            try:
                                result = run_patient_flow(
                                    name=name.strip(),
                                    symptoms=[s.strip() for s in symptoms.split(",")],
                                    vitals=vitals,
                                    symptom_duration=duration,
                                    age=age,
                                    gender=gender,
                                    email=safe_email,
                                )
                                st.session_state["last_patient"] = result[
                                    "patient"
                                ].to_dict()
                                st.session_state["logs"] = result["logs"]
                            except Exception as e:
                                st.error(f"System Error: {e}")

        with col_result:
            if st.session_state.last_patient:
                p = st.session_state.last_patient
                st.success("Triage Complete!")
                with st.container(border=True):
                    st.markdown(f"### {p.get('name', 'Patient')} Summary")
                    st.markdown("---")
                    m1, m2 = st.columns(2)
                    m1.metric(
                        "Priority Level", get_priority_icon(p.get("triage_level"))
                    )
                    m2.metric("Assigned Dept", p.get("department", "Pending"))

                    m3, m4 = st.columns(2)
                    m3.metric("Assigned Doctor", p.get("assigned_doctor") or "Queued")
                    m4.metric(
                        "Assigned Bed",
                        (
                            f"Bed {p.get('assigned_bed')}"
                            if p.get("assigned_bed")
                            else "Queued"
                        ),
                    )

                    st.caption(
                        f"Detected Emotional State: **{p.get('mood', 'Unknown').title()}** | System Score: **{p.get('priority_score', 0)}**"
                    )
            else:
                st.info(
                    "Awaiting patient submission. Fill out the form to the left to begin."
                )

    # --- TAB 2: LIVE DASHBOARD ---
    with tab_dashboard:
        # 1. The Live Control Header
        head_col1, head_col2 = st.columns([1, 4])
        with head_col1:
            live_mode = st.toggle(
                "🔴 LIVE Auto-Pilot", value=False, help="Refreshes data every 3 seconds"
            )
        with head_col2:
            st.markdown(
                "<div style='text-align: right; color: #64748b; font-size: 14px;'>📡 Server Connection: Active | Latency: 12ms</div>",
                unsafe_allow_html=True,
            )

        st.divider()

        # 2. Live Capacity Gauges (Plotly)
        st.subheader("🛏️ Real-Time Facility Capacity")
        try:
            beds = get_beds()
            if not beds:
                st.warning("No bed data found in database.")
            else:
                gauge_cols = st.columns(len(beds))

                for idx, (bed_type, bed_data) in enumerate(beds.items()):
                    total = bed_data[0] + bed_data[1]
                    occupied = bed_data[1]
                    fill_pct = (occupied / total * 100) if total > 0 else 0

                    color = (
                        "#2ecc71"
                        if fill_pct < 60
                        else "#f39c12" if fill_pct < 85 else "#e74c3c"
                    )

                    fig = go.Figure(
                        go.Indicator(
                            mode="gauge+number",
                            value=fill_pct,
                            number={
                                "suffix": "%",
                                "font": {"size": 24, "color": "#1e293b"},
                            },
                            domain={"x": [0, 1], "y": [0, 1]},
                            title={
                                "text": str(bed_type).replace("_", " "),
                                "font": {"size": 16, "color": "#64748b"},
                            },
                            gauge={
                                "axis": {"range": [0, 100], "visible": False},
                                "bar": {"color": color, "thickness": 0.75},
                                "bgcolor": "#f1f5f9",
                                "borderwidth": 0,
                            },
                        )
                    )

                    fig.update_layout(
                        height=200,
                        margin=dict(l=10, r=10, t=30, b=10),
                        paper_bgcolor="rgba(0,0,0,0)",
                        font={"family": "sans-serif"},
                    )

                    with gauge_cols[idx]:
                        st.plotly_chart(
                            fig,
                            use_container_width=True,
                            config={"displayModeBar": False},
                        )
                        st.markdown(
                            f"<div style='text-align: center; color: #64748b;'>{occupied} of {total} Beds In Use</div>",
                            unsafe_allow_html=True,
                        )

        except Exception as e:
            st.error(f"Could not load telemetry data. Error: {e}")

        st.divider()

        # 3. Live Medical Staff Feed
        st.subheader("👨‍⚕️ Live Staff Telemetry")
        try:
            status = get_doctor_status()
            staff_cols = st.columns(
                3
            )  # Display in a 3-column grid for better visualization

            for idx, doc in enumerate(status):
                with staff_cols[idx % 3]:
                    if doc["status"] == "BUSY":
                        st.markdown(
                            f"""
                        <div class="minimal-card" style="border-top: 4px solid #e74c3c;">
                            <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                                <div>
                                    <h4 style="margin:0; color: #0f172a;">{doc['doctor_name']}</h4>
                                    <span style="color:#64748b; font-size:13px;">🩺 {doc['department']}</span>
                                </div>
                                <span class="status-badge badge-busy" style="animation: pulse 2s infinite;">🔴 BUSY</span>
                            </div>
                            <div style="margin-top: 12px; font-size: 14px; background: #f8fafc; padding: 8px; border-radius: 6px;">
                                <strong>Patient:</strong> {doc.get('with_patient', 'Unknown')}<br>
                                <strong>ETA:</strong> {doc['time_remaining']} mins
                            </div>
                        </div>""",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f"""
                        <div class="minimal-card" style="border-top: 4px solid #2ecc71;">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <div>
                                    <h4 style="margin:0; color: #0f172a;">{doc['doctor_name']}</h4>
                                    <span style="color:#64748b; font-size:13px;">🩺 {doc['department']}</span>
                                </div>
                                <span class="status-badge badge-available">🟢 READY</span>
                            </div>
                        </div>""",
                            unsafe_allow_html=True,
                        )
        except Exception as e:
            st.error("Could not load staff telemetry.")

        # 4. The Auto-Refresh Execution Trigger
        if live_mode:
            time.sleep(3)  # Wait 3 seconds
            st.rerun()  # Automatically reload the page

    # --- TAB 3: SYSTEM LOGS ---
    with tab_logs:
        st.markdown("### Agent Execution Trace")
        if not st.session_state.logs:
            st.info(
                "No logs available yet. Run a patient intake to see agent communication."
            )
        else:
            for log in st.session_state.logs:
                color = (
                    "#dc2626"
                    if "error" in log.lower() or "failed" in log.lower()
                    else "#16a34a"
                )
                st.markdown(
                    f"<code style='color:{color}; display:block; padding:8px; background:#f1f5f9; margin-bottom:4px; border-left: 3px solid {color};'>{log}</code>",
                    unsafe_allow_html=True,
                )


if __name__ == "__main__":
    main()
