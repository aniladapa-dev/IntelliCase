import streamlit as st
import os
import pandas as pd
import zipfile
import shutil
from streamlit_option_menu import option_menu
from st_cytoscape import cytoscape
from src.utils.cytoscape_helper import get_cytoscape_elements, STYLESHEET
from src.processors.fir_processor import process_fir
from src.processors.cdr_processor import process_cdr
from src.processors.cctv_processor import process_cctv
from src.processors.bank_processor import process_bank_statement
from src.graph_manager import GraphManager
from src.cctns_loader import load_cctns_history

# ... (Rest of Setup) ...

# --- PAGE CONFIG ---
st.set_page_config(
    layout="wide", 
    page_title="IntelliCase - Criminal Investigation Platform", 
    page_icon="🕵️‍♂️",
    initial_sidebar_state="expanded"
)

# --- INIT ---
os.makedirs("assets", exist_ok=True)
gm = GraphManager()

# --- SESSION STATE & THEME ---
if 'theme' not in st.session_state: st.session_state.theme = 'light'
for key in ['fir_processed', 'cdr_processed', 'cctv_processed', 'bank_processed']:
    if key not in st.session_state: st.session_state[key] = False

# --- CUSTOM CSS ---
def load_css(theme):
    if theme == 'light':
        return """
        <style>
            :root { --background: #F8F9FA; --surface: #FFFFFF; --text: #1F2937; --primary: #2563EB; --border: #E5E7EB; }
            .stApp { background-color: var(--background); color: var(--text); font-family: 'Inter', sans-serif; }
            
            /* Sidebar */
            [data-testid="stSidebar"] { background-color: var(--surface); border-right: 1px solid var(--border); }
            
            /* Buttons */
            div.stButton > button { 
                border-radius: 8px; font-weight: 500; border: 1px solid var(--border);
                background-color: var(--surface); color: var(--text); transition: all 0.2s;
            }
            div.stButton > button:hover { border-color: var(--primary); color: var(--primary); background: #EFF6FF; }
            
            /* Inputs */
            .stTextInput > div > div > input, .stSelectbox > div > div > select { 
                background-color: var(--surface); border-radius: 6px; border: 1px solid var(--border); color: var(--text);
            }
            
            /* Cards/Containers */
            div[data-testid="stExpander"] { background-color: var(--surface); border-radius: 8px; border: 1px solid var(--border); }
            
            /* Tables */
            .stDataFrame { border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
            
            /* Headers */
            h1, h2, h3 { color: #111827; font-weight: 600; letter-spacing: -0.025em; }
            
            /* Alerts */
            .stSuccess { background-color: #ECFDF5; border-left: 4px solid #10B981; }
            .stInfo { background-color: #EFF6FF; border-left: 4px solid #3B82F6; }
            .stWarning { background-color: #FFFBEB; border-left: 4px solid #F59E0B; }
            .stError { background-color: #FEF2F2; border-left: 4px solid #EF4444; }
        </style>
        """
    else:
        return """
        <style>
            :root { --background: #0F172A; --surface: #1E293B; --text: #E2E8F0; --primary: #60A5FA; --border: #334155; }
            .stApp { background-color: var(--background); color: var(--text); font-family: 'Inter', sans-serif; }
            
            [data-testid="stSidebar"] { background-color: var(--surface); border-right: 1px solid var(--border); }
            
            div.stButton > button { 
                background-color: var(--surface); color: var(--text); border: 1px solid var(--border); border-radius: 8px;
            }
            div.stButton > button:hover { border-color: var(--primary); color: var(--primary); }
            
            .stTextInput > div > div > input, .stSelectbox > div > div > select { 
                background-color: #334155; color: white; border: 1px solid var(--border);
            }
            
            div[data-testid="stExpander"] { background-color: var(--surface); border: 1px solid var(--border); }
            
            h1, h2, h3 { color: #F8FAFC; }
            
            .stSuccess { background-color: #064E3B; border-left: 4px solid #34D399; color: #D1FAE5; }
            .stInfo { background-color: #1E3A8A; border-left: 4px solid #60A5FA; color: #DBEAFE; }
        </style>
        """

