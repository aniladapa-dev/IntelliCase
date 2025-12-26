import sys
import os

# Add src to python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.graph_manager import GraphManager

def main():
    print("Initializing GraphManager...")
    gm = GraphManager()
    
    if gm.driver:
        print("Driver created. Attempting to clear database...")
        try:
            gm.clean_database()
            print("Database cleaned.")
            
            with gm.driver.session() as session:
                result = session.run("RETURN 1")
                record = result.single()
                if record and record[0] == 1:
                    print("✅ Docker Connection Successful!")
        except Exception as e:
            print(f"❌ Connection/Query failed: {e}")
        finally:
            gm.close()
    else:
        print("❌ Failed to initialize driver (Check .env credentials)")

if __name__ == "__main__":
    main()
