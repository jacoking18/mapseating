# app.py — Dynamic Office Map Simulation (Streamlit)
# - Built-in floor map (no images)
# - Add people (team, optional "near" preference)
# - Click to assign seats on the map
# - Layout scoring (team adjacency + preference distance)
# - Heuristic simulator to suggest swaps that increase score
# - Lock seats (pinned), Save/Load JSON snapshots

import os, math, json, random, io
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw
try:
    from streamlit_drawable_canvas import st_canvas
except ModuleNotFoundError:
    st.error(
        "❌ Missing dependency 'streamlit-drawable-canvas'.\n"
        "Add `streamlit-drawable-canvas` to requirements.txt and restart."
    )
    raise

# ---------------- Layout (edit to tweak geometry) ----------------
CANVAS_W, CANVAS_H = 1350, 750
SEAT_R = 14                  # circle radius
OVAL_W, OVAL_H = 56, 28      # oval size

COL_BG        = "#f7f9fc"
COL_TABLE     = "#bccdee"
COL_TXT       = "#1f2937"
COL_OUTLINE   = "#556"
COL_ASSIGNED  = "#cfead0"
COL_FREE      = "#ffe6a3"
COL_UNUSED    = "#f6c7c7"
COL_LOCKED    = "#c9d4ff"

Legend = [("Unassigned", COL_FREE), ("Assigned", COL_ASSIGNED), ("Not in Use", COL_UNUSED), ("Locked", COL_LOCKED)]

def build_layout():
    """Return (seats:list, tables:list). Seats include id, x, y, shape, zone, status, label, locked."""
    seats, tables = [], []
    # LEFT: 5 vertical bars, 6 rows, circles both sides of bar
    left_start_x = 240; cols = 5; rows = 6; col_gap = 120; row_gap = 85; top_y = 160; table_w = 22
    table_h = rows*row_gap + 20
    for c in range(cols):
        tx = left_start_x + c*col_gap
        tables.append(("vbar", tx, top_y-10, table_w, table_h))
    seat_id = 1
    for r in range(rows):
        cy = top_y + r*row_gap
        for c in range(cols):
            tx = left_start_x + c*col_gap
            seats.append(dict(id=str(seat_id), shape="circle", x=tx-40,        y=cy, zone="E", status="Unassigned", label="", locked=False)); seat_id += 1
            seats.append(dict(id=str(seat_id), shape="circle", x=tx+40+table_w, y=cy, zone="E", status="Unassigned", label="", locked=False)); seat_id += 1

    # RIGHT: 8 horizontal bars, 4 ovals each
    right_start_x = 820; right_table_w = 420; right_table_h = 22; right_rows = 8; row_gap2 = 70
    right_top_y = 80; seats_per = 4; seat_gap = 100
    base_label = 49  # labeling bottom 3 rows to mimic your image
    for r in range(right_rows):
        ty = right_top_y + r*row_gap2
        tables.append(("hbar", right_start_x, ty, right_table_w, right_table_h))
        for i in range(seats_per):
            sx = right_start_x + 80 + i*seat_gap
            sy = ty + right_table_h//2
            lbl = ""
            if r >= right_rows-3:
                lbl = str(base_label + (r-(right_rows-3))*seats_per + i)
            seats.append(dict(id=str(seat_id), shape="oval", x=sx, y=sy, zone="R", status="Unassigned", label=lbl, locked=False)); seat_id += 1
    return seats, tables

SEATS_TEMPLATE, TABLES = build_layout()

# ---------------- Data state ----------------
def init_state():
    if "people" not in st.session_state:
        st.session_state.people = []  # list of dict {name, team, near}
    if "assign" not in st.session_state:
        st.session_state.assign = {}  # seat_id -> name
    if "overrides" not in st.session_state:
        st.session_state.overrides = {s["id"]: s["status"] for s in SEATS_TEMPLATE}  # Unassigned/Not in Use
    if "locks" not in st.session_state:
        st.session_state.locks = {s["id"]: bool(s.get("locked", False)) for s in SEATS_TEMPLATE}

init_state()

