import os
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

    def add_fir_data(self, data, link_to_case_id=None):
        if not self.driver or not data: return
        
        # Prepare Data
        suspect = self._clean_val(data.get('suspect_name'))
        # Normalize phones to ensure matching with CDRs
        suspect_phone = self._normalize_phone(data.get('suspect_phone')) or self._normalize_phone(data.get('phone_number'))
        
        victim = self._clean_val(data.get('victim_name'))
        victim_phone = self._normalize_phone(data.get('victim_phone'))

        vehicle = self._normalize(data.get('vehicle_number'))
        crime_type = self._clean_val(data.get('crime_type'))
        location = self._clean_val(data.get('location'))
        date = data.get('date')

        params = {
            'suspect_name': suspect,
            'suspect_phone': suspect_phone,
            'victim_name': victim,
            'victim_phone': victim_phone,
            'vehicle_number': vehicle, 
            'vehicle_model': data.get('vehicle_model'),
            'crime_type': crime_type,
            'date': date,
            'location': location,
            'case_id': link_to_case_id
        }

        # Query using FOREACH hack for conditional creation
        query = """
        MERGE (c:Crime {type: $crime_type, date: $date})
        MERGE (l:Location {name: $location})
        MERGE (c)-[:OCCURRED_AT]->(l)
        
        // SUSPECT (Merge by Name, Set Phone, Case ID)
        FOREACH (_ IN CASE WHEN $suspect_name IS NOT NULL THEN [1] ELSE [] END |
            MERGE (p:Person {name: $suspect_name})
            ON CREATE SET p.origin = 'FIR', p.role = 'Suspect'
            // Always update phone and case_id
            SET p.phone = $suspect_phone, p.case_id = $case_id
            MERGE (p)-[:ACCUSED_IN]->(c)
        )
        
        // Removed Victim Logic as per request ("we only want to add the names of the suspect")
        
        // VEHICLE
        FOREACH (_ IN CASE WHEN $vehicle_number IS NOT NULL THEN [1] ELSE [] END |
            MERGE (veh:Vehicle {number: $vehicle_number})
            ON CREATE SET veh.model = $vehicle_model
            FOREACH (_ IN CASE WHEN $suspect_name IS NOT NULL THEN [1] ELSE [] END |
                MERGE (p2:Person {name: $suspect_name})
                MERGE (p2)-[:OWNS]->(veh)
            )
        )
        """
        
        # Link to Case
        if link_to_case_id:
            query += """
            MERGE (k:Case {id: $case_id})
            ON CREATE SET k.status = 'ARCHIVED'
            MERGE (c)-[:PART_OF]->(k)
            FOREACH (_ IN CASE WHEN $suspect_name IS NOT NULL THEN [1] ELSE [] END |
                MERGE (p3:Person {name: $suspect_name})
                MERGE (p3)-[:LINKED_TO]->(k)
            )
            """

        # Only run if we at least have a crime/location
        if crime_type and location:
             with self.driver.session() as session:
                session.run(query, **params)


    def add_cdr_data(self, data_list, link_to_case_id=None):
        """
        Strict CDR Ingestion:
        - Only link existing Persons (Suspects/Victims).
        - Ignore raw numbers not in DB.
        """
        if not self.driver or not data_list: return
        
        # Strict Person-Centric Match
        query = """
        MATCH (p1:Person {phone: $source})
        MATCH (p2:Person {phone: $target})
        
        MERGE (p1)-[r:CALLED]->(p2)
        SET r.weight = $weight, r.duration = $duration, r.timestamp = $timestamp
        """
        
        if link_to_case_id:
            query += "SET r.case_id = $case_id"

        with self.driver.session() as session:
            for item in data_list:
                params = {
                    'source': item.get('source'),
                    'target': item.get('destination'), 
                    'weight': item.get('weight', 1),
                    'duration': item.get('duration_sec', 0),
                    'timestamp': str(item.get('timestamp', '')),
                    'case_id': link_to_case_id
                }
                session.run(query, **params)

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