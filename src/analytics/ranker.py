import pandas as pd

def generate_suspect_ranking(driver, focus_fir_id="Show All"):
    """
    Analyzes graph topology to rank suspects based on centrality and risk.
    Returns a list of dicts: [{Rank, Name, Score, Reasoning}]
    """
    rankings = []
    if not driver: return []
    
    # QUERY LOGIC:
    # We score Person nodes based on:
    # 1. Connectivity (Degree)
    # 2. Cross-Case Links (Critical)
    # 3. Asset Sharing (Phone/Vehicle hubs)

    # Note: Case nodes use the 'id' property for the FIR number.
    if focus_fir_id == "Show All":
        match_clause = "MATCH (p:Person)"
        params = {}
    else:
        # Focus Mode: People connected to the target FIR cluster (recursive)
        # We use a shorter hop (1..2) for ranking relevance
        match_clause = "MATCH (target:Case {id: $fir_id})-[:HAS_SUSPECT|INVOLVED_VEHICLE|LINKED_PHONE|PART_OF|LINKED_TO|CALLED|SENT_TO*1..2]-(p:Person)"
        params = {"fir_id": focus_fir_id}

    query = f"""
    {match_clause}
    
    // 1. Calculate connectivity details
    WITH distinct p
    OPTIONAL MATCH (p)-[:HAS_SUSPECT|INVOLVED_VEHICLE|LINKED_PHONE|PART_OF|LINKED_TO]-(c:Case)
    WITH p, collect(distinct c.id) as cases, count(distinct c) as case_count
    
    OPTIONAL MATCH (p)-[r]-(asset) 
    WHERE NOT asset:Case AND NOT asset:Person
    WITH p, cases, case_count, count(distinct asset) as asset_count
    
    // 2. SCORING ALGORITHM
    // Base Score: 10
    // +50 points for every EXTRA case (Cross-Case Link)
    // +10 points for every Asset (Phone/Car)
    WITH p, cases, case_count, asset_count,
         (10 + ((case_count - 1) * 50) + (asset_count * 10)) as score
    
    WHERE score > 0
    RETURN p.name as name, cases, case_count, asset_count, score
    ORDER BY score DESC LIMIT 5
    """
    
    try:
        with driver.session() as session:
            result = session.run(query, params)
            
            rank = 1
            for row in result:
                name = row['name'] or "Unknown Suspect"
                cases = row['cases']
                case_count = row['case_count']
                score = row['score']
                
                # REASONING GENERATOR
                reasons = []
                if case_count > 1:
                    reasons.append(f"🔥 **High Risk:** Linked to {case_count} Cases ({', '.join(cases)})")
                elif case_count == 1:
                    reasons.append(f"Linked to Case {cases[0]}")
                
                if row['asset_count'] > 0:
                    reasons.append(f"🔗 Connected to {row['asset_count']} Assets (Phone/Vehicle)")
                
                # Icon assignment
                icon = "🥇" if rank == 1 else ("🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}.")
                
                rankings.append({
                    "Rank": icon,
                    "Suspect": name,
                    "Risk Score": score,
                    "Intelligence Insights": " | ".join(reasons)
                })
                rank += 1
                
    except Exception as e:
        print(f"Ranking Error: {e}")
        return []

    return rankings
