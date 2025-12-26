import streamlit as st
import os
import pandas as pd
from streamlit_option_menu import option_menu
from streamlit_agraph import agraph, Node, Edge, Config
from src.processors.fir_processor import process_fir
from src.processors.cdr_processor import process_cdr
from src.processors.cctv_processor import process_cctv
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
for key in ['fir_processed', 'cdr_processed', 'cctv_processed']:
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
        show_evidence = st.checkbox("🔵 Show Vehicles", value=True)
        st.markdown("---")
        show_calls = st.checkbox("📞 Show Call Logs", value=True)
        
    st.markdown("---")
    if st.button("🗑️ Reset Case Data"):
        gm.clean_database()
        for key in ['fir_processed', 'cdr_processed', 'cctv_processed']:
            st.session_state[key] = False
        st.success("Case Reset!")

# --- TAB 1: DATA INGESTION ---
if selected == "Data Ingestion":
    st.title("📂 Evidence Ingestion")
    col1, col2, col3 = st.columns(3)

    # FIR
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

    # CDR
    with col2:
        st.info("📞 **Call Logs**")
        cdr_files = st.file_uploader("Upload CDR", type=["csv"], accept_multiple_files=True, key="cdr")
        if st.button("Analyze Logs"):
            if cdr_files:
                for f in cdr_files:
                    path = os.path.join("assets", f.name)
                    with open(path, "wb") as file: file.write(f.getbuffer())
                    try:
                        data = process_cdr(path)
                        gm.add_cdr_data(data)
                        st.success(f"Linked: {len(data)} calls")
                    except: st.error("Error processing CDR")
                st.session_state['cdr_processed'] = True

    # CCTV
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

# --- TAB 2: INVESTIGATION BOARD (FIXED ICONS) ---
elif selected == "Investigation Board":
    st.title("🕸️ Crime Linkage Map")
    
    col_graph, col_details = st.columns([3, 1])

    with col_graph:
        raw_data = gm.get_graph_data()
        nodes = []
        edges = []
        node_ids = set()
        node_details = {}

        # --- USE ONLINE URLS (Fixes invisible nodes) ---
        ICON_SUSPECT = "https://cdn-icons-png.flaticon.com/512/3050/3050414.png"
        ICON_CRIME = "https://cdn-icons-png.flaticon.com/512/8653/8653200.png"
        ICON_CAR = "https://cdn-icons-png.flaticon.com/512/3202/3202926.png"
        ICON_LOC = "https://cdn-icons-png.flaticon.com/512/535/535137.png"

        for record in raw_data:
            n = record['n']
            m = record['m']
            r = record['r']
            
            # --- FILTER EDGES ---
            if r.type == "CALLED" and not show_calls: continue

            def get_id(node): return getattr(node, 'element_id', getattr(node, 'id', str(node)))
            n_id, m_id = get_id(n), get_id(m)
            node_details[n_id] = dict(n)
            node_details[m_id] = dict(m)

            def create_node(node, nid):
                labels = list(node.labels)
                lbl = labels[0] if labels else "Unknown"
                
                # Filters
                if "Crime" in labels and not show_crime: return None
                if "Person" in labels and not show_person: return None
                if "Vehicle" in labels and not show_evidence: return None
                
                # Assign Icon
                img = ICON_LOC
                size = 25
                if "Person" in labels: img = ICON_SUSPECT; size=30
                elif "Crime" in labels: img = ICON_CRIME; size=35
                elif "Vehicle" in labels: img = ICON_CAR; size=30
                elif "Evidence" in labels: img = ICON_CAR; size=30

                # Label Logic
                caption = node.get('name') or node.get('number') or node.get('type') or node.get('phone') or lbl
                
                # Font Settings (White text below icon)
                font = {"color": "white", "face": "arial", "align": "bottom"}
                
                return Node(id=nid, label=caption, size=size, image=img, shape="image", font=font)

            n_obj = create_node(n, n_id)
            m_obj = create_node(m, m_id)

            if n_obj and m_obj:
                if n_id not in node_ids: nodes.append(n_obj); node_ids.add(n_id)
                if m_id not in node_ids: nodes.append(m_obj); node_ids.add(m_id)
                
                # Edge Style
                color = "#555555"
                if r.type == "CALLED": color = "#777777"
                edges.append(Edge(source=n_id, target=m_id, color=color))

        # Render Graph
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