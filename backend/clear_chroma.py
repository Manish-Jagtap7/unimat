import chromadb
import shutil
import os

try:
    client = chromadb.PersistentClient(path="./chroma_data")
    client.delete_collection("material_master")
    print("SUCCESS: Deleted collection material_master")
except Exception as e:
    print("Error deleting via client:", e)
    
try:
    if os.path.exists("./chroma_data"):
        print("Folder exists, but we'll leave it as is if collection deleted.")
except Exception as e:
    print("Error:", e)
