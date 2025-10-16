# app.py — Desk & Seat Mapper (with preloaded office layout)
# Draw long bars (desks) and circles (chairs). Save/Load JSON. Export PNG.
# Now auto-loads your office layout and adds a "Reset to office layout" button.

import io
import json
import numpy as np
from PIL import Image, ImageDraw
import streamlit as st

# --- dependency check ---
try:
    from streamlit_drawable_canvas import st_canvas
except ModuleNotFoundError:
    st.error("Missing 'streamlit-drawable-canvas'. Add it to requirements.txt and restart.")
    raise

# ---------- Canvas / grid ----------
W, H = 1300, 740
BG = "#f7f9fc"

def grid_image(w=W, h=H, step=20, major=100) -> Image.Image:
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    # minor grid
    for x in range(0, w, step):
        d.line([(x,0), (x,h)], fill="#e9edf3")
    for y in range(0, h, step):
        d.line([(0,y), (w,y)], fill="#e9edf3")
    # major grid
    for x in range(0, w, major):
        d.line([(x,0), (x,h)], fill="#d6dde8", width=2)
    for y in range(0, h, major):
        d.line([(0,y), (w,y)], fill="#d6dde8", width=2)
    return img

# ---------- Default office layout (bars + circles + labels) ----------
TABLE_FILL = "#bccdee"
SEAT_FILL  = "#cfead0"
OUTLINE    = "#556"
TEXT_CLR   = "#1f2937"

def default_office_fabric() -> dict:
    """Return a Fabric.js JSON with your office map."""
    objects = []

    # LEFT SIDE: 5 vertical desks (bars)
    left_start_x = 240
    cols = 5
    col_gap = 120
    top_y = 150
    rows = 6
    row_gap = 85
    table_w = 22
    table_h = rows * row_gap + 30

    for c in range(cols):
        tx = left_start_x + c * col_gap
        # Desk (rectangle)
        objects.append({
            "type":"rect","left":tx,"top":top_y,"width":table_w,"height":table_h,
            "fill":TABLE_FILL,"stroke":OUTLINE,"strokeWidth":2,"angle":0,"scaleX":1,"scaleY":1
        })
        # Seats: two columns of circles per row (left/right of bar)
        for r in range(rows):
            cy = top_y + 20 + r * row_gap
            # left side
            objects.append({
                "type":"circle","left":tx-40,"top":cy,"radius":14,
                "fill":SEAT_FILL,"stroke":OUTLINE,"strokeWidth":2,"scaleX":1,"scaleY":1
            })
            # right side
            objects.append({
                "type":"circle","left":tx+table_w+40,"top":cy,"radius":14,
                "fill":SEAT_FILL,"stroke":OUTLINE,"strokeWidth":2,"scaleX":1,"scaleY":1
            })

    # RIGHT SIDE: 8 horizontal desks, 4 seats each
    right_start_x = 820
    right_table_w = 420
    right_table_h = 22
    right_rows = 8
    row_gap2 = 70
    right_top_y = 80
    seats_per = 4
    seat_gap = 100

    # Bottom three rows labeled 49–74
    label_base = 49
    label_rows_start = right_rows - 3  # 6,7,8th bars

    for r in range(right_rows):
        ty = right_top_y + r * row_gap2
        # Desk (rectangle)
        objects.append({
            "type":"rect","left":right_start_x,"top":ty,"width":right_table_w,"height":right_table_h,
            "fill":TABLE_FILL,"stroke":OUTLINE,"strokeWidth":2,"angle":0,"scaleX":1,"scaleY":1
        })
        # Seats on the bar
        for i in range(seats_per):
            sx = right_start_x + 80 + i * seat_gap
            sy = ty + right_table_h // 2
            objects.append({
                "type":"circle","left":sx,"top":sy,"radius":16,
                "fill":SEAT_FILL,"stroke":OUTLINE,"strokeWidth":2,"scaleX":1,"scaleY":1
            })
            if r >= label_rows_start:
                label = str(label_base + (r - label_rows_start) * seats_per + i)
                # Small label near the seat
                objects.append({
                    "type":"textbox","left":sx-10,"top":sy-30,"width":40,"height":18,
                    "text":label,"fontSize":14,"fill":TEXT_CLR
                })

    return {"version":"5.2.4","objects":objects}

# ---------- State ----------
if "fabric" not in st.session_state:
    st.session_state.fabric = default_office_fabric()

