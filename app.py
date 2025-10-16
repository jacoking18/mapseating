# app.py — Minimal Desk & Seat Mapper
# Draw long bars (desks) and circles (chairs). Save/Load JSON. Export PNG.

import json
import numpy as np
from PIL import Image, ImageDraw
import streamlit as st

try:
    from streamlit_drawable_canvas import st_canvas
except ModuleNotFoundError:
    st.error("Missing 'streamlit-drawable-canvas'. Add it to requirements.txt.")
    raise

# ---------- Canvas settings ----------
W, H = 1300, 740
BG = "#f7f9fc"

def grid_image(w=W, h=H, step=20, major=100) -> Image.Image:
    """Create a faint grid background to help align bars/chairs."""
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

# ---------- Session state ----------
if "fabric" not in st.session_state:
    st.session_state.fabric = {"version":"5.2.4","objects":[]}  # fabric.js JSON

def set_tool(t: str):
    st.session_state.tool = t

st.set_page_config(page_title="Desk & Seat Mapper", layout="wide")
st.title("🗺️ Desk & Seat Mapper")

with st.sidebar:
    st.subheader("Tool")
    tool = st.radio(
        "Choose tool",
        ["Add Desk (Rectangle)", "Add Seat (Circle)", "Select/Move"],
        on_change=lambda: None,
    )
    if tool == "Add Desk (Rectangle)":
        drawing_mode = "rect"
    elif tool == "Add Seat (Circle)":
        drawing_mode = "circle"
    else:
        drawing_mode = "transform"

    st.subheader("Style")
    fill = st.color_picker("Fill color", "#cfead0" if drawing_mode!="rect" else "#bccdee")
    stroke = st.color_picker("Outline color", "#556")
    stroke_w = st.slider("Outline width", 1, 8, 2)
    seat_radius = st.slider("Seat radius (circle)", 8, 40, 14)
    st.caption("Tip: for long desks, pick rectangle tool and drag a long thin bar.")

    st.subheader("Grid / Export")
    show_grid = st.checkbox("Show grid", value=True)
    if st.button("🗑️ Clear all"):
        st.session_state.fabric = {"version":"5.2.4","objects":[]}
    if st.button("↩️ Undo last"):
        objs = st.session_state.fabric.get("objects", [])
        if objs:
            st.session_state.fabric["objects"] = objs[:-1]
    st.download_button(
        "⬇️ Download layout.json",
        data=json.dumps(st.session_state.fabric, indent=2),
        file_name="layout.json"
    )
    uploaded = st.file_uploader("Upload layout.json", type=["json"])
    if uploaded:
        st.session_state.fabric = json.loads(uploaded.read().decode("utf-8"))
        st.success("Layout loaded.")

# Background image (grid or solid)
bg_img = grid_image() if show_grid else Image.new("RGB", (W, H), BG)

# Canvas
st.caption("Draw: Rectangle = long desk, Circle = seat. Use Select/Move to reposition/resize. Hold Shift to constrain.")
canvas = st_canvas(
    background_image=bg_img,
    width=W,
    height=H,
    drawing_mode=drawing_mode,
    stroke_width=stroke_w,
    stroke_color=stroke,
    fill_color=fill,
    update_streamlit=True,
    initial_drawing=st.session_state.fabric,  # load prior objects
    display_toolbar=True,
    drawing_mode_dict={
        "rect": {"type": "rect"},
        "circle": {"type": "circle", "radius": seat_radius},  # radius hint
        "transform": {"type": "transform"}
    },
    key="map_canvas",
)

# Persist new drawing back into session
if canvas and canvas.json_data:
    st.session_state.fabric = canvas.json_data

# Export PNG snapshot
st.markdown("### Preview / Export PNG")
# Render a PNG by drawing the objects on top of the background
def render_png(fabric_json):
    out = (grid_image() if show_grid else Image.new("RGB",(W,H),BG)).copy()
    d = ImageDraw.Draw(out)
    for obj in fabric_json.get("objects", []):
        otype = obj.get("type")
        left = int(obj.get("left", 0))
        top  = int(obj.get("top", 0))
        angle = int(obj.get("angle", 0))

        if otype == "rect":
            w = int(obj.get("width", 60) * obj.get("scaleX", 1))
            h = int(obj.get("height", 20) * obj.get("scaleY", 1))
            x0, y0, x1, y1 = left, top, left + w, top + h
            d.rectangle([x0,y0,x1,y1], fill=obj.get("fill","#bccdee"), outline=obj.get("stroke","#556"), width=int(obj.get("strokeWidth",2)))
        elif otype == "circle":
            r = int(obj.get("radius", 14) * obj.get("scaleX", 1))
            x0, y0, x1, y1 = left - r, top - r, left + r, top + r
            d.ellipse([x0,y0,x1,y1], fill=obj.get("fill","#cfead0"), outline=obj.get("stroke","#556"), width=int(obj.get("strokeWidth",2)))
        # (fabric supports more types; we keep it minimal)

    return out

png = render_png(st.session_state.fabric)
st.image(np.array(png), use_container_width=True)
st.download_button("⬇️ Download map.png", data=png_to_bytes := png_to_bytes if 'png_to_bytes' in locals() else None)

# Helper to provide PNG bytes lazily
def _png_bytes(im: Image.Image) -> bytes:
    import io
    bio = io.BytesIO()
    im.save(bio, format="PNG")
    return bio.getvalue()

if 'png_to_bytes' not in locals():
    png_to_bytes = _png_bytes(png)

st.download_button("⬇️ Export PNG", data=png_to_bytes, file_name="desk_seat_map.png", mime="image/png")
