import streamlit as st
from src.utils.static_icons import StaticIcons
import hashlib

# 1. ICON MAP & PALETTE
ICON_MAP = {
    "Case": StaticIcons.CASE,
    "Person": StaticIcons.PERSON,
    "Vehicle": StaticIcons.VEHICLE,
    "Phone": StaticIcons.PHONE,
    "Location": StaticIcons.LOCATION,
    "Money": StaticIcons.MONEY,
    "Crime": StaticIcons.CRIME,
    "Transaction": StaticIcons.MONEY
}

CASE_PALETTE = [
    "#FF9F40", "#4BC0C0", "#9966FF", "#FF6384", "#36A2EB", 
    "#FFCD56", "#C9CBCF", "#71B37C"
]

def get_case_color(case_id):
    if not case_id: return "#888888"
    hash_val = int(hashlib.sha256(str(case_id).encode('utf-8')).hexdigest(), 16)
    return CASE_PALETTE[hash_val % len(CASE_PALETTE)]

def clean_label(lbl, node_type):
    if not lbl: return node_type
    for symbol in ["👤", "🚙", "📞", "🛡️", "💰", "🚗", "🚙"]:
        lbl = lbl.replace(symbol, "")
    lbl = lbl.strip()
    if lbl == node_type or not lbl: return node_type
    if node_type == "Person" and "Person_" in lbl: return "Unknown"
    return lbl

# 2. STYLESHEET (STRICT NO LABELS BY DEFAULT)
STYLESHEET = [
    {
        "selector": "node",
        "style": {
            "label": "data(label)",
            "width": "60px",
            "height": "60px",
            "background-fit": "cover",
            "background-image": "data(icon)",
            "background-color": "white",
            "border-width": 0,
            "font-size": "12px",
            "text-valign": "bottom",
            "text-margin-y": "5px",
            "color": "#333",
            "text-background-opacity": 0.8,
            "text-background-color": "white",
            "text-background-padding": "2px"
        }
    },
    {
        "selector": "edge",
        "style": {
            "width": "data(width)",
            "line-color": "data(color)",
            "line-style": "data(style)",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "data(color)",
            "curve-style": "bezier",
            "opacity": 0.8,
            # FORCE HIDE LABELS
            "label": "",
            "text-opacity": 0
        }
    },
    {
        "selector": "edge:selected",
        "style": {
            "label": "data(label)",
            "text-opacity": 1,
            "width": 4,
            "line-color": "#000000",
            "target-arrow-color": "#000000",
            "text-background-opacity": 1,
            "text-background-color": "#FFFFFF",
            "font-size": "11px",
            "color": "black"
        }
    }
]

