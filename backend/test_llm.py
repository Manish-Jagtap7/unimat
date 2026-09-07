import requests
import time

BASE_URL = "http://localhost:8000"

print("Uploading file...")
with open("../CPSE_Material_Master_Benchmark_Dataset.xlsx", "rb") as f:
    files = {"files": ("CPSE_Material_Master_Benchmark_Dataset.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    data = {"cpse_codes": "MIXED"}
    resp = requests.post(f"{BASE_URL}/api/upload", files=files, data=data)
    
session_ids = [s["id"] for s in resp.json()["sessions"]]
print(f"Uploaded, session_ids={session_ids}")

print("Running pipeline...")
requests.post(f"{BASE_URL}/api/pipeline/run", json={
    "session_ids": session_ids,
    "dup_threshold": 0.95,
    "near_dup_threshold": 0.85
})
time.sleep(15)

print("\nGenerating LLM names...")
requests.post(f"{BASE_URL}/api/materials/generate-names")
time.sleep(15) # Wait for Gemini to finish

print("\n=== Clusters ===")
resp = requests.get(f"{BASE_URL}/api/materials?page_size=200")
items = resp.json()["items"]

parents = [m for m in items if m["cluster_number"] is not None]
children = [m for m in items if m["matched_material_id"] is not None]

from collections import defaultdict
child_map = defaultdict(list)
for c in children:
    child_map[c["matched_material_id"]].append(c)

for p in sorted(parents, key=lambda x: x["cluster_number"]):
    kids = child_map.get(p["id"], [])
    print(f"Cluster {p['cluster_number']}: {p['standardized_description']} ({len(kids)} children)")
    print(f"  Parent: {p['cpse_source']} - {p['raw_description']}")
    for k in kids:
        print(f"  Child: {k['cpse_source']} - {k['raw_description']}")
    print("-" * 40)
