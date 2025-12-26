# src/graph_manager.py
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

class GraphManager:
    def __init__(self):
        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USER")
        password = os.getenv("NEO4J_PASSWORD")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def clean_database(self):
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    def add_fir_data(self, data):
        with self.driver.session() as session:
            # 1. Create Crime & Location
            session.run("""
                MERGE (c:Crime {type: $crime_type, date: $date})
                MERGE (l:Location {name: $location})
                MERGE (c)-[:OCCURRED_AT]->(l)
            """, data)
            
            # 2. Link Suspect (if exists)
            if data.get('suspect_name'):
                session.run("""
                    MATCH (c:Crime {type: $crime_type, date: $date})
                    MERGE (p:Person {name: $suspect_name})
                    MERGE (p)-[:ACCUSED_IN]->(c)
                """, data)
            
            # 3. Link Vehicle (if exists)
            if data.get('vehicle_number'):
                session.run("""
                    MATCH (c:Crime {type: $crime_type, date: $date})
                    MERGE (v:Vehicle {number: $vehicle_number})
                    SET v.model = $vehicle_model
                    MERGE (v)-[:USED_IN]->(c)
                """, data)

            # 4. Link Suspect <-> Vehicle (if both exist)
            if data.get('suspect_name') and data.get('vehicle_number'):
                session.run("""
                    MATCH (p:Person {name: $suspect_name})
                    MATCH (v:Vehicle {number: $vehicle_number})
                    MERGE (p)-[:OWNS_OR_DRIVES]->(v)
                """, data)

    def add_cdr_data(self, data_list):
        with self.driver.session() as session:
            for item in data_list:
                session.run("""
                    MERGE (p1:Person {phone: $source})
                    MERGE (p2:Person {phone: $target})
                    MERGE (p1)-[r:CALLED]->(p2)
                    SET r.weight = $weight, r.duration = $duration
                """, item)

    def add_cctv_data(self, data):
        with self.driver.session() as session:
            if data.get('detected_text'):
                for text in data['detected_text']:
                    if len(text) > 4: 
                        session.run("""
                            MATCH (v:Vehicle) 
                            WHERE v.number CONTAINS $text OR $text CONTAINS v.number
                            MERGE (e:Evidence {type: "CCTV_Image"})
                            MERGE (v)-[:CAPTURED_IN]->(e)
                            SET e.text = $text
                        """, {"text": text})

    def get_graph_data(self):
        with self.driver.session() as session:
            # We return the RAW result, not .data()
            result = session.run("MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 100")
            return list(result)