"""Clear Qdrant vector database collection."""
from qdrant_client import QdrantClient

try:
    client = QdrantClient(path="./qdrant_data")
    if client.collection_exists("material_master"):
        client.delete_collection("material_master")
        print("SUCCESS: Deleted Qdrant collection 'material_master'")
    else:
        print("Collection 'material_master' does not exist.")
    client.close()
except Exception as e:
    print("Error:", e)
