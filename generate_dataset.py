"""
generate_dataset.py — Creates a realistic synthetic Excel dataset for the UniMat AI prototype.

This script produces ~105 rows of messy, duplicated material descriptions from
various Central Public Sector Enterprises (CPSEs) to simulate the real-world
challenge of "One Nation – One Material Code".

Each cluster of items represents the SAME physical material, but described differently
by different organizations — with varying abbreviations, formats, and naming conventions.
"""

import pandas as pd
import random
import string

# ─── Seed for reproducibility ──────────────────────────────────────────────────
random.seed(42)

# ─── Define CPSEs ──────────────────────────────────────────────────────────────
CPSES = ["IOCL", "ONGC", "CPCL", "BPCL", "GAIL", "HPCL"]

# ─── Define material clusters ─────────────────────────────────────────────────
# Each cluster has:
#   - cluster_id: Ground truth cluster label
#   - unified_code: The target standardized national code
#   - std_desc: Target standardized description
#   - uom: Unit of Measure
#   - variants: List of messy raw descriptions that all refer to the SAME item
CLUSTERS = [
    {
        "cluster_id": "CLUSTER_001",
        "unified_code": "NAT-VLV-BALL-001",
        "std_desc": "Ball Valve, SS316, 2 Inch, Class 150, Flanged, Raised Face",
        "uom": "NOS",
        "variants": [
            "VLV-BALL-SS316-2IN-150#-FLG-RF",
            "2 Inch Stainless Steel Ball Valve Class 150",
            "BALL VALVE 2\" 150LB SS316 FLANGED RF",
            "SS316 BALL VLV, 50MM, CL150, FLANGED END",
            "Ball Valve - SS 316 - 2 inch - ANSI 150 - Flanged",
        ],
    },
    {
        "cluster_id": "CLUSTER_002",
        "unified_code": "NAT-VLV-GATE-001",
        "std_desc": "Gate Valve, CS (A216 WCB), 4 Inch, Class 300, Flanged",
        "uom": "NOS",
        "variants": [
            "GTE VLV CS WCB 4IN 300# FLG",
            "Gate Valve 4 inch Carbon Steel Class 300 Flanged",
            "GATE VALVE - A216 WCB - 4\" - 300LB - FLANGED",
            "CS Gate Valve, DN100, CL300, Flanged End",
            "4 IN GATE VLV CARBON STL 300LB",
        ],
    },
    {
        "cluster_id": "CLUSTER_003",
        "unified_code": "NAT-PIPE-CS-001",
        "std_desc": "Seamless Pipe, Carbon Steel, A106 Gr.B, 6 Inch, Sch 40",
        "uom": "MTR",
        "variants": [
            "PIPE SMLS CS A106 GR.B 6\" SCH40",
            "6 inch Seamless Carbon Steel Pipe Schedule 40",
            "CS SMLS PIPE - A106 GR B - 6IN - SCH 40",
            "Seamless Pipe 6\" CS ASTM A106 Gr.B SCH-40",
            "CARBON STEEL PIPE, SEAMLESS, DN150, SCH40, A106B",
        ],
    },
    {
        "cluster_id": "CLUSTER_004",
        "unified_code": "NAT-FLG-WNRF-001",
        "std_desc": "Flange, Weld Neck Raised Face, A105, 4 Inch, Class 150",
        "uom": "NOS",
        "variants": [
            "FLG WNRF A105 4IN 150#",
            "Weld Neck RF Flange 4\" 150LB A105",
            "4 INCH WNRF FLANGE CS A105 CL150",
            "FLANGE, WELD NECK, RF, A105, DN100, 150LB",
            "A105 Weld-Neck Raised Face Flange 4 inch Class 150",
        ],
    },
    {
        "cluster_id": "CLUSTER_005",
        "unified_code": "NAT-GSKT-SW-001",
        "std_desc": "Gasket, Spiral Wound, SS316/Graphite, 4 Inch, Class 150",
        "uom": "NOS",
        "variants": [
            "GSKT SPIRAL WOUND SS316/GRAPHITE 4IN 150#",
            "Spiral Wound Gasket 4\" SS316 Graphite Fill Cl.150",
            "SPIRAL WOUND GASKET, SS316/GRAPH, DN100, CL150",
            "4 inch SW Gasket - SS 316 - Graphite Filler - 150LB",
            "SWG SS316/GRAPHITE 4\" 150#",
        ],
    },
    {
        "cluster_id": "CLUSTER_006",
        "unified_code": "NAT-BLT-STUD-001",
        "std_desc": "Stud Bolt, B7/2H, 5/8 Inch x 4.5 Inch, with 2 Nuts",
        "uom": "SET",
        "variants": [
            "STUD BOLT B7/2H 5/8\" x 4-1/2\" C/W 2 NUTS",
            "Stud Bolt ASTM A193 B7 with A194 2H Nut 5/8 x 4.5",
            "B7/2H STUD BOLT 5/8IN x 4.5IN WITH NUTS",
            "STUD BOLT SET - B7 - 5/8\" DIA x 4-1/2\" LG - 2H NUTS",
        ],
    },
    {
        "cluster_id": "CLUSTER_007",
        "unified_code": "NAT-PUMP-CENT-001",
        "std_desc": "Centrifugal Pump, Horizontal, API 610, 100 m³/hr, 80m Head",
        "uom": "NOS",
        "variants": [
            "PUMP CENTRFGL HORIZ API610 100M3/HR 80M HD",
            "Horizontal Centrifugal Pump API 610 100 cum/hr 80m",
            "API 610 Centrifugal Pump, Horizontal, Q=100m3/h, H=80m",
            "CENT. PUMP - HORIZONTAL - API610 - 100 CU.M/HR - 80MTR HEAD",
            "Centrifugal Pump Horizontal API-610 Flow 100m³/hr Head 80m",
        ],
    },
    {
        "cluster_id": "CLUSTER_008",
        "unified_code": "NAT-BRG-BALL-001",
        "std_desc": "Ball Bearing, Deep Groove, 6205-2RS, 25x52x15mm",
        "uom": "NOS",
        "variants": [
            "BEARING BALL DG 6205-2RS 25x52x15",
            "Deep Groove Ball Bearing 6205-2RS 25x52x15mm",
            "BALL BRG 6205-2RS DEEP GROOVE 25X52X15MM",
            "6205-2RS Deep Groove Ball Bearing - 25mm Bore",
            "DG BALL BEARING - 6205-2RS - 25/52/15 MM",
        ],
    },
    {
        "cluster_id": "CLUSTER_009",
        "unified_code": "NAT-CABLE-PWR-001",
        "std_desc": "Power Cable, XLPE, 3.5C x 240 sq.mm, 11kV, Armoured",
        "uom": "MTR",
        "variants": [
            "CABLE PWR XLPE 3.5Cx240SQMM 11KV ARM",
            "Power Cable 3.5 Core 240 Sq mm XLPE 11kV Armoured",
            "11KV XLPE POWER CABLE 3.5Cx240 SQ.MM ARMOURED",
            "XLPE CABLE 3.5C x 240MM2 - 11KV - ARMOURED",
            "POWER CABLE 11KV XLPE INSULATED 3.5Cx240SQMM WITH ARMOUR",
        ],
    },
    {
        "cluster_id": "CLUSTER_010",
        "unified_code": "NAT-ELB-90-001",
        "std_desc": "Elbow 90°, Butt Weld, CS (A234 WPB), 6 Inch, Sch 40, LR",
        "uom": "NOS",
        "variants": [
            "ELBOW 90DEG BW CS A234WPB 6IN SCH40 LR",
            "90° Elbow BW 6\" CS A234 WPB Sch 40 Long Radius",
            "6 INCH 90 DEG LR ELBOW CS A234-WPB SCH40",
            "CS BUTT WELD ELBOW 90DEG LR 6\" SCH40",
            "ELBOW 90 BW LR - A234 WPB - 6IN - SCH-40",
        ],
    },
    {
        "cluster_id": "CLUSTER_011",
        "unified_code": "NAT-VLV-CHK-001",
        "std_desc": "Check Valve, Swing Type, CS (A216 WCB), 3 Inch, Class 150",
        "uom": "NOS",
        "variants": [
            "CHK VLV SWING CS WCB 3IN 150# FLG",
            "Swing Check Valve 3\" CS A216 WCB 150LB Flanged",
            "3 INCH SWING CHECK VALVE CARBON STEEL CL150",
            "CS CHECK VALVE - SWING TYPE - 3IN - 150LB - WCB",
            "Check Valve Swing Type WCB 3 inch Class 150 Flanged",
        ],
    },
    {
        "cluster_id": "CLUSTER_012",
        "unified_code": "NAT-REDUCER-001",
        "std_desc": "Reducer, Concentric, BW, CS (A234 WPB), 6x4 Inch, Sch 40",
        "uom": "NOS",
        "variants": [
            "REDUCER CON BW CS A234WPB 6x4IN SCH40",
            "Concentric Reducer BW 6\"x4\" CS A234 WPB Sch 40",
            "6\"x4\" CONC REDUCER CS BUTT WELD SCH40",
            "CS CONCENTRIC REDUCER 6IN x 4IN SCH40 A234-WPB",
        ],
    },
    {
        "cluster_id": "CLUSTER_013",
        "unified_code": "NAT-TEE-EQ-001",
        "std_desc": "Tee, Equal, BW, CS (A234 WPB), 4 Inch, Sch 40",
        "uom": "NOS",
        "variants": [
            "TEE EQUAL BW CS A234WPB 4IN SCH40",
            "Equal Tee Butt Weld 4\" CS A234 WPB Sch 40",
            "4 INCH EQUAL TEE CS BW SCH40",
            "CS EQUAL TEE - 4IN - SCH40 - A234 WPB BW",
        ],
    },
    {
        "cluster_id": "CLUSTER_014",
        "unified_code": "NAT-INST-PTX-001",
        "std_desc": "Pressure Transmitter, Smart, 0-100 bar, 4-20mA, HART",
        "uom": "NOS",
        "variants": [
            "PRESS TRANSMITTER SMART 0-100BAR 4-20MA HART",
            "Smart Pressure Transmitter 0 to 100 bar 4-20mA HART",
            "SMART PT 0-100 BAR, OUTPUT 4-20MA, HART PROTOCOL",
            "Pressure Transmitter - Smart - Range 0~100bar - 4-20mA HART",
            "SMART PRESSURE TRANSMITTER 0-100BAR 4/20MA HART",
        ],
    },
    {
        "cluster_id": "CLUSTER_015",
        "unified_code": "NAT-PAINT-EP-001",
        "std_desc": "Paint, Epoxy, Two Component, Grey, RAL 7035",
        "uom": "LTR",
        "variants": [
            "PAINT EPOXY 2-COMP GREY RAL7035",
            "Epoxy Paint Two Component Grey RAL 7035",
            "2-PACK EPOXY PAINT - GREY - RAL 7035",
            "TWO COMPONENT EPOXY PAINT GREY RAL-7035",
        ],
    },
    {
        "cluster_id": "CLUSTER_016",
        "unified_code": "NAT-MOTOR-IND-001",
        "std_desc": "Induction Motor, 3-Phase, 15 kW, 1500 RPM, TEFC, IE3",
        "uom": "NOS",
        "variants": [
            "MOTOR INDUCTION 3PH 15KW 1500RPM TEFC IE3",
            "3 Phase Induction Motor 15kW 1500 RPM TEFC IE3",
            "INDUCTION MOTOR - 3PH - 15 KW - 1500RPM - TEFC - IE3",
            "15KW 3PH SQUIRREL CAGE MOTOR 1500RPM TEFC IE3",
            "AC INDUCTION MOTOR 15KW/1500RPM/TEFC/IE3/3PHASE",
        ],
    },
    {
        "cluster_id": "CLUSTER_017",
        "unified_code": "NAT-PIPE-SS-001",
        "std_desc": "Seamless Pipe, SS316L, 2 Inch, Sch 10S, ASTM A312",
        "uom": "MTR",
        "variants": [
            "PIPE SMLS SS316L 2IN SCH10S A312",
            "Seamless SS 316L Pipe 2\" Sch 10S ASTM A312",
            "SS316L SEAMLESS PIPE 2 INCH SCH-10S A312",
            "A312 SS316L SMLS PIPE - 2IN - SCH 10S",
        ],
    },
    {
        "cluster_id": "CLUSTER_018",
        "unified_code": "NAT-VLV-GLOBE-001",
        "std_desc": "Globe Valve, CS (A216 WCB), 2 Inch, Class 150, Flanged",
        "uom": "NOS",
        "variants": [
            "GLOBE VLV CS WCB 2IN 150# FLG",
            "Globe Valve 2\" Carbon Steel WCB Class 150 Flanged",
            "2 INCH GLOBE VALVE CS A216-WCB CL150 FLANGED",
            "CS GLOBE VALVE 2IN 150LB FLANGED WCB",
            "Globe Valve - CS WCB - 2 inch - 150LB - Flanged End",
        ],
    },
    {
        "cluster_id": "CLUSTER_019",
        "unified_code": "NAT-GSKT-PTFE-001",
        "std_desc": "Gasket, PTFE Envelope, 3 Inch, Class 150, RF",
        "uom": "NOS",
        "variants": [
            "GSKT PTFE ENVELOPE 3IN 150# RF",
            "PTFE Envelope Gasket 3\" Class 150 Raised Face",
            "3 INCH PTFE ENVELOPE GASKET CL150 RF",
            "PTFE GASKET ENVELOPE TYPE - 3IN - 150LB - RF",
        ],
    },
    {
        "cluster_id": "CLUSTER_020",
        "unified_code": "NAT-CABLE-CTRL-001",
        "std_desc": "Control Cable, PVC, 12C x 2.5 sq.mm, 1.1kV, Armoured",
        "uom": "MTR",
        "variants": [
            "CABLE CTRL PVC 12Cx2.5SQMM 1.1KV ARM",
            "Control Cable 12 Core 2.5 Sq mm PVC 1.1kV Armoured",
            "1.1KV PVC CONTROL CABLE 12Cx2.5 SQMM ARMOURED",
            "PVC CONTROL CABLE - 12C x 2.5MM2 - 1.1KV - ARMOURED",
        ],
    },
    {
        "cluster_id": "CLUSTER_021",
        "unified_code": "NAT-INST-TW-001",
        "std_desc": "Thermowell, SS316, 200mm Insertion, 1/2\" NPT, Stepped",
        "uom": "NOS",
        "variants": [
            "THERMOWELL SS316 200MM 1/2NPT STEPPED",
            "SS316 Thermowell 200mm Insertion Length 1/2\" NPT Stepped",
            "THERMOWELL - SS316 - 200MM IL - 1/2\"NPT - STEPPED TYPE",
            "Stepped Thermowell SS316 200mm 1/2 inch NPT",
        ],
    },
]