st.set_page_config(page_title="Desk & Seat Mapper", layout="wide")
st.title("🗺️ Desk & Seat Mapper")

# ---------- Sidebar ----------
with st.sidebar:
    st.subheader("Tool")
    tool = st.radio("Choose tool", ["Select/Move", "Add Desk (Rectangle)", "Add Seat (Circle)"], index=0)
    drawing_mode = {"Add Desk (Rectangle)": "rect",
                    "Add Seat (Circle)": "circle",
                    "Select/Move": "transform"}[tool]

    st.subheader("Style")
    default_fill = TABLE_FILL if drawing_mode == "rect" else SEAT_FILL
    fill = st.color_picker("Fill color", default_fill, key="fill")
    stroke = st.color_picker("Outline color", OUTLINE, key="stroke")
    stroke_w = st.slider("Outline width", 1, 8, 2)
    seat_radius = st.slider("Seat radius (circle)", 10, 32, 16)

    st.caption("Tip: rectangles → long thin bars for desks. Circles → chairs.")

    st.subheader("Grid / Layout")
    show_grid = st.checkbox("Show grid", value=True)
    if st.button("🔁 Reset to office layout"):
        st.session_state.fabric = default_office_fabric()
        st.success("Layout reset.")

    if st.button("🗑️ Clear all"):
        st.session_state.fabric = {"version": "5.2.4", "objects": []}
    if st.button("↩️ Undo last"):
        objs = st.session_state.fabric.get("objects", [])
        if objs:
            st.session_state.fabric["objects"] = objs[:-1]

    st.subheader("Save/Load")
    st.download_button("⬇️ Download layout.json",
                       data=json.dumps(st.session_state.fabric, indent=2),
                       file_name="layout.json")
    uploaded = st.file_uploader("Upload layout.json", type=["json"])
    if uploaded:
        st.session_state.fabric = json.loads(uploaded.read().decode("utf-8"))
        st.success("Layout loaded.")

# ---------- Canvas ----------
bg_img = grid_image() if show_grid else Image.new("RGB", (W, H), BG)

st.caption("Use Select/Move to reposition. Add rectangles for desks, circles for chairs.")
canvas = st_canvas(
    background_image=bg_img,
    width=W,
    height=H,
    drawing_mode=drawing_mode,
    stroke_width=stroke_w,
    stroke_color=stroke,
    fill_color=fill,
    update_streamlit=True,
    initial_drawing=st.session_state.fabric,
    display_toolbar=True,
    key="map_canvas",
)

# Persist drawing back to session
if canvas and canvas.json_data:
    st.session_state.fabric = canvas.json_data

# ---------- Export PNG ----------
def render_png(fabric_json, include_grid=True) -> Image.Image:
    base = grid_image() if include_grid else Image.new("RGB", (W, H), BG)
    out = base.copy()
    d = ImageDraw.Draw(out)
    for obj in fabric_json.get("objects", []):
        otype = obj.get("type")
        left = int(obj.get("left", 0))
        top  = int(obj.get("top", 0))
        scx  = float(obj.get("scaleX", 1))
        scy  = float(obj.get("scaleY", 1))
        stroke_c = obj.get("stroke", OUTLINE)
        stroke_w = int(obj.get("strokeWidth", 2))
        fill_c   = obj.get("fill", TABLE_FILL if otype=="rect" else SEAT_FILL)

        if otype == "rect":
            w = int(obj.get("width", 60) * scx)
            h = int(obj.get("height", 20) * scy)
            d.rectangle([left, top, left + w, top + h], fill=fill_c, outline=stroke_c, width=stroke_w)

        elif otype == "circle":
            r = int(obj.get("radius", 14) * scx)  # circle uses scaleX for radius
            d.ellipse([left - r, top - r, left + r, top + r], fill=fill_c, outline=stroke_c, width=stroke_w)

        elif otype in ("textbox","i-text","text"):
            text = obj.get("text","")
            d.text((left, top), text, fill=obj.get("fill", TEXT_CLR))

    return out

def png_bytes(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()

png_img = render_png(st.session_state.fabric, include_grid=show_grid)
st.markdown("### Preview / Export")
st.image(np.array(png_img), use_container_width=True)
st.download_button("⬇️ Export PNG", data=png_bytes(png_img), file_name="desk_seat_map.png", mime="image/png")
