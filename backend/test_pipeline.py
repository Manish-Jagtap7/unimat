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
time.sleep(20)

print("\n=== ALL items ===")
resp = requests.get(f"{BASE_URL}/api/materials?page_size=200")
items = resp.json()["items"]

from collections import Counter, defaultdict
print(f"Total: {len(items)}")
print(f"Classifications: {dict(Counter(m['classification'] for m in items))}")

parents = [m for m in items if m["cluster_number"] is not None]
children = [m for m in items if m["matched_material_id"] is not None]
singletons = [m for m in items if m["cluster_number"] is None and m["matched_material_id"] is None]
print(f"Cluster Parents: {len(parents)}, Children: {len(children)}, Singletons: {len(singletons)}")

# Check for chain bug: does any child point to another child?
child_ids = {m["id"] for m in children}
for child in children:
    if child["matched_material_id"] in child_ids:
        print(f"  ⚠️ CHAIN BUG! Item {child['id']} points to child {child['matched_material_id']} instead of root parent!")

# Show clusters sorted
print("\nClusters (sorted):")
clusters = defaultdict(list)
parent_map = {p["id"]: p for p in parents}
for c in children:
    clusters[c["matched_material_id"]].append(c)

for p in sorted(parents, key=lambda x: x["cluster_number"]):
    kids = clusters.get(p["id"], [])
    kid_info = [f"{c['cpse_source']}:{c['classification']}({c['similarity_score']})" for c in kids]
    print(f"  Cluster {p['cluster_number']}: {p['cpse_source']} '{p['raw_description'][:50]}' -> {len(kids)} children: {kid_info}")

print(f"\n=== CLUSTER filter ===")
resp = requests.get(f"{BASE_URL}/api/materials?page_size=200&filter_mode=CLUSTER")
print(f"Items: {len(resp.json()['items'])}")

print(f"\n=== UNIQUE filter ===")
resp = requests.get(f"{BASE_URL}/api/materials?page_size=200&filter_mode=UNIQUE")
print(f"Items: {len(resp.json()['items'])}")
