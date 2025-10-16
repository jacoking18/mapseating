# app.py — Minimal Desk & Seat Mapper (fixed)
# Draw long bars (rectangles) and seats (circles). Save/Load JSON. Export PNG.

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

# ---------- State ----------
if "fabric" not in st.session_state:
    st.session_state.fabric = {"version": "5.2.4", "objects": []}  # fabric.js JSON

st.set_page_config(page_title="Desk & Seat Mapper", layout="wide")
st.title("🗺️ Desk & Seat Mapper")

# ---------- Sidebar ----------
with st.sidebar:
    st.subheader("Tool")
    tool = st.radio("Choose tool", ["Add Desk (Rectangle)", "Add Seat (Circle)", "Select/Move"])
    drawing_mode = {"Add Desk (Rectangle)": "rect",
                    "Add Seat (Circle)": "circle",
                    "Select/Move": "transform"}[tool]

    st.subheader("Style")
    default_fill = "#bccdee" if drawing_mode == "rect" else "#cfead0"
    fill = st.color_picker("Fill color", default_fill, key="fill")
    stroke = st.color_picker("Outline color", "#556", key="stroke")
    stroke_w = st.slider("Outline width", 1, 8, 2)
    seat_radius = st.slider("Seat radius (circle)", 8, 40, 14)

    st.caption("Tip: rectangles → long thin bars for desks. Circles → chairs.")

    st.subheader("Grid / Layout")
    show_grid = st.checkbox("Show grid", value=True)
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

st.caption("Draw: Rectangle = desk, Circle = seat. Use Select/Move to reposition/resize.")
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
        stroke_c = obj.get("stroke", "#556")
        stroke_w = int(obj.get("strokeWidth", 2))
        fill_c   = obj.get("fill", default_fill)

        if otype == "rect":
            w = int(obj.get("width", 60) * scx)
            h = int(obj.get("height", 20) * scy)
            d.rectangle([left, top, left + w, top + h], fill=fill_c, outline=stroke_c, width=stroke_w)

        elif otype == "circle":
            r = int(obj.get("radius", 14) * scx)  # circle uses scaleX
            d.ellipse([left - r, top - r, left + r, top + r], fill=fill_c, outline=stroke_c, width=stroke_w)

        # You can add 'line' or 'textbox' support later if needed.

    return out

png_img = render_png(st.session_state.fabric, include_grid=show_grid)
st.markdown("### Preview / Export")
st.image(np.array(png_img), use_container_width=True)

# Compute bytes BEFORE the download button (avoids walrus operator issues)
def png_bytes(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()

png_data = png_bytes(png_img)
st.download_button("⬇️ Export PNG", data=png_data, file_name="desk_seat_map.png", mime="image/png")