# ---------------- Geometry helpers ----------------
def seat_bbox(s):
    if s["shape"] == "circle":
        r = SEAT_R
        return (s["x"]-r, s["y"]-r, s["x"]+r, s["y"]+r)
    else:
        return (s["x"]-OVAL_W//2, s["y"]-OVAL_H//2, s["x"]+OVAL_W//2, s["y"]+OVAL_H//2)

def dist(a, b): return math.hypot(a[0]-b[0], a[1]-b[1])

def nearest_seat(x, y, tol=36):
    best, bestd = None, 1e9
    for s in SEATS_TEMPLATE:
        d = dist((x,y), (s["x"], s["y"]))
        if d < bestd:
            best, bestd = s, d
    return best if bestd <= tol else None

def neighbors(seat_id, radius_px=120):
    s = next((t for t in SEATS_TEMPLATE if t["id"]==seat_id), None)
    if not s: return []
    out = []
    for t in SEATS_TEMPLATE:
        if t["id"] == seat_id: continue
        if dist((s["x"], s["y"]), (t["x"], t["y"])) <= radius_px:
            out.append(t["id"])
    return out

NEIGH_CACHE = {s["id"]: neighbors(s["id"]) for s in SEATS_TEMPLATE}

# ---------------- Rendering ----------------
def color_for(seat_id, assigned):
    if st.session_state.locks.get(seat_id, False):
        return COL_LOCKED
    if seat_id in assigned:
        return COL_ASSIGNED
    status = st.session_state.overrides.get(seat_id, "Unassigned")
    return COL_UNUSED if status == "Not in Use" else COL_FREE

def draw_map(assigned: Dict[str,str]):
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), COL_BG)
    d = ImageDraw.Draw(img)
    # tables
    for kind, x, y, w, h in TABLES:
        d.rectangle([x, y, x+w, y+h], fill=COL_TABLE, outline=COL_OUTLINE)
    # legend
    lx, ly = 360, 36
    d.rectangle([lx-22, ly-16, lx+300, ly+100], outline=COL_OUTLINE, width=1)
    d.text((lx-18, ly-28), "Legend", fill=COL_TXT)
    for i,(label,color) in enumerate([("Unassigned",COL_FREE),("Assigned",COL_ASSIGNED),("Not in Use",COL_UNUSED),("Locked",COL_LOCKED)]):
        cy = ly + i*26
        d.ellipse([lx, cy, lx+18, cy+18], fill=color, outline=COL_OUTLINE)
        d.text((lx+26, cy-2), label, fill=COL_TXT)
    # seats
    for s in SEATS_TEMPLATE:
        sid = s["id"]; fill = color_for(sid, assigned)
        d.ellipse(seat_bbox(s), fill=fill, outline=COL_OUTLINE, width=2)
        label = s["label"] or sid
        bx0, by0, _, _ = seat_bbox(s)
        d.text((bx0, by0-14), str(label), fill=COL_TXT)
        # if assigned, show initials
        if sid in assigned:
            name = assigned[sid]
            initials = "".join([p[0] for p in name.split() if p])[:2].upper()
            cx, cy = s["x"], s["y"]
            d.text((cx-5, cy-6), initials, fill="#1a1a1a")
    return img

# ---------------- People helpers ----------------
def person_by_name(name): 
    for p in st.session_state.people:
        if p["name"] == name: return p
    return None

def seat_of_person(name, assigned):
    for sid, n in assigned.items():
        if n == name: return sid
    return None

# ---------------- Scoring ----------------
def layout_score(assigned: Dict[str,str], neighbor_weight=1.0, near_weight=0.3):
    """Score = team adjacency + negative distance to preferred person."""
    # Build reverse: name -> seat id
    reverse = {n: sid for sid, n in assigned.items()}
    team_score = 0.0
    pref_score = 0.0
    # adjacency: for each seated person, +1 per neighbor who shares team
    for sid, name in assigned.items():
        p = person_by_name(name)
        if not p: continue
        team = p.get("team") or ""
        for nid in NEIGH_CACHE[sid]:
            other = assigned.get(nid)
            if other and other != name:
                po = person_by_name(other)
                if po and (po.get("team") or "") == team and team:
                    team_score += 1
    team_score = team_score / 2.0  # each pair counted twice
    # preference distance: smaller is better
    for sid, name in assigned.items():
        p = person_by_name(name)
        if not p: continue
        near = (p.get("near") or "").strip()
        if near:
            s1 = sid
            s2 = reverse.get(near)
            if s2:
                a = next(t for t in SEATS_TEMPLATE if t["id"]==s1)
                b = next(t for t in SEATS_TEMPLATE if t["id"]==s2)
                dpx = dist((a["x"],a["y"]), (b["x"],b["y"]))
                pref_score += max(0, 200 - dpx) / 200.0  # 0..1
    return neighbor_weight*team_score + near_weight*pref_score

