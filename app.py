# app.py — Office Seating (built-in floor map, click-to-assign)
import os, math
import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
from streamlit_drawable_canvas import st_canvas

# ---------- Persistence ----------
PEOPLE_CSV = "people.csv"
ASSIGN_CSV = "assignments.csv"

def ensure_files():
    if not os.path.exists(PEOPLE_CSV):
        pd.DataFrame(columns=["employee_name","team","active"]).to_csv(PEOPLE_CSV, index=False)
    if not os.path.exists(ASSIGN_CSV):
        pd.DataFrame(columns=["seat_id","employee_name"]).to_csv(ASSIGN_CSV, index=False)

def load_people(): return pd.read_csv(PEOPLE_CSV) if os.path.exists(PEOPLE_CSV) else pd.DataFrame(columns=["employee_name","team","active"])
def load_assign(): return pd.read_csv(ASSIGN_CSV) if os.path.exists(ASSIGN_CSV) else pd.DataFrame(columns=["seat_id","employee_name"])
def save_people(df): df.to_csv(PEOPLE_CSV, index=False)
def save_assign(df): df.to_csv(ASSIGN_CSV, index=False)

# ---------- Layout (EDIT HERE to tweak shape/counts/labels) ----------
CANVAS_W, CANVAS_H = 1350, 750
SEAT_R = 14                    # circle radius
OVAL_W, OVAL_H = 56, 28        # oval size

# Colors
COL_BG   = "#f7f9fc"
COL_WALL = "#d9dee7"
COL_TABLE= "#bccdee"
COL_TXT  = "#1f2937"
COL_ASSIGNED   = "#cfead0"     # green
COL_UNASSIGNED = "#ffe6a3"     # yellow
COL_UNUSED     = "#f6c7c7"     # red
COL_OUTLINE    = "#556"

# Legend & zones (E/R)
LEGEND = [("Unassigned", COL_UNASSIGNED), ("Assigned", COL_ASSIGNED), ("Not in Use", COL_UNUSED)]

# Seat types:
#  - shape: "circle" or "oval"
#  - x,y: anchor (center for circle; center for oval)
#  - status: Unassigned / Not in Use (Assigned is inferred if someone sits there)
#  - label: shown text on/near seat (optional)

def build_layout():
    seats, tables = [], []

    # Left block — 5 vertical tables with circular seats (grid)
    left_start_x = 240
    cols = 5
    rows = 6
    col_gap = 120
    row_gap = 85
    top_y = 160
    # Draw tables (vertical bars)
    table_w = 22
    table_h = rows*row_gap + 20
    for c in range(cols):
        tx = left_start_x + c*col_gap
        tables.append(("vbar", tx, top_y-10, table_w, table_h))
    # Seats around those tables: two per table per row (left/right of bar)
    seat_id = 1
    for r in range(rows):
        cy = top_y + r*row_gap
        for c in range(cols):
            tx = left_start_x + c*col_gap
            # left side
            seats.append(dict(seat_id=str(seat_id), shape="circle", x=tx-40, y=cy, status="Not in Use", label=""))
            seat_id += 1
            # right side
            seats.append(dict(seat_id=str(seat_id), shape="circle", x=tx+40+table_w, y=cy, status="Not in Use", label=""))
            seat_id += 1

    # Right block — 8 horizontal tables with oval seats (4 per table)
    right_start_x = 820
    right_table_w  = 420
    right_table_h  = 22
    right_rows = 8
    right_row_gap = 70
    right_top_y = 80
    seats_per_row = 4
    seat_gap = 100
    for r in range(right_rows):
        ty = right_top_y + r*right_row_gap
        tables.append(("hbar", right_start_x, ty, right_table_w, right_table_h))
        for i in range(seats_per_row):
            sx = right_start_x + 80 + i*seat_gap
            sy = ty + right_table_h//2
            label = ""
            # bottom two rows have explicit labels 49–74 to mimic your map
            if r >= right_rows-3:
                base = 49  # starting label roughly like image
                label = str(base + (r-(right_rows-3))*seats_per_row + i)
            seats.append(dict(seat_id=str(seat_id), shape="oval", x=sx, y=sy, status="Unassigned", label=label))
            seat_id += 1

    # Side labels (E/R zone plaque)
    side_labels = [("E", 96, 56), ("R", 96, CANVAS_H-120)]

    return seats, tables, side_labels

