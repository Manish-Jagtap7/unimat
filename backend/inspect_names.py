import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from app.database import SessionLocal
from app.models import MaterialItem, NationalCode

db = SessionLocal()

items = db.query(MaterialItem).filter(MaterialItem.matched_cnmc_id != None).all()
print(f"Items with CNMC: {len(items)}")

ncs = db.query(NationalCode).all()
for nc in ncs:
    print(f"CNMC: {nc.cnmc_code} - {nc.standardized_description}")

db.close()