def propose_swaps(assigned: Dict[str,str], iterations=300):
    """Heuristic hill-climb: try random valid swaps; keep best improvements; return list of (sidA, sidB, delta)."""
    assigned = dict(assigned)  # copy
    best_moves = []
    base = layout_score(assigned)
    seat_ids = [s["id"] for s in SEATS_TEMPLATE if st.session_state.overrides.get(s["id"], "Unassigned") != "Not in Use"]
    movable = [sid for sid in seat_ids if not st.session_state.locks.get(sid, False)]
    if len(movable) < 2: return [], base
    for _ in range(iterations):
        a, b = random.sample(movable, 2)
        assigned[a], assigned[b] = assigned.get(b), assigned.get(a)
        sc = layout_score(assigned)
        delta = sc - base
        if delta > 0.01:
            best_moves.append((a, b, round(delta, 3)))
            base = sc
        else:
            # revert
            assigned[a], assigned[b] = assigned.get(b), assigned.get(a)
    # dedup by pair (orderless) and keep top few
    seen = set(); uniq = []
    for a,b,delta in sorted(best_moves, key=lambda x: -x[2]):
        key = tuple(sorted([a,b]))
        if key in seen: continue
        seen.add(key); uniq.append((a,b,delta))
        if len(uniq) >= 5: break
    return uniq, layout_score({**assigned}),  # second value is after our accepted steps

# ---------------- Persistence ----------------
def export_json():
    data = {
        "people": st.session_state.people,
        "assign": st.session_state.assign,
        "overrides": st.session_state.overrides,
        "locks": st.session_state.locks,
    }
    return json.dumps(data, indent=2)

def import_json(text:str):
    data = json.loads(text)
    st.session_state.people = data.get("people", [])
    st.session_state.assign = data.get("assign", {})
    st.session_state.overrides = data.get("overrides", st.session_state.overrides)
    st.session_state.locks = data.get("locks", st.session_state.locks)

# ---------------- UI ----------------
st.set_page_config(page_title="Dynamic Office Map Simulation", layout="wide")
st.title("🗺️ Dynamic Office Map — Seating Simulator")

# Sidebar: data ops
with st.sidebar:
    st.subheader("Data")
    st.download_button("⬇️ Download snapshot.json", data=export_json(), file_name="seating_snapshot.json")
    uploaded = st.file_uploader("Upload snapshot.json", type=["json"])
    if uploaded:
        import_json(uploaded.read().decode("utf-8"))
        st.success("Snapshot loaded.")

# Tabs
tab_people, tab_assign, tab_sim, tab_view = st.tabs(["👤 People", "📍 Assign / Toggle / Lock", "🧠 Simulate", "📊 Status"])

# --- People ---
with tab_people:
    st.subheader("Add / Manage People")
    c1,c2,c3 = st.columns([1.6,1.1,1.3])
    with c1: name = st.text_input("Full name")
    with c2: team = st.text_input("Team (e.g., Sales, Ops)")
    with c3: near = st.text_input("Prefer near (manager name, optional)")
    if st.button("➕ Add person"):
        if name.strip():
            st.session_state.people.append({"name": name.strip(), "team": team.strip(), "near": near.strip()})
            st.success(f"Added {name}")
        else:
            st.warning("Name is required.")
    if st.session_state.people:
        st.dataframe(pd.DataFrame(st.session_state.people), use_container_width=True)