def generate_legacy_code(cpse: str) -> str:
    """Generate a realistic-looking legacy item code for a given CPSE."""
    code_num = random.randint(100000, 999999)
    return f"{cpse}-M-{code_num}"


def build_dataset() -> pd.DataFrame:
    """Build the full dataset from cluster definitions."""
    rows = []
    for cluster in CLUSTERS:
        cid = cluster["cluster_id"]
        n_variants = len(cluster["variants"])
        # Pick random CPSEs for each variant (no repeat within cluster ideally)
        cpse_list = random.sample(CPSES * 3, n_variants)  # allow repeats across clusters

        for i, desc in enumerate(cluster["variants"]):
            cpse = cpse_list[i]
            rows.append(
                {
                    "CPSE_Source": cpse,
                    "Legacy_Item_Code": generate_legacy_code(cpse),
                    "Raw_Description": desc,
                    "UOM": cluster["uom"],
                    "Ground_Truth_Cluster_ID": cid,
                    "Is_Duplicate_Cluster": True if n_variants > 1 else False,
                    "Unified_National_Code": cluster["unified_code"],
                    "Standardized_Description": cluster["std_desc"],
                }
            )

    df = pd.DataFrame(rows)
    # Shuffle the rows so clusters are not contiguous (simulates real messy data)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    return df


if __name__ == "__main__":
    df = build_dataset()
    output_path = "sample_data.xlsx"
    df.to_excel(output_path, index=False, engine="openpyxl")
    print(f"SUCCESS: Dataset generated: {output_path}")
    print(f"    Total rows : {len(df)}")
    print(f"    Clusters   : {df['Ground_Truth_Cluster_ID'].nunique()}")
    print(f"    CPSEs      : {df['CPSE_Source'].nunique()}")
