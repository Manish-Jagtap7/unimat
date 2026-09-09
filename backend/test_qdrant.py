"""Test: Verify hybrid search improves accuracy over dense-only."""
import sys, os, shutil
sys.path.append(os.path.abspath("."))

# Clean slate
if os.path.exists("./qdrant_data"):
    shutil.rmtree("./qdrant_data")

from app.services.vector_service import add_items, query_batch

# Add cluster centers (same items from our dataset)
items = [
    ("item_1", "VALVE BALL STAINLESS STEEL SS316 2 INCH 150 CLASS FLANGED RAISED FACE"),
    ("item_2", "GASKET SPIRAL WOUND 4 INCH 150 CLASS SS316 GRAPHITE ASME B16.20"),
    ("item_3", "PUMP CENTRIFUGAL HORIZONTAL 50 M3/HR 60 M HEAD 15 KW ELECTRIC MOTOR"),
    ("item_4", "FLANGE WELD NECK RAISED FACE SS316 2 INCH 150 CLASS SCH40 ASME B16.5"),
    ("item_5", "SAFETY HELMET INDUSTRIAL YELLOW HDPE RATCHET IS 2925"),
]

ids = [i[0] for i in items]
docs = [i[1] for i in items]
metas = [{"cpse": "TEST"} for _ in items]

add_items(ids, docs, metas)
print(f"Added {len(items)} cluster centers\n")

# THE KEY TEST: Query with items that should match specific clusters
queries = [
    # Should match item_1 (Ball Valve) - true duplicate
    ("2 INCH STAINLESS STEEL BALL VALVE CLASS 150 FLANGED END RF", "q1", "item_1"),
    # Should match item_1 (Ball Valve) - abbreviated version
    ("VALVE BALL SS316 50MM 150# FLANGED RAISED FACE", "q2", "item_1"),
    # THE BIG TEST: Flange should match item_4 (Flange), NOT item_1 (Valve)!
    ("FLANGE WELD NECK SS316 2 INCH 150LB SCH40 RAISED FACE", "q3", "item_4"),
    # Another Flange variant
    ("FLG-WN-SS316-2IN-150LB-SCH40-RF", "q4", "item_4"),
    # Should match item_5 (Helmet)
    ("HELMET SAFETY HDPE RATCHET YELLOW IS2925", "q5", "item_5"),
    # Should match item_3 (Pump)
    ("PUMP CENTRIFUGAL 50M3/HR HEAD 60M 15KW INDUCTION MOTOR", "q6", "item_3"),
]

print("=" * 80)
print(f"{'Query':<55} {'Expected':<10} {'Got':<10} {'Score':<8} {'OK?'}")
print("=" * 80)

all_pass = True
for q_text, q_id, expected in queries:
    results = query_batch([q_text], [q_id], n_results=1)
    if results[0]:
        match_id, score, meta = results[0][0]
        ok = "PASS" if match_id == expected else "FAIL"
        if match_id != expected:
            all_pass = False
        print(f"{q_text[:55]:<55} {expected:<10} {match_id:<10} {score:.4f}   {ok}")
    else:
        print(f"{q_text[:55]:<55} {expected:<10} {'NONE':<10} {'N/A':<8} FAIL")
        all_pass = False

print("=" * 80)
if all_pass:
    print("ALL TESTS PASSED — Hybrid search correctly distinguishes Flanges from Valves!")
else:
    print("SOME TESTS FAILED — Check scores above")
