import os
import random
from dotenv import load_dotenv
from neo4j import GraphDatabase
from pathlib import Path

# Load env from root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class GraphManager:
    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            # Verify connectivity
            self.driver.verify_connectivity()
        except Exception as e:
            print(f"Failed to create Neo4j driver: {e}")
            self.driver = None

    def close(self):
        if self.driver:
            self.driver.close()

    def clean_database(self):
        if not self.driver: return
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    def _clean_val(self, val):
        if val is None: return None
        s = str(val).strip()
        if s.lower() in ["none", "unknown", "n/a", "", "null"]: return None
        return s

    def _normalize(self, val):
        s = self._clean_val(val)
        if not s: return None
        # Upper + Remove space/dash
    def _normalize_phone(self, val):
        """
        Matches logic in cdr_processor.py:
        - Strip non-digits.
        - Strip leading 91.
        """
        if not val: return None
        s = str(val).strip()
        import re
        s = re.sub(r'\D', '', s)
        if s.startswith("91") and len(s) > 10:
            s = s[2:]
        return s

    def add_fir_data(self, data):
        if not self.driver or not data: return
        
        # ---------------------------------------------------------
        # FIX: Handle different key names for FIR Number
        # ---------------------------------------------------------
        # Try to find the ID in common keys
        fir_id = data.get('fir_id') or data.get('fir_number') or data.get('fir_no') or data.get('case_id')
        
        # If still None, generate a fallback ID using the suspect name or a random string
        if not fir_id:
            import uuid
            print(f"⚠️ Warning: No FIR ID found in data. Generating fallback ID. Data: {data.keys()}")
            fir_id = f"UNKNOWN_ID_{uuid.uuid4().hex[:6]}"
        
        # ---------------------------------------------------------
        # NORMALIZE DATA: Convert single values to arrays for compatibility
        # ---------------------------------------------------------
        def normalize_to_array(value):
            if isinstance(value, list):
                return [v for v in value if v and v.strip()]  # Remove empty strings
            elif value and str(value).strip():
                return [str(value).strip()]
            else:
                return []
        
        suspects = normalize_to_array(data.get('suspects') or data.get('suspect_name'))
        vehicles = normalize_to_array(data.get('vehicles') or data.get('vehicle_number'))
        phones = normalize_to_array(data.get('phones') or data.get('suspect_phone'))
        
        # ---------------------------------------------------------

        query = """
        // 1. Merge the Central Case Node (The Hub)
        MERGE (c:Case {id: $fir_id})
        SET c.type = $crime_type, 
            c.date = $date, 
            c.station = $station,
            c.label = "📁 " + $fir_id  // Folder Icon

        // 2. Link Suspects
        FOREACH (name IN $suspects | 
            MERGE (p:Person {name: name}) 
            SET p.label = name // Silhouette Icon removed
            
            // SMART LINKING: If we have exactly 1 suspect and >0 phones, assign first phone to person
            FOREACH (ignoreMe IN CASE WHEN size($suspects) = 1 AND size($phone_numbers) > 0 THEN [1] ELSE [] END |
                SET p.phone = head($phone_numbers) 
            )
            
            MERGE (c)-[:HAS_SUSPECT]->(p))

        // 3. Link Vehicles
        FOREACH (num IN $vehicle_numbers | 
            MERGE (v:Vehicle {number: num}) 
            SET v.label = num // Car Icon removed
            MERGE (c)-[:INVOLVED_VEHICLE]->(v))

        // 4. Link Phones
        FOREACH (num IN $phone_numbers | 
            MERGE (ph:Phone {number: num}) 
            SET ph.label = num // Phone Icon removed
            MERGE (c)-[:LINKED_PHONE]->(ph))
        """
        
        with self.driver.session() as session:
            session.run(query, 
                fir_id=fir_id,
                crime_type=data.get('crime_type', 'Unknown'),
                date=data.get('date', 'Unknown Date'),
                station=data.get('station', 'Unknown Station'),
                suspects=suspects,
                vehicle_numbers=vehicles,
                phone_numbers=phones
            )

    def add_cdr_data(self, data_list, link_to_case_id=None):
        """
        CDR Ingestion with SMART LINKING:
        - Checks if Person exists with phone number.
        - If yes, links call directly to Person.
        - If no, links to Phone node.
        """
        if not self.driver or not data_list: return
        
        # New Query Logic (Fixed Syntax)
        query = """
        UNWIND $calls AS call
        
        // --- 1. Handle Source ---
        OPTIONAL MATCH (p1:Person {phone: call.source})
        // Conditionally create Phone if Person not found
        FOREACH (_ IN CASE WHEN p1 IS NULL THEN [1] ELSE [] END | 
            MERGE (ph1:Phone {number: call.source}) 
            ON CREATE SET ph1.label = "📞 " + call.source
        )
        // Select the correct node (Person or Phone)
        WITH call
        MATCH (source) 
        WHERE (source:Person AND source.phone = call.source) OR (source:Phone AND source.number = call.source)
        WITH call, head(collect(source)) AS source

        // --- 2. Handle Target ---
        OPTIONAL MATCH (p2:Person {phone: call.destination})
        FOREACH (_ IN CASE WHEN p2 IS NULL THEN [1] ELSE [] END | 
            MERGE (ph2:Phone {number: call.destination}) 
            ON CREATE SET ph2.label = "📞 " + call.destination
        )
        WITH call, source
        MATCH (target) 
        WHERE (target:Person AND target.phone = call.destination) OR (target:Phone AND target.number = call.destination)
        WITH call, source, head(collect(target)) AS target
        
        // --- 3. Create Edge ---
        MERGE (source)-[r:CALLED]->(target)
        SET r.date = call.date,
            r.time = call.time,
            r.duration = call.duration,
            r.title = "📅 " + toString(call.date) + " | ⏳ " + toString(call.duration) + "s"
        """
        if link_to_case_id:
            query += " SET r.case_id = $case_id"
            
        # Convert incoming list ... (Rest is same)
        if link_to_case_id:
            query += " SET r.case_id = $case_id"
            
        # Convert incoming list of dicts to params if needed, but data_list is already list of dicts
        # We need to ensure keys match: source, destination, date, time, duration
        # Existing process_cdr returns: source, destination, timestamp, duration_sec...
        # We need to adapt data_list to match query params 'call'
        
        formatted_calls = []
        for d in data_list:
            formatted_calls.append({
                'source': d.get('source'),
                'destination': d.get('destination'),
                'date': str(d.get('timestamp', '')), # Simplified
                'time': str(d.get('timestamp', '')), 
                'duration': d.get('duration_sec', 0)
            })

        with self.driver.session() as session:
            session.run(query, calls=formatted_calls, case_id=link_to_case_id)

    def add_cctv_data(self, data, link_to_case_id=None):
        if not self.driver or not data: return
        
        detected_texts = data.get('detected_text', [])
        vehicle_num = data.get('vehicle_number') # If smart extractor found it
        
        # Prefer vehicle number if found
        to_process = [vehicle_num] if vehicle_num else detected_texts
        
        query = """
        MATCH (v:Vehicle) WHERE v.number = $text
        MERGE (e:Evidence {type: "CCTV_Image"})
        MERGE (v)-[:CAPTURED_IN]->(e)
        """
        
        if link_to_case_id:
            query += """
            MERGE (k:Case {id: $case_id})
            ON CREATE SET k.status = 'ARCHIVED'
            MERGE (v)-[:LINKED_TO]->(k)
            MERGE (e)-[:PART_OF]->(k)
            """
            
        with self.driver.session() as session:
            for text in to_process:
                clean_text = self._normalize(text)
                if not clean_text: continue 
                
                params = {'text': clean_text}
                if link_to_case_id:
                    params['case_id'] = link_to_case_id
                session.run(query, **params)

    def add_bank_data(self, data, link_to_case_id=None):
        if not self.driver or not data: return
        
        transactions = data.get('transactions', [])
        
        query = """
        MERGE (t:Transaction {signature: $date + '_' + $amount + '_' + $description})
        SET t.amount = $amount, t.date = $date, t.description = $description, t.type = 'Bank_Tx'
        
        WITH t
        MATCH (p:Person) WHERE t.description CONTAINS p.name
        MERGE (t)-[:SENT_TO]->(p)
        """
        
        if link_to_case_id:
            query += """
            WITH t
            MERGE (k:Case {id: $case_id})
            ON CREATE SET k.status = 'ARCHIVED'
            MERGE (t)-[:PART_OF]->(k)
            """

        with self.driver.session() as session:
            for tx in transactions:
                params = tx.copy()
                if link_to_case_id:
                    params['case_id'] = link_to_case_id
                session.run(query, **params)

    def get_graph_data(self):
        if not self.driver: return []
        
        query = "MATCH (n)-[r]->(m) RETURN n, r, m"
        results = []
        with self.driver.session() as session:
            result = session.run(query)
            for record in result:
                results.append(record)
        return results

    def get_dashboard_stats(self):
        """Fetches counts, timeline, station stats, map data, and sunburst data."""
        stats = {
            "cases": 0, "suspects": 0, "vehicles": 0, "phones": 0,
            "recent_cases": [], "crime_types": {},
            "timeline": [], "stations": {},
            "map_data": [], "sunburst_data": []
        }
        
        # SMART GEOCODING: Major Indian City Hubs (Lat, Lon)
        CITY_HUBS = {
            "Delhi": [28.6139, 77.2090], "Mumbai": [19.0760, 72.8777],
            "Bangalore": [12.9716, 77.5946], "Hyderabad": [17.3850, 78.4867],
            "Chennai": [13.0827, 80.2707], "Kolkata": [22.5726, 88.3639],
            "Pune": [18.5204, 73.8567], "Ahmedabad": [23.0225, 72.5714],
            "Jaipur": [26.9124, 75.7873], "Kochi": [9.9312, 76.2673],
            "Indiranagar": [12.9716, 77.5946], # Mapping specific stations
            "Panjagutta": [17.3850, 78.4867],
            "Aluva": [9.9312, 76.2673],
            "Saket": [28.6139, 77.2090],
            "Andheri": [19.1136, 72.8697]
        }

        try:
            with self.driver.session() as session:
                # 1. Basic Counts
                q_counts = "MATCH (c:Case) WITH count(c) as cases OPTIONAL MATCH (p:Person) WITH cases, count(p) as suspects OPTIONAL MATCH (v:Vehicle) WITH cases, suspects, count(v) as vehicles OPTIONAL MATCH (ph:Phone) WITH cases, suspects, vehicles, count(ph) as phones RETURN cases, suspects, vehicles, phones"
                res = session.run(q_counts).single()
                if res:
                    stats["cases"] = res["cases"]
                    stats["suspects"] = res["suspects"]
                    stats["vehicles"] = res["vehicles"]
                    stats["phones"] = res["phones"]

                # 2. Visuals: Map & Sunburst
                map_points = []
                sunburst_rows = []
                
                # Note: c.type used instead of c.crime_type to match DB schema
                q_visuals = "MATCH (c:Case) RETURN c.station as station, c.type as type, count(c) as count"
                for row in session.run(q_visuals):
                    st_name = row['station'] if row['station'] else "Unknown"
                    c_type = row['type']
                    count = row['count']
                    
                    sunburst_rows.append({"station": st_name, "type": c_type, "count": count})
                    
                    # Geocoding Logic
                    found_coords = None
                    for city, coords in CITY_HUBS.items():
                        if city.lower() in st_name.lower():
                            found_coords = coords
                            break
                    
                    if found_coords:
                        base_lat, base_lon = found_coords
                        for _ in range(count):
                            # Add Jitter (Approx 2km) for realistic clustering
                            map_points.append({
                                "lat": base_lat + random.uniform(-0.02, 0.02),
                                "lon": base_lon + random.uniform(-0.02, 0.02)
                            })
                
                stats["map_data"] = map_points
                stats["sunburst_data"] = sunburst_rows
                
                # 3. Analytics: Timeline & Stations
                stats["timeline"] = [dict(row) for row in session.run("MATCH (c:Case) RETURN c.date as date, count(c) as count ORDER BY c.date ASC")]
                stats["stations"] = {row["station"]: row["count"] for row in session.run("MATCH (c:Case) RETURN c.station as station, count(c) as count ORDER BY count DESC LIMIT 10")}
                # Note: c.type used instead of c.crime_type to match DB schema
                stats["crime_types"] = {row["type"]: row["count"] for row in session.run("MATCH (c:Case) RETURN c.type as type, count(c) as count")}
                # Note: c.id used instead of c.fir_id to match DB schema, c.type instead of c.crime_type
                stats["recent_cases"] = [dict(r) for r in session.run("MATCH (c:Case) RETURN c.id as FIR_ID, c.station as Station, c.date as Date, c.type as Crime ORDER BY c.date DESC LIMIT 5")]

        except Exception as e:
            print(f"Error fetching stats: {e}")
        return stats