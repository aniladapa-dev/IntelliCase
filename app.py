import streamlit as st
import os
import pandas as pd
import zipfile
import shutil
from streamlit_option_menu import option_menu
from streamlit_agraph import agraph, Node, Edge, Config
from src.processors.fir_processor import process_fir
from src.processors.cdr_processor import process_cdr
from src.processors.cctv_processor import process_cctv
from src.processors.bank_processor import process_bank_statement
from src.graph_manager import GraphManager

# Page Config
st.set_page_config(layout="wide", page_title="IntelliCase", initial_sidebar_state="expanded")
os.makedirs("assets", exist_ok=True)
gm = GraphManager()

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .stApp { background-color: #0E1117; }
    div.stButton > button { width: 100%; border-radius: 5px; }
    [data-testid="stSidebar"] { background-color: #161B22; }
    h1, h2, h3 { color: #E6E6E6; }
</style>
""", unsafe_allow_html=True)

# --- SESSION STATE ---
for key in ['fir_processed', 'cdr_processed', 'cctv_processed', 'bank_processed']:
    if key not in st.session_state: st.session_state[key] = False

# --- SIDEBAR NAVIGATION ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/10051/10051259.png", width=60)
    st.title("IntelliCase")
    
    selected = option_menu(
        "Main Menu", 
        ["Data Ingestion", "Investigation Board", "Call Log Analyzer"], 
        icons=["cloud-upload", "diagram-3", "telephone"], 
        menu_icon="cast", 
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "#161B22"},
            "icon": {"color": "orange", "font-size": "18px"}, 
            "nav-link": {"font-size": "16px", "text-align": "left", "margin":"0px", "--hover-color": "#262B33"},
            "nav-link-selected": {"background-color": "#FF4B4B"},
        }
    )
    
    if selected == "Investigation Board":
        st.markdown("---")
        st.subheader("🕵️ Filters")
        show_crime = st.checkbox("🔴 Show Crimes", value=True)
        show_person = st.checkbox("🟠 Show Suspects", value=True)
        show_evidence = st.checkbox("🔵 Show Vehicles/Evidence", value=True)
        show_money = st.checkbox("💰 Show Transactions", value=True)
        show_locations = st.checkbox("⚪ Show Locations", value=True)
        show_cases = st.checkbox("📁 Show Cases", value=True)
        show_calls = st.checkbox("📞 Show Call Logs", value=True)
        
    st.markdown("---")
    if st.button("🗑️ Reset Case Data"):
        gm.clean_database()
        for key in ['fir_processed', 'cdr_processed', 'cctv_processed', 'bank_processed']:
            st.session_state[key] = False
        st.success("Case Reset!")

    st.markdown("---")
    st.caption("⚙️ **Legacy Sync**")
    if st.button("🔄 Load Evidence_DB"):
        from src.bulk_loader import load_evidence_db
        with st.spinner("Indexing Archives..."):
            logs = load_evidence_db()
            for log in logs:
                if "❌" in log: st.error(log)
                elif "⚠️" in log: st.warning(log)
                else: st.success(log)

# --- TAB 1: DATA INGESTION ---
if selected == "Data Ingestion":
    st.title("📂 Evidence Ingestion")
    
    # --- ZIP UPLOAD SECTION ---
    st.info("📦 **Bulk Case Upload** (ZIP)")
    zip_file = st.file_uploader("📂 Upload Complete Case Folder (ZIP)", type="zip", key="zip_upload")
    
    if zip_file and st.button("Process Case Folder"):
        # Save ZIP
        zip_path = os.path.join("assets", "uploaded_case.zip")
        with open(zip_path, "wb") as f:
            f.write(zip_file.getbuffer())
            
        # Extract ZIP
        extract_dir = os.path.join("assets", "temp_extracted")
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        os.makedirs(extract_dir)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
            
        st.markdown("### Processing Logs:")
        
        # Iterate and Process
        for root, dirs, files in os.walk(extract_dir):
            for filename in files:
                file_path = os.path.join(root, filename)
                ext = filename.lower().split('.')[-1]
                
                print(f"⏳ [PROCESSING] {filename}...", flush=True)

                try:
                    # FIR Processing
                    if ext in ['txt', 'pdf']:
                        data = process_fir(file_path)
                        gm.add_fir_data(data)
                        st.success(f"📄 FIR Linked: {filename}")
                        st.session_state['fir_processed'] = True
                        print(f"✅ [SUCCESS] {filename} processed.", flush=True)
                        
                    # CSV processing (Smart Routing)
                    elif ext == 'csv':
                        # Read header
                        df_head = pd.read_csv(file_path, nrows=1)
                        cols = list(df_head.columns)
                        cols_str = " ".join([str(c) for c in cols]).lower()
                        
                        if 'duration' in cols_str or 'source' in cols_str:
                            data = process_cdr(file_path)
                            gm.add_cdr_data(data)
                            st.success(f"📞 CDR Analyzed: {filename}")
                            st.session_state['cdr_processed'] = True
                            print(f"✅ [SUCCESS] {filename} (CDR) processed.", flush=True)
                        elif 'amount' in cols_str or 'credit' in cols_str or 'debit' in cols_str:
                            data = process_bank_statement(file_path)
                            gm.add_bank_data(data)
                            st.success(f"💰 Statement Processed: {filename}")
                            st.session_state['bank_processed'] = True
                            print(f"✅ [SUCCESS] {filename} (Bank) processed.", flush=True)
                        else:
                            st.warning(f"⚠️ Unknown CSV format: {filename}")
                            print(f"⚠️ [WARNING] Unknown CSV format: {filename}", flush=True)
                        
                    # CCTV Processing
                    elif ext in ['png', 'jpg', 'jpeg']:
                        data = process_cctv(file_path)
                        gm.add_cctv_data(data)
                        st.success(f"📷 Evidence Scanned: {filename}")
                        st.session_state['cctv_processed'] = True
                        print(f"✅ [SUCCESS] {filename} processed.", flush=True)
                        
                except Exception as e:
                    st.error(f"❌ Error processing {filename}: {str(e)}")
                    print(f"❌ [ERROR] Failed to process {filename}: {str(e)}", flush=True)
                    
        # Optional Cleanup
        # shutil.rmtree(extract_dir)
        # os.remove(zip_path)
        st.success("✅ Bulk Processing Complete!")
        
    st.markdown("---")
    st.subheader("Manual Uploads")

    col1, col2, col3 = st.columns(3)

    # FIR (Manual)
    with col1:
        st.info("📄 **FIR Reports**")
        fir_files = st.file_uploader("Upload FIRs", type=["txt", "pdf"], accept_multiple_files=True, key="fir")
        if st.button("Process FIRs"):
            if fir_files:
                for f in fir_files:
                    path = os.path.join("assets", f.name)
                    with open(path, "wb") as file: file.write(f.getbuffer())
                    try:
                        data = process_fir(path)
                        gm.add_fir_data(data)
                        st.success(f"Linked: {f.name}")
                    except Exception as e: st.error(f"Error: {e}")
                st.session_state['fir_processed'] = True

    # SMART CSV (Manual)
    with col2:
        st.info("📊 **CSV Files (CDR / Bank)**")
        csv_files = st.file_uploader("Upload CSVs", type=["csv"], accept_multiple_files=True, key="csv_manual")
        if st.button("Process CSVs"):
            if csv_files:
                for f in csv_files:
                    path = os.path.join("assets", f.name)
                    with open(path, "wb") as file: file.write(f.getbuffer())
                    try:
                        # Smart Detection
                        df_head = pd.read_csv(path, nrows=1)
                        cols = list(df_head.columns)
                        cols_str = " ".join([str(c) for c in cols]).lower()
                        
                        if 'duration' in cols_str or 'source' in cols_str:
                            data = process_cdr(path)
                            gm.add_cdr_data(data)
                            st.success(f"📞 CDR: {f.name}")
                            st.session_state['cdr_processed'] = True
                        elif 'amount' in cols_str or 'credit' in cols_str or 'debit' in cols_str:
                            data = process_bank_statement(path)
                            gm.add_bank_data(data)
                            st.success(f"💰 Bank: {f.name}")
                            st.session_state['bank_processed'] = True
                        else:
                            st.error(f"❌ Unknown Format: {f.name}")
                    except Exception as e: st.error(f"Error {f.name}: {e}")

    # CCTV (Manual)
    with col3:
        st.info("📷 **CCTV Evidence**")
        cctv_files = st.file_uploader("Upload Images", type=["png", "jpg"], accept_multiple_files=True, key="cctv")
        if st.button("Scan Evidence"):
            if cctv_files:
                for f in cctv_files:
                    path = os.path.join("assets", f.name)
                    with open(path, "wb") as file: file.write(f.getbuffer())
                    try:
                        data = process_cctv(path)
                        gm.add_cctv_data(data)
                        st.success(f"Detected: {data.get('detected_text')}")
                    except: st.error("OCR Failed")
                st.session_state['cctv_processed'] = True

# --- TAB 2: INVESTIGATION BOARD (SMART VISIBILITY) ---
elif selected == "Investigation Board":
    st.title("🕸️ Crime Linkage Map")
    
    col_graph, col_details = st.columns([3, 1])

    with col_graph:
        raw_data = gm.get_graph_data()
        nodes = []
        edges = []
        node_details = {}
        
        # 1. Calculate Degrees & Identify Unique Nodes
        node_degree = {}
        all_nodes = {}
        
        def get_id(node): return getattr(node, 'element_id', getattr(node, 'id', str(node)))

        for record in raw_data:
            n, m = record['n'], record['m']
            n_id, m_id = get_id(n), get_id(m)
            
            all_nodes[n_id] = n
            all_nodes[m_id] = m
            
            node_degree[n_id] = node_degree.get(n_id, 0) + 1
            node_degree[m_id] = node_degree.get(m_id, 0) + 1

        # --- ICONS ---
        ICON_SUSPECT = "https://cdn-icons-png.flaticon.com/512/3050/3050414.png" # With Name
        ICON_PHONE = "https://cdn-icons-png.flaticon.com/512/724/724664.png"   # Phone Only
        ICON_CRIME_SMALL = "https://cdn-icons-png.flaticon.com/512/8653/8653200.png" 
        ICON_CAR = "https://cdn-icons-png.flaticon.com/512/3202/3202926.png"
        ICON_LOC = "https://img.icons8.com/color/96/marker.png" # Map Pin
        ICON_HAND_CENTER = "https://img.icons8.com/color/96/crime.png" 
        ICON_MONEY = "https://cdn-icons-png.flaticon.com/512/2454/2454269.png"

        visible_node_ids = set()

        # 2. First Pass: Determine Node Visibility & Create Nodes
        for nid, node in all_nodes.items():
            labels = list(node.labels)
            degree = node_degree.get(nid, 0)
            props = dict(node)
            name = props.get('name')
            
            is_visible = False
            
            # A. HARD CATEGORIES
            if "Case" in labels: 
                if show_cases: is_visible = True
            elif "Crime" in labels:
                if show_crime: is_visible = True
            elif "Location" in labels:
                if show_locations: is_visible = True
            elif "Vehicle" in labels or "Evidence" in labels:
                if show_evidence: is_visible = True
            
            # B. SMART CATEGORIES
            elif "Person" in labels:
                if name: 
                    # Suspect (Name exists) -> Always show if 'Show Suspects' is on
                    if show_person: is_visible = True
                else:
                    # Phone Number (No Name)
                    # STRICT FILTER: Only show if 'Show Call Logs' checkbox is ON.
                    # (Removed previous 'degree > 1' smart override to ensure filter works as expected)
                    if show_calls:
                        is_visible = True
                        
            elif "Transaction" in labels:
                if show_money:
                    is_visible = True

            if is_visible:
                visible_node_ids.add(nid)
                node_details[nid] = props
                
                # Style Logic
                img = ICON_LOC
                size = 25
                caption = "Unknown"
                
                if "Person" in labels:
                    if name:
                        img = ICON_SUSPECT; size = 30
                        caption = name
                    else:
                        img = ICON_PHONE; size = 20
                        caption = props.get('phone')
                        
                elif "Case" in labels:
                    img = ICON_HAND_CENTER; size = 45; caption = props.get('id', 'Case')
                elif "Crime" in labels:
                    img = ICON_CRIME_SMALL; size = 20; caption = props.get('type', 'Crime')
                elif "Vehicle" in labels:
                    img = ICON_CAR; size = 30; caption = props.get('number', 'Vehicle')
                elif "Evidence" in labels:
                    img = ICON_CAR; size = 30; caption = "Evidence"
                elif "Transaction" in labels:
                    img = ICON_MONEY; size = 28; caption = f"${props.get('amount')}"
                elif "Location" in labels:
                    img = ICON_LOC; size = 25; caption = props.get('name', 'Location')
                    
                nodes.append(Node(id=nid, label=caption, size=size, image=img, shape="image", font={"color": "white", "face": "arial", "align": "bottom"}))

        # 3. Second Pass: Create Edges (Strict Visibility Check)
        for record in raw_data:
            n, m = record['n'], record['m']
            r = record['r']
            n_id, m_id = get_id(n), get_id(m)
            
            # STRICT EDGE FILTER
            if r.type == "CALLED" and not show_calls:
                continue
                
            if n_id in visible_node_ids and m_id in visible_node_ids:
                color = "#555555"
                if r.type == "CALLED": color = "#777777"
                # Label is empty to reduce clutter, info in title (tooltip)
                edges.append(Edge(source=n_id, target=m_id, color=color, label="", title=r.type))

        # Render
        config = Config(width=900, height=700, directed=True, nodeHighlightBehavior=True, highlightColor="#F7A241", collapsible=False)
        selected_id = agraph(nodes=nodes, edges=edges, config=config)

    with col_details:
        st.subheader("📋 Dossier")
        if selected_id and selected_id in node_details:
            st.info(f"ID: {selected_id}")
            for k, v in node_details[selected_id].items():
                st.text_input(k.upper(), str(v), disabled=True)
        else:
            st.write("👈 Click an icon to view details.")

# --- TAB 3: CALL ANALYZER ---
elif selected == "Call Log Analyzer":
    st.title("📞 Call Logs")
    with gm.driver.session() as session:
        result = session.run("""
            MATCH (p1:Person)-[r:CALLED]->(p2:Person)
            RETURN p1.phone as Source, p2.phone as Target, r.duration as Duration
        """)
        calls = [record.data() for record in result]
    
    if calls:
        df = pd.DataFrame(calls)
        st.dataframe(df.style.background_gradient(subset=['Duration'], cmap='Reds'), use_container_width=True)
    else:
        st.info("No calls found.")

gm.close()