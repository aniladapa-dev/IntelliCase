def get_entity_details(driver, node_id, node_type):
    """
    Fetches deep details for a specific node to populate the Dossier.
    Note: node_id here should be the raw elementId from Neo4j.
    """
    data = {"title": "Unknown", "details": {}, "badge": None}
    
    # Map sanitised ID back to Neo4j if needed, but usually we pass the raw elementId
    # Assuming node_id is the elementId(n)
    
    with driver.session() as session:
        # ---------------------------------
        # SCENARIO 1: PERSON (Suspect)
        # ---------------------------------
        if node_type in ["Person", "Suspect"]:
            # Fetch Name, Connected Cases, and Connected Assets
            query = """
            MATCH (n) WHERE elementId(n) = $id
            OPTIONAL MATCH (n)-[:HAS_SUSPECT|INVOLVED_VEHICLE|LINKED_PHONE|PART_OF|LINKED_TO]-(c:Case)
            OPTIONAL MATCH (n)--(asset) WHERE NOT asset:Case AND NOT asset:Person
            RETURN n.name as name, collect(distinct c.id) as cases, collect(distinct coalesce(asset.number, asset.label)) as assets
            """
            res = session.run(query, id=node_id).single()
            if res:
                name = res['name'] or "Unknown Name"
                data["title"] = name
                
                # STATUS BADGE
                case_count = len(res['cases'])
                if case_count > 1:
                    data["badge"] = "🔴 REPEAT OFFENDER"
                elif case_count == 1:
                    data["badge"] = "🟠 ACTIVE SUSPECT"
                else:
                    data["badge"] = "⚪ ASSOCIATE"

                # DEEP DETAILS
                data["details"] = {
                    "Full Name": name,
                    "Criminal Record": f"Linked to {case_count} Case(s)",
                    "Case IDs": ", ".join(res['cases']) if res['cases'] else "None",
                    "Key Assets": ", ".join([str(a) for a in res['assets'] if a]) if res['assets'] else "None"
                }

        # ---------------------------------
        # SCENARIO 2: VEHICLE
        # ---------------------------------
        elif node_type == "Vehicle":
            query = """
            MATCH (n:Vehicle) WHERE elementId(n) = $id
            OPTIONAL MATCH (n)-[]-(c:Case)
            OPTIONAL MATCH (n)-[]-(p:Person)
            RETURN coalesce(n.number, n.label) as plate, collect(distinct c.id) as cases, collect(distinct p.name) as drivers
            """
            res = session.run(query, id=node_id).single()
            if res:
                plate = res['plate'] or "Unknown Plate"
                data["title"] = plate
                if len(res['cases']) > 1: data["badge"] = "⚠️ USED IN MULTIPLE CRIMES"
                
                data["details"] = {
                    "License Plate": plate,
                    "Involved In": f"{len(res['cases'])} Case(s)",
                    "FIR References": ", ".join(res['cases']) if res['cases'] else "None",
                    "Drivers/Users": ", ".join([str(d) for d in res['drivers'] if d]) if res['drivers'] else "None"
                }

        # ---------------------------------
        # SCENARIO 3: PHONE
        # ---------------------------------
        elif node_type == "Phone":
            query = """
            MATCH (n:Phone) WHERE elementId(n) = $id
            OPTIONAL MATCH (n)-[]-(c:Case)
            RETURN coalesce(n.number, n.label) as number, collect(distinct c.id) as cases
            """
            res = session.run(query, id=node_id).single()
            if res:
                num = res['number'] or "Unknown Number"
                data["title"] = num
                if len(res['cases']) > 1: data["badge"] = "🔥 BURNER PHONE (Suspected)"
                
                data["details"] = {
                    "Number": num,
                    "Linked Cases": ", ".join(res['cases']) if res['cases'] else "None"
                }

        # ---------------------------------
        # SCENARIO 4: CASE (FIR)
        # ---------------------------------
        elif node_type == "Case":
            query = """
            MATCH (n:Case) WHERE elementId(n) = $id
            RETURN n.id as fir, n.date as date, n.station as station, n.crime_type as type
            """
            res = session.run(query, id=node_id).single()
            if res:
                fir = res['fir'] or "Unknown FIR"
                data["title"] = fir
                data["details"] = {
                    "FIR ID": fir,
                    "Incident Date": res['date'] or "N/A",
                    "Police Station": res['station'] or "N/A",
                    "Primary Crime": res['type'] or "N/A"
                }

    return data
