from src.graph_manager import GraphManager

def verify():
    gm = GraphManager()
    if not gm.driver:
        print("❌ Could not connect to Neo4j.")
        return

    with gm.driver.session() as session:
        result = session.run("MATCH (n) RETURN count(n) as count")
        node_count = result.single()["count"]
        
        result_edges = session.run("MATCH ()-[r]->() RETURN count(r) as count")
        edge_count = result_edges.single()["count"]

    print(f"✅ Connection Successful.")
    print(f"📊 Graph Stats:")
    print(f"   - Nodes: {node_count}")
    print(f"   - Relationships: {edge_count}")
    
    if node_count == 0:
        print("\n⚠️  The graph is EMPTY. Please run 'Sync National DB' or upload files in the app.")
    else:
        print("\n✅ Data is present. If graph is hidden, check UI rendering.")

    gm.close()

if __name__ == "__main__":
    verify()