SEATS_TEMPLATE, TABLES, SIDE_LABELS = build_layout()

# map seat_id->status override (for "Not in Use")
STATUS_OVERRIDES = { s["seat_id"]: s["status"] for s in SEATS_TEMPLATE }

def seat_bbox(seat):
    if seat["shape"] == "circle":
        r = SEAT_R
        return (seat["x"]-r, seat["y"]-r, seat["x"]+r, seat["y"]+r)
    else:
        return (seat["x"]-OVAL_W//2, seat["y"]-OVAL_H//2, seat["x"]+OVAL_W//2, seat["y"]+OVAL_H//2)

def draw_map(assign_df):
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), COL_BG)
    d = ImageDraw.Draw(img)

    # perimeter walls (visual only)
    d.rectangle([24, 24, CANVAS_W-24, CANVAS_H-24], outline=COL_WALL, width=8)

    # tables
    for kind, x, y, w, h in TABLES:
        d.rectangle([x, y, x+w, y+h], fill=COL_TABLE, outline=COL_OUTLINE)

    # legend
    lx, ly = 360, 40
    d.rectangle([lx-20, ly-10, lx+260, ly+90], outline=COL_OUTLINE, width=1)
    d.text((lx-18, ly-26), "Legend", fill=COL_TXT)
    for i,(label,color) in enumerate(LEGEND):
        cy = ly + i*28
        d.ellipse([lx, cy, lx+18, cy+18], fill=color, outline=COL_OUTLINE)
        d.text((lx+26, cy-2), label, fill=COL_TXT)

    # side labels
    for text, sx, sy in SIDE_LABELS:
        d.rectangle([sx-30, sy-24, sx+30, sy+24], outline=COL_OUTLINE, width=2)
        d.text((sx-6, sy-10), text, fill=COL_TXT)

    # seats
    assigned_ids = set(assign_df["seat_id"].astype(str).tolist())
    for s in SEATS_TEMPLATE:
        sid = s["seat_id"]
        is_assigned = sid in assigned_ids
        status = "Assigned" if is_assigned else STATUS_OVERRIDES.get(sid, "Unassigned")
        fill = COL_ASSIGNED if is_assigned else (COL_UNUSED if status=="Not in Use" else COL_UNASSIGNED)
        if s["shape"] == "circle":
            d.ellipse(seat_bbox(s), fill=fill, outline=COL_OUTLINE, width=2)
        else:
            d.ellipse(seat_bbox(s), fill=fill, outline=COL_OUTLINE, width=2)
        label = s["label"] or sid
        # little text next to/inside
        bx0, by0, bx1, by1 = seat_bbox(s)
        d.text((bx0, by0-14), str(label), fill=COL_TXT)

    return img

def nearest_seat(x, y, tol=32):
    # pick nearest seat center within tol (px)
    best, bestd = None, 1e9
    for s in SEATS_TEMPLATE:
        dx, dy = s["x"]-x, s["y"]-y
        d = math.hypot(dx, dy)
        if d < bestd:
            best, bestd = s, d
    return best if bestd <= tol else None

def color_status(val):
    if val=="Assigned": return "background-color:#cfead0"
    if val=="Unassigned": return "background-color:#ffe6a3"
    if val=="Not in Use": return "background-color:#f6c7c7"
    return ""

# ---------- UI ----------
st.set_page_config(page_title="Office Seating Planner", layout="wide")
st.title("🏢 Office Seating Planner (Built-in Map)")

ensure_files()
people = load_people()
assigns = load_assign()

with st.sidebar:
    st.subheader("Quick actions")
    st.download_button("Export assignments.csv", assigns.to_csv(index=False), file_name="assignments.csv")
    st.caption("Edit the layout in code (top of file) to move/resize rows, counts, labels (49–74).")

tab_people, tab_assign, tab_status, tab_tables = st.tabs(["👤 Add Users", "📍 Assign / Clear / Toggle", "📋 Current Status", "🧱 Layout Preview"])

