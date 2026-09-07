import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from app.database import SessionLocal
from app.models import MaterialItem

db = SessionLocal()

# Find the item with legacy code IOCL-M-100452
parent = db.query(MaterialItem).filter(MaterialItem.legacy_item_code == "IOCL-M-100452").first()
if not parent:
    print("Parent not found!")
    sys.exit(0)

print(f"Parent: {parent.id} {parent.cpse_source} {parent.raw_description}")
print(f"Classification: {parent.classification}")
print(f"Matched Material ID: {parent.matched_material_id}")

children = db.query(MaterialItem).filter(MaterialItem.matched_material_id == parent.id).all()
print(f"\nChildren count: {len(children)}")
for c in children:
    print(f" - {c.id} {c.cpse_source} {c.legacy_item_code} {c.classification} ({c.similarity_score}): {c.raw_description[:60]}")

db.close()