# --- Assign / Toggle / Lock ---
with tab_assign:
    st.subheader("Click a seat on the map (snap to nearest)")
    # pick person for assign
    names = ["— Select —"] + [p["name"] for p in st.session_state.people]
    person = st.selectbox("Person", names)
    action = st.radio("Action", ["Assign / Move", "Clear Seat", "Toggle Not in Use", "Toggle Lock"], horizontal=True)

    bg = draw_map(st.session_state.assign)
    canvas = st_canvas(background_image=bg, width=CANVAS_W, height=CANVAS_H,
                       drawing_mode="point", point_display_radius=2, key="assign_canvas")
    clicked_xy = None
    if canvas and canvas.json_data and "objects" in canvas.json_data and len(canvas.json_data["objects"])>0:
        obj = canvas.json_data["objects"][-1]
        clicked_xy = (int(obj.get("left", CANVAS_W//2)), int(obj.get("top", CANVAS_H//2)))

    if clicked_xy:
        target = nearest_seat(*clicked_xy, tol=40)
        if target:
            sid = target["id"]
            st.info(f"Seat selected: {sid}  (label: {target['label'] or sid})")
            if st.button("✅ Apply"):
                if action == "Assign / Move":
                    if person == "— Select —":
                        st.warning("Pick a person first.")
                    else:
                        # enforce Not in Use & lock rules
                        if st.session_state.overrides.get(sid, "Unassigned") == "Not in Use":
                            st.warning("That seat is Not in Use. Toggle it first.")
                        elif st.session_state.locks.get(sid, False):
                            st.warning("That seat is locked. Unlock it first.")
                        else:
                            # remove person elsewhere
                            for k,v in list(st.session_state.assign.items()):
                                if v == person: st.session_state.assign.pop(k)
                            # replace whoever is there
                            st.session_state.assign[sid] = person
                            st.success(f"Assigned {person} → seat {sid}")
                elif action == "Clear Seat":
                    if sid in st.session_state.assign:
                        st.session_state.assign.pop(sid)
                        st.success(f"Cleared seat {sid}")
                elif action == "Toggle Not in Use":
                    cur = st.session_state.overrides.get(sid, "Unassigned")
                    new = "Not in Use" if cur != "Not in Use" else "Unassigned"
                    # kick out if setting Not in Use
                    if new == "Not in Use" and sid in st.session_state.assign:
                        st.session_state.assign.pop(sid)
                    st.session_state.overrides[sid] = new
                    st.success(f"Seat {sid}: {new}")
                elif action == "Toggle Lock":
                    st.session_state.locks[sid] = not st.session_state.locks.get(sid, False)
                    st.success(f"Seat {sid}: {'Locked' if st.session_state.locks[sid] else 'Unlocked'}")
        else:
            st.warning("No seat near that click.")

# --- Simulate ---
with tab_sim:
    st.subheader("Heuristic Simulation (suggest better swaps)")
    current = layout_score(st.session_state.assign)
    st.metric("Current score", f"{current:.2f}")
    iters = st.slider("Iterations", 100, 1000, 400, step=100)
    if st.button("🔍 Propose swaps"):
        suggestions, _after, = propose_swaps(st.session_state.assign, iterations=iters)
        if not suggestions:
            st.info("No beneficial swaps found (or not enough movable seats).")
        else:
            for i,(a,b,delta) in enumerate(suggestions, start=1):
                c1,c2,c3,c4 = st.columns([1,1,1,1.6])
                with c1: st.write(f"#{i}")
                with c2: st.write(f"Swap **{a}**")
                with c3: st.write(f"↔ **{b}**")
                with c4:
                    if st.button(f"Apply (+{delta})", key=f"apply_{i}"):
                        # perform swap if both seats are not locked or Not in Use
                        if st.session_state.locks.get(a, False) or st.session_state.locks.get(b, False):
                            st.warning("One of these seats is locked.")
                        elif st.session_state.overrides.get(a,"Unassigned")=="Not in Use" or st.session_state.overrides.get(b,"Unassigned")=="Not in Use":
                            st.warning("One of these seats is Not in Use.")
                        else:
                            st.session_state.assign[a], st.session_state.assign[b] = st.session_state.assign.get(b), st.session_state.assign.get(a)
                            st.success(f"Swapped {a} ↔ {b}")

    st.caption("Score = team adjacency (neighbors with same team) + proximity to preferred person (if set).")

# --- Status view ---
with tab_view:
    st.subheader("Current Seating Table")
    rows = []
    for s in SEATS_TEMPLATE:
        sid = s["id"]
        rows.append({
            "seat_id": sid,
            "label": s["label"] or sid,
            "zone": s["zone"],
            "status": ("Assigned" if sid in st.session_state.assign
                       else st.session_state.overrides.get(sid,"Unassigned")),
            "locked": st.session_state.locks.get(sid, False),
            "employee": st.session_state.assign.get(sid,"")
        })
    df = pd.DataFrame(rows).sort_values(["zone","seat_id"])
    st.dataframe(df, use_container_width=True)

    st.subheader("Map Preview")
    st.image(draw_map(st.session_state.assign), use_container_width=True)