# ---- Add Users ----
with tab_people:
    st.subheader("Add a person")
    c1,c2,c3 = st.columns([1.6,1,1])
    with c1:
        name = st.text_input("Full name")
    with c2:
        team = st.text_input("Team (optional)")
    with c3:
        active = st.selectbox("Active", ["YES","NO"])
    if st.button("➕ Add person"):
        if name.strip():
            people = pd.concat([people, pd.DataFrame([{"employee_name":name.strip(), "team":team.strip(), "active":active}])], ignore_index=True)
            save_people(people)
            st.success(f"Added {name}")
        else:
            st.warning("Name is required.")
    st.divider()
    st.dataframe(people, use_container_width=True)

# ---- Assign / Clear ----
with tab_assign:
    st.subheader("Click a seat on the map (we’ll snap to the nearest one)")
    active_people = people[people["active"].astype(str).str.upper().isin(["YES","TRUE","1","YES"])].sort_values("employee_name")
    person = st.selectbox("Person", ["— Select —"] + active_people["employee_name"].tolist())
    mode = st.radio("Action", ["Assign / Move", "Clear Seat", "Toggle Not in Use"], horizontal=True)

    bg = draw_map(assigns)
    canvas = st_canvas(
        background_image=bg,
        width=CANVAS_W, height=CANVAS_H,
        drawing_mode="point",
        point_display_radius=2,
        key="assign_canvas",
    )

    clicked_xy = None
    if canvas and canvas.json_data and "objects" in canvas.json_data and len(canvas.json_data["objects"])>0:
        obj = canvas.json_data["objects"][-1]
        clicked_xy = (int(obj.get("left", CANVAS_W//2)), int(obj.get("top", CANVAS_H//2)))

    if clicked_xy:
        target = nearest_seat(*clicked_xy, tol=36)
        if target:
            st.info(f"Nearest seat: {target['seat_id']}  (label: {target['label'] or target['seat_id']})")
            if st.button("✅ Apply"):
                sid = str(target["seat_id"])
                if mode == "Assign / Move":
                    if person == "— Select —":
                        st.warning("Pick a person first.")
                    else:
                        # person unique: remove from other seat
                        assigns = assigns[assigns["employee_name"] != person]
                        # clear whoever is at this seat (move)
                        assigns = assigns[assigns["seat_id"].astype(str) != sid]
                        assigns = pd.concat([assigns, pd.DataFrame([{"seat_id": sid, "employee_name": person}])], ignore_index=True)
                        save_assign(assigns)
                        st.success(f"Assigned **{person}** to seat **{sid}**")
                elif mode == "Clear Seat":
                    assigns = assigns[assigns["seat_id"].astype(str) != sid]
                    save_assign(assigns)
                    st.success(f"Cleared seat **{sid}**")
                elif mode == "Toggle Not in Use":
                    # flip override
                    cur = STATUS_OVERRIDES.get(sid, "Unassigned")
                    new = "Not in Use" if cur != "Not in Use" else "Unassigned"
                    STATUS_OVERRIDES[sid] = new
                    # if turning Not in Use, boot anyone sitting
                    if new == "Not in Use":
                        assigns = assigns[assigns["seat_id"].astype(str) != sid]
                        save_assign(assigns)
                    st.success(f"Seat **{sid}** → {new}")
        else:
            st.warning("No seat near that click (try closer to a colored seat).")

# ---- Current Status ----
with tab_status:
    # Build status table
    rows = []
    assigned_map = {str(r.seat_id): r.employee_name for r in assigns.itertuples(index=False)}
    for s in SEATS_TEMPLATE:
        sid = s["seat_id"]
        assigned = assigned_map.get(sid, "")
        status = "Assigned" if assigned else STATUS_OVERRIDES.get(sid, "Unassigned")
        rows.append({
            "seat_id": sid,
            "label": s["label"] or sid,
            "shape": s["shape"],
            "status": status,
            "employee_name": assigned
        })
    view = pd.DataFrame(rows).sort_values(["status","seat_id"])
    st.dataframe(view, use_container_width=True)

# ---- Layout Preview ----
with tab_tables:
    st.image(draw_map(assigns), use_container_width=True)
    st.caption("Preview. Edit the layout constants at the top of this file to change row/column counts and labels (e.g., 49–74).")