st.markdown(load_css(st.session_state.theme), unsafe_allow_html=True)

# --- SIDEBAR ---
import plotly.express as px

# ... (Imports remain same) ...

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/10051/10051259.png", width=50)
    st.markdown("### **IntelliCase**")
    st.markdown("---")
    
    # Navigation
    selected = option_menu(
        menu_title=None,
        options=["Home", "Dashboard", "Data Ingestion", "Investigation Board"], 
        icons=["house", "speedometer2", "cloud-upload", "diagram-3"], 
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"font-size": "16px"}, 
            "nav-link": {"font-size": "14px", "margin":"0px", "--hover-color": "rgba(0,0,0,0.05)"},
            "nav-link-selected": {"background-color": "#2563EB", "color": "#FFF"},
        }
    )
    
    st.markdown("---")
    
    # Theme Toggle
    toggle_col1, toggle_col2 = st.columns([1,3])
    with toggle_col1:
        st.write("🌗")
    with toggle_col2:
        theme_choice = st.radio("Theme", ['light', 'dark'], label_visibility="collapsed", horizontal=True)
        if theme_choice != st.session_state.theme:
            st.session_state.theme = theme_choice
            st.rerun()

    st.markdown("---")
    with st.expander("🛠️ **System Tools**"):
        if st.button("🗑️ Purge All Data"):
            gm.clean_database()
            for key in st.session_state:
                if key.endswith('_processed'): st.session_state[key] = False
            st.success("System Reset.")
            
        if st.button("🔄 Sync National DB (FIRs)"):
            with st.spinner("Connecting to CCTNS..."):
                load_cctns_history()
                st.success("Synced.")