# 3. DATA GENERATOR
def get_cytoscape_elements(driver, focus_fir_id="Show All"):
    elements = []
    node_metadata = {}
    
    try:
        with driver.session() as session:
            # MODE 1: SHOW ALL
            if focus_fir_id == "Show All":
                query_nodes = """
                MATCH (n) 
                OPTIONAL MATCH (n)-[:HAS_SUSPECT|INVOLVED_VEHICLE|LINKED_PHONE|PART_OF|LINKED_TO]-(c:Case)
                RETURN elementId(n) as id, n.label as label, n.name as name, n.number as number, 
                       labels(n) as types, collect(distinct c.id) as fir_ids, n.id as self_fir
                """
                edge_elements = []
                nodes_with_edges = set()
                
                for rec in session.run(query_nodes):
                    raw_id = rec['id']
                    safe_id = raw_id.replace(":", "_")
                    types = rec['types']
                    node_type = types[0] if types else "Unknown"
                    
                    fir_ids = set([f for f in rec['fir_ids'] if f])
                    if node_type == "Case" and rec['self_fir']:
                        fir_ids.add(rec['self_fir'])
                    
                    if len(fir_ids) == 1:
                        node_color = get_case_color(list(fir_ids)[0])
                    elif len(fir_ids) > 1:
                        node_color = "#FF0000" 
                    else:
                        node_color = "#888888"

                    node_metadata[safe_id] = {"fir_ids": fir_ids, "color": node_color, "type": node_type}
                    raw_lbl = rec.get("label") or rec.get("name") or rec.get("number") or node_type
                    
                    elements.append({
                        "data": {
                            "id": safe_id,
                            "label": clean_label(raw_lbl, node_type),
                            "type": node_type,
                            "color": node_color,
                            "icon": ICON_MAP.get(node_type, StaticIcons.DEFAULT),
                            "raw_id": raw_id
                        }
                    })

                query_edges = "MATCH (s)-[r]->(t) RETURN elementId(s) as source, elementId(t) as target, type(r) as label"
                for rec in session.run(query_edges):
                    src_safe = rec['source'].replace(":", "_")
                    tgt_safe = rec['target'].replace(":", "_")
                    if src_safe in node_metadata and tgt_safe in node_metadata:
                        src_meta = node_metadata[src_safe]
                        tgt_meta = node_metadata[tgt_safe]
                        common = src_meta["fir_ids"].intersection(tgt_meta["fir_ids"])
                        
                        if common:
                            edge_color = get_case_color(list(common)[0])
                            style, width = "solid", 2
                        elif src_meta["fir_ids"] and tgt_meta["fir_ids"]:
                            edge_color, style, width = "#FF0000", "dashed", 4
                        else:
                            edge_color, style, width = "#CCCCCC", "solid", 2

                        edge_elements.append({
                            "data": {
                                "source": src_safe, "target": tgt_safe,
                                "label": rec['label'],
                                "color": edge_color, "style": style, "width": width
                            }
                        })
                        nodes_with_edges.add(src_safe)
                        nodes_with_edges.add(tgt_safe)

                # Orphan filtering
                filtered_nodes = []
                for node in elements:
                    nid = node['data']['id']
                    meta = node_metadata.get(nid, {})
                    if meta.get("type") == "Transaction" and nid not in nodes_with_edges and not meta.get("fir_ids"):
                        continue
                    filtered_nodes.append(node)
                
                elements = filtered_nodes + edge_elements

            # MODE 2: FOCUS MODE (Recursive Cluster Detection)
            else:
                target_case_id = focus_fir_id
                query_relevant_cases = """
                MATCH (target:Case {id: $fir_id})
                OPTIONAL MATCH (target)-[:HAS_SUSPECT|INVOLVED_VEHICLE|LINKED_PHONE|PART_OF|LINKED_TO|CALLED|SENT_TO*..10]-(other:Case)
                RETURN collect(distinct other.id) + [$fir_id] as fir_ids
                """
                res = session.run(query_relevant_cases, fir_id=target_case_id)
                relevant_fir_ids = res.single()['fir_ids'] if res.peek() else [target_case_id]
                
                found_node_ids = set()
                query_cases = "MATCH (c:Case) WHERE c.id IN $fir_ids RETURN elementId(c) as id, c.id as fir_id"
                for rec in session.run(query_cases, fir_ids=relevant_fir_ids):
                    raw_id = rec['id']
                    safe_id = raw_id.replace(":", "_")
                    fir_id = rec['fir_id']
                    node_color = get_case_color(fir_id)
                    node_metadata[safe_id] = {"fir_ids": {fir_id}, "color": node_color, "type": "Case"}
                    elements.append({
                        "data": {
                            "id": safe_id, "label": fir_id, "type": "Case", 
                            "color": node_color, "icon": ICON_MAP["Case"],
                            "raw_id": raw_id
                        }
                    })
                    found_node_ids.add(raw_id)

                query_nodes = """
                MATCH (n)-[:HAS_SUSPECT|INVOLVED_VEHICLE|LINKED_PHONE|PART_OF|LINKED_TO]-(c:Case)
                WHERE c.id IN $fir_ids
                RETURN elementId(n) as id, n.label as label, n.name as name, n.number as number, 
                       labels(n) as types, collect(distinct c.id) as fir_ids
                """
                for rec in session.run(query_nodes, fir_ids=relevant_fir_ids):
                    raw_id = rec['id']
                    if raw_id in found_node_ids: continue
                    safe_id = raw_id.replace(":", "_")
                    node_type = rec['types'][0] if rec['types'] else "Unknown"
                    fir_ids = set([f for f in rec['fir_ids'] if f])
                    
                    if len(fir_ids) == 1: color = get_case_color(list(fir_ids)[0])
                    elif len(fir_ids) > 1: color = "#FF0000"
                    else: color = "#888888"

                    node_metadata[safe_id] = {"fir_ids": fir_ids, "color": color, "type": node_type}
                    raw_lbl = rec.get("label") or rec.get("name") or rec.get("number") or node_type
                    elements.append({
                        "data": {
                            "id": safe_id, "label": clean_label(raw_lbl, node_type),
                            "type": node_type, "color": color, "icon": ICON_MAP.get(node_type, StaticIcons.DEFAULT),
                            "raw_id": raw_id
                        }
                    })
                    found_node_ids.add(raw_id)

                query_edges = """
                MATCH (s)-[r]->(t)
                WHERE elementId(s) IN $n_ids AND elementId(t) IN $n_ids
                RETURN elementId(s) as source, elementId(t) as target, type(r) as label
                """
                for rec in session.run(query_edges, n_ids=list(found_node_ids)):
                    src_safe, tgt_safe = rec['source'].replace(":", "_"), rec['target'].replace(":", "_")
                    src_m, tgt_m = node_metadata.get(src_safe, {}), node_metadata.get(tgt_safe, {})
                    common = src_m.get("fir_ids", set()).intersection(tgt_m.get("fir_ids", set()))
                    
                    if common: color, style, width = get_case_color(list(common)[0]), "solid", 2
                    elif src_m.get("fir_ids") and tgt_m.get("fir_ids"): color, style, width = "#FF0000", "dashed", 4
                    else: color, style, width = "#CCCCCC", "solid", 2

                    elements.append({
                        "data": {
                            "source": src_safe, "target": tgt_safe,
                            "label": rec['label'], "color": color, "style": style, "width": width
                        }
                    })

    except Exception as e:
        st.error(f"Error fetching Cytoscape elements: {e}")
        
    return elements