# --- PAGE: HOME (LANDING) ---
if selected == "Home":
    st.markdown("""
    <div style="text-align: center; padding: 50px 0;">
        <h1 style="font-size: 3rem; margin-bottom: 10px;">Welcome to IntelliCase</h1>
        <p style="font-size: 1.2rem; color: #6B7280;">AI-Powered Criminal Intelligence Platform</p>
    </div>
    """, unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("### 🕵️‍♂️ Entity Resolution")
        st.caption("Automatically link suspects, phones, and vehicles across multiple cases using Graph Theory.")
    with c2:
        st.markdown("### 🧠 AI Extraction")
        st.caption("Turn unstructured FIRs and CCTV images into structured intelligence using Gemini Flash.")
    with c3:
        st.markdown("### 🕸️ Network Analysis")
        st.caption("Visualize hidden criminal syndicates and follow the money trail.")
        
    st.markdown("---")
    res_col1, res_col2 = st.columns([1, 4])
    with res_col1:
        if st.button("Go to Dashboard ->", type="primary"):
            st.session_state.selected = "Dashboard" # Hacky nav, usually requires rerun
            st.rerun()

# --- PAGE: DASHBOARD (ANALYTICS) ---
elif selected == "Dashboard":
    st.title("📊 Intelligence Command Center")
    
    stats = gm.get_dashboard_stats()
    
    # 1. Heads-Up Display
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Cases", stats['cases'])
    k2.metric("Suspects Tracked", stats['suspects'])
    k3.metric("Vehicles", stats['vehicles'])
    k4.metric("Phone Intercepts", stats['phones'])
    
    st.markdown("---")
    
    # 2. Analytics Split
    ac1, ac2 = st.columns([2, 1])
    
    with ac1:
        st.subheader("📉 Crime Distribution")
        if stats['crime_types']:
            df_chart = pd.DataFrame(list(stats['crime_types'].items()), columns=['Type', 'Count'])
            fig = px.bar(df_chart, x='Type', y='Count', color='Count', template="plotly_white")
            st.plotly_chart(fig, width="stretch")
            
        else:
            st.info("No crime data available for visualization.")
            
    with ac2:
        st.subheader("📝 Recent Activity")
        if stats['recent_cases']:
            st.dataframe(
                pd.DataFrame(stats['recent_cases']), 
                hide_index=True, 
                width="stretch"
            )
        else:
            st.caption("No recent cases found.")
    
    st.success("✅ System Status: Online | Database: Connected")

# --- PAGE: DATA INGESTION ---
elif selected == "Data Ingestion":
    st.title("📂 Evidence Management")
    
    tab1, tab2 = st.tabs(["📤 Quick Upload", "📦 Bulk Import (Project)"])
    
    # --- TAB 1: QUICK UPLOAD (Split by type) ---
    with tab1:
        st.markdown("#### Single File Uploads")
        
        c1, c2, c3, c4 = st.columns(4)
        
        with c1: # FIR
            st.markdown("##### 📄 FIR / Reports")
            fir_files = st.file_uploader("Drop PDF/TXT", type=["txt", "pdf"], accept_multiple_files=True, key="quick_fir")
            if fir_files and st.button("Process Reports"):
                for f in fir_files:
                    path = os.path.join("assets", f.name)
                    with open(path, "wb") as file: file.write(f.getbuffer())
                    data = process_fir(path)
                    gm.add_fir_data(data)
                    st.toast(f"Linked: {f.name}", icon="✅")
        
        with c2: # CDR
            st.markdown("##### 📞 Call Logs")
            cdr_files = st.file_uploader("Drop CDR CSV", type=["csv"], accept_multiple_files=True, key="quick_cdr")
            if cdr_files and st.button("Process CDR"):
                for f in cdr_files:
                    path = os.path.join("assets", f.name)
                    with open(path, "wb") as file: file.write(f.getbuffer())
                    gm.add_cdr_data(process_cdr(path))
                    st.toast(f"CDR Processed: {f.name}", icon="📞")

        with c3: # Bank
            st.markdown("##### 💰 Bank Logs")
            bank_files = st.file_uploader("Drop Statement CSV", type=["csv"], accept_multiple_files=True, key="quick_bank")
            if bank_files and st.button("Process Bank"):
                for f in bank_files:
                    path = os.path.join("assets", f.name)
                    with open(path, "wb") as file: file.write(f.getbuffer())
                    gm.add_bank_data(process_bank_statement(path))
                    st.toast(f"Bank Log Processed: {f.name}", icon="💰")

        with c4: # CCTV
            st.markdown("##### 📷 Surveillance")
            cctv_files = st.file_uploader("Drop Images", type=["png", "jpg"], accept_multiple_files=True, key="quick_cctv")
            if cctv_files and st.button("Scan Evidence"):
                for f in cctv_files:
                    path = os.path.join("assets", f.name)
                    with open(path, "wb") as file: file.write(f.getbuffer())
                    data = process_cctv(path)
                    gm.add_cctv_data(data)
                    st.toast(f"Scanned: {data.get('vehicle_number', 'No Text')}", icon="👁️")

    # --- TAB 2: BULK IMPORT ---
    with tab2:
        st.warning("⚠️ **Project Mode**: Upload a ZIP file containing the entire case folder structure.")
        zip_file = st.file_uploader("Upload Case Archive (.zip)", type="zip", key="zip_upload")
        
        if zip_file and st.button("🚀 Ingest Full Project"):
            zip_path = os.path.join("assets", "uploaded_case.zip")
            with open(zip_path, "wb") as f: f.write(zip_file.getbuffer())
            
            extract_dir = os.path.join("assets", "temp_extracted")
            if os.path.exists(extract_dir): shutil.rmtree(extract_dir)
            os.makedirs(extract_dir)
            
            with zipfile.ZipFile(zip_path, 'r') as z: z.extractall(extract_dir)
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # --- PROCESS LOGIC ---
            files_to_process = []
            for root, _, files in os.walk(extract_dir):
                for f in files: files_to_process.append(os.path.join(root, f))
            
            for i, file_path in enumerate(files_to_process):
                filename = os.path.basename(file_path)
                status_text.text(f"Processing: {filename}...")
                ext = filename.split('.')[-1].lower()
                
                try:
                    if ext in ['txt', 'pdf']:
                        gm.add_fir_data(process_fir(file_path))
                    elif ext == 'csv':
                        # Minimal Smart Check (duplicated for brevity, ideally utils)
                        h = pd.read_csv(file_path, nrows=1)
                        s = " ".join([str(c) for c in h.columns]).lower()
                        if 'duration' in s: gm.add_cdr_data(process_cdr(file_path))
                        elif 'amount' in s: gm.add_bank_data(process_bank_statement(file_path))
                    elif ext in ['jpg', 'png']:
                        gm.add_cctv_data(process_cctv(file_path))
                except Exception as e:
                    st.error(f"Failed {filename}: {e}")
                
                progress_bar.progress((i + 1) / len(files_to_process))
            
            status_text.text("Ingestion Complete!")
            st.success("✅ Case successfully reconstructed in Knowledge Graph.")

# --- PAGE: INVESTIGATION BOARD ---
elif selected == "Investigation Board":
    from src.utils.cytoscape_helper import get_cytoscape_elements, STYLESHEET
    from st_cytoscape import cytoscape

    st.title("🕸️ Investigation Board")
    
    gm = GraphManager()
    
    # ---------------------------------------------------------
    # 1. CONTROLS SECTION (Search & Sort)
    # ---------------------------------------------------------
    all_firs = []
    try:
        with gm.driver.session() as session:
            # Sort by FIR ID Descending
            query = "MATCH (c:Case) RETURN c.id as fir ORDER BY c.id DESC"
            res = session.run(query)
            all_firs = [r['fir'] for r in res]
    except Exception as e:
        st.error(f"Database Error: {e}")

    # ---------------------------------------------------------
    # 1. CONTROLS SECTION (Focus & Layout)
    # ---------------------------------------------------------
    all_firs = []
    try:
        with gm.driver.session() as session:
            # Sort by FIR ID Descending (Newest First)
            query = "MATCH (c:Case) RETURN c.id as fir ORDER BY c.id DESC"
            res = session.run(query)
            all_firs = [r['fir'] for r in res]
    except Exception as e:
        st.error(f"Database Error: {e}")

    # Simplified 2-Column Layout for Controls
    c1, c2 = st.columns([3, 1])
    
    with c1:
        final_options = ["Show All"] + all_firs
        # Default to newest FIR if it exists, otherwise "Show All"
        default_idx = 1 if len(all_firs) > 0 else 0
        
        focus_case = st.selectbox(
            "🔍 Focus Investigation:", 
            final_options, 
            index=default_idx
        )

    with c2:
        layout_mode = st.selectbox("Layout", ['cose', 'breadthfirst', 'circle', 'grid'], index=0)

    # ---------------------------------------------------------
    # 2. FILTER SECTION (The New Checkboxes)
    # ---------------------------------------------------------
    with st.expander("🔻 Graph Filters", expanded=True):
        f1, f2, f3, f4 = st.columns(4)
        with f1: show_cases = st.checkbox("🛡️ Cases", value=True)
        with f2: show_people = st.checkbox("👤 Suspects", value=True)
        with f3: show_vehicles = st.checkbox("🚗 Vehicles", value=True)
        with f4: show_phones = st.checkbox("📞 Phones", value=True)

    # ---------------------------------------------------------
    # 3. DATA FETCHING & FILTERING LOGIC
    # ---------------------------------------------------------
    # A. Fetch Raw Data
    raw_elements = get_cytoscape_elements(gm.driver, focus_fir_id=focus_case)
    
    # B. Define Allowed Types
    allowed_types = []
    if show_cases: allowed_types.append("Case")
    if show_people: allowed_types.append("Person")
    if show_vehicles: allowed_types.append("Vehicle")
    if show_phones: allowed_types.append("Phone")
    
    # C. Apply Filter (Nodes first, then Edges)
    filtered_elements = []
    visible_node_ids = set()

    # Pass 1: Filter Nodes
    for el in raw_elements:
        if 'source' not in el['data']: # It's a Node
            node_type = el['data'].get('type', 'Unknown')
            # Check if type is allowed (Safe fallback: if unknown, show it)
            if node_type in allowed_types or node_type == "Unknown":
                filtered_elements.append(el)
                visible_node_ids.add(el['data']['id'])
    
    # Pass 2: Filter Edges (Only if both Source & Target are visible)
    for el in raw_elements:
        if 'source' in el['data']: # It's an Edge
            src = el['data']['source']
            tgt = el['data']['target']
            if src in visible_node_ids and tgt in visible_node_ids:
                filtered_elements.append(el)

    # ---------------------------------------------------------
    # 4. RENDER GRAPH & DOSSIER
    # ---------------------------------------------------------
    col_graph, col_details = st.columns([3, 1])

    with col_graph:
        if filtered_elements:
            with st.container(border=True):
                selected_node = cytoscape(
                    filtered_elements, 
                    stylesheet=STYLESHEET, 
                    layout={'name': layout_mode}, 
                    height="600px", 
                    key="cytoscape_board_v3"
                )
            
            # Count stats for the visible graph
            node_count = sum(1 for e in filtered_elements if 'source' not in e['data'])
            st.caption(f"Showing {node_count} visible entities. (Hidden: {len(raw_elements) - len(filtered_elements)})")
            
            # ---------------------------------------------------------
            # 5. AI SUSPECT RANKING (The New Section)
            # ---------------------------------------------------------
            st.markdown("---")
            st.subheader("AI Suspect Analysis")
            
            import pandas as pd
            from src.analytics.ranker import generate_suspect_ranking
            
            # Run Analysis
            analysis_data = generate_suspect_ranking(gm.driver, focus_fir_id=focus_case)
            
            if analysis_data:
                # Display as a clean interactive table
                df_analysis = pd.DataFrame(analysis_data)
                st.dataframe(
                    df_analysis,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Rank": st.column_config.TextColumn("Rank", width="small"),
                        "Suspect": st.column_config.TextColumn("Suspect Name", width="medium"),
                        "Risk Score": st.column_config.ProgressColumn(
                            "Risk Score", 
                            format="%d", 
                            min_value=0, 
                            max_value=200,
                            help="Calculated based on cross-case links and asset control."
                        ),
                        "Intelligence Insights": st.column_config.TextColumn("AI Reasoning", width="large"),
                    }
                )
            else:
                st.info("No suspects found in this context to analyze.")
        else:
            selected_node = None
            st.warning("⚠️ No entities found matching your filters.")

    with col_details:
        st.markdown("### Entity Dossier")
        
        from src.utils.dossier_helper import get_entity_details

        if selected_node and 'nodes' in selected_node and len(selected_node['nodes']) > 0:
            node_id = selected_node['nodes'][0]
            
            # Find the original node data to get the raw ID and type
            node_data = None
            for el in filtered_elements:
                if 'data' in el and el['data'].get('id') == node_id:
                    node_data = el['data']
                    break
            
            if node_data:
                raw_id = node_data.get('raw_id') or node_id.replace("_", ":", 1)
                node_type = node_data.get('type', 'Unknown')
                
                dossier = get_entity_details(gm.driver, raw_id, node_type)
                
                st.subheader(dossier["title"])
                if dossier["badge"]:
                    if "🔴" in dossier["badge"] or "⚠️" in dossier["badge"]: st.error(dossier["badge"])
                    elif "🟠" in dossier["badge"] or "🔥" in dossier["badge"]: st.warning(dossier["badge"])
                    else: st.info(dossier["badge"])
                
                st.markdown("---")
                # Premium Detail View (Markdown instead of disabled inputs)
                for label, val in dossier["details"].items():
                    st.markdown(f"**{label}**")
                    st.code(val, language="text")
            else:
                st.info(f"Selected: {node_id}")
        else:
            st.caption("Click a node on the map to view deep intelligence dossier.")

    gm.close()