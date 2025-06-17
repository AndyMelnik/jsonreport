
import streamlit as st
import json
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Image, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from PIL import Image as PILImage
import tempfile
import uuid

st.set_page_config(layout="wide")
st.title("📊 JSON Report Visualizer & PDF Exporter")

# Store visuals selected for PDF
if "selected_visuals" not in st.session_state:
    st.session_state.selected_visuals = {}

# Helpers
def sanitize_text(text):
    return str(text).replace("\n", " ").replace("\r", "").strip()

def save_chart_as_image(fig):
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf

def df_to_image(df, title=None):
    num_rows, num_cols = df.shape
    fig_width = min(20, max(6, num_cols * 1.2))
    fig_height = min(20, max(3, num_rows * 0.4))

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    ax.axis('off')
    table = ax.table(cellText=df.values, colLabels=df.columns, cellLoc='center', loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(0.8, 0.8)

    if title:
        plt.title(sanitize_text(title), fontsize=10, pad=16)

    return save_chart_as_image(fig)

def plot_pie_chart(values, title):
    labels = [sanitize_text(item["title"]) for item in values]
    sizes = [item["raw"] for item in values]
    colors = [item.get("color", None) for item in values]

    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors, textprops={'fontsize': 8})
    ax.set_title(sanitize_text(title), fontsize=10)
    return save_chart_as_image(fig)

def plot_stacked_bar_chart(data, series, x_label, y_label):
    dates = [x["x"]["v"] for x in data]
    bar_data = {s["field"]: [x["bars"][s["field"]]["raw"] for x in data] for s in series}
    colors = [s["color"] for s in series]

    fig, ax = plt.subplots(figsize=(10, 4))
    bottom = [0] * len(dates)
    for idx, s in enumerate(series):
        ax.bar(dates, bar_data[s["field"]], bottom=bottom, label=s["title"], color=s["color"])
        bottom = [i + j for i, j in zip(bottom, bar_data[s["field"]])]

    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.legend(fontsize=8)
    plt.xticks(rotation=45)
    return save_chart_as_image(fig)

def add_visual_to_pdf_elements(image_buf, pdf_elements):
    with PILImage.open(image_buf) as img:
        temp_img = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        img.save(temp_img.name)
        pdf_elements.append(Image(temp_img.name, width=6.5*inch, preserveAspectRatio=True))
        pdf_elements.append(Spacer(1, 0.2 * inch))

def generate_pdf():
    pdf_elements = []
    for visual_id, content in st.session_state.selected_visuals.items():
        if content["include"]:
            add_visual_to_pdf_elements(content["image"], pdf_elements)
    if not pdf_elements:
        st.warning("No visuals selected for PDF.")
        return
    pdf_path = Path(tempfile.gettempdir()) / f"report_{uuid.uuid4().hex}.pdf"
    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)
    doc.build(pdf_elements)
    with open(pdf_path, "rb") as f:
        st.download_button("📥 Download PDF", f, file_name="report.pdf", mime="application/pdf")

# Main
uploaded_file = st.file_uploader("Upload JSON Report", type=["json"])
if uploaded_file:
    try:
        raw = uploaded_file.read()
        decoded = raw.decode("utf-8", errors="replace")
        report_data = json.loads(decoded)
    except Exception as e:
        st.error(f"Failed to parse JSON: {e}")
        st.stop()

    report = report_data.get("report", {})
    st.header(sanitize_text(report.get("title", "Report")))

    for sheet_idx, sheet in enumerate(report.get("sheets", [])):
        with st.expander(f"📄 Sheet: {sanitize_text(sheet.get('header', 'Unnamed Sheet'))}", expanded=True):
            for section_idx, section in enumerate(sheet.get("sections", [])):
                if not isinstance(section, dict):
                    continue
                section_type = section.get("type", "")
                visual_id = f"{section_type}_{sheet_idx}_{section_idx}"

                if section_type == "table":
                    data = section.get("data", [])
                    for group_idx, group in enumerate(data):
                        group_header = sanitize_text(group.get("header", f"Table {group_idx+1}"))
                        rows = group.get("rows", [])
                        if not rows:
                            continue
                        df = pd.DataFrame([{col: sanitize_text(str(cell.get("v", ""))) for col, cell in row.items()} for row in rows])
                        st.subheader(group_header)
                        st.dataframe(df)

                        img = df_to_image(df, group_header)
                        st.checkbox("Include in PDF", key=visual_id + f"_g{group_idx}", on_change=lambda v=visual_id, g=group_idx, i=img: st.session_state.selected_visuals.update({f"{v}_g{g}": {"include": st.session_state[f"{v}_g{g}"], "image": i}}))

                elif section_type == "map_table":
                    df = pd.DataFrame([{col["name"]: col.get("v", "") for col in section.get("rows", [])}])
                    st.subheader(sanitize_text(section.get("header", "Map Table")))
                    st.dataframe(df.T)
                    img = df_to_image(df.T, section.get("header", ""))
                    st.checkbox("Include in PDF", key=visual_id, on_change=lambda v=visual_id, i=img: st.session_state.selected_visuals.update({v: {"include": st.session_state[v], "image": i}}))

                elif section_type == "pie_chart":
                    values = section.get("values", [])
                    if values:
                        st.subheader(sanitize_text(section.get("header", "Pie Chart")))
                        img = plot_pie_chart(values, section.get("header", ""))
                        st.image(img, caption="Pie Chart")
                        st.checkbox("Include in PDF", key=visual_id, on_change=lambda v=visual_id, i=img: st.session_state.selected_visuals.update({v: {"include": st.session_state[v], "image": i}}))

                elif section_type == "stacked_bar_chart":
                    st.subheader(sanitize_text(section.get("header", "Stacked Bar Chart")))
                    data = section.get("data", [])
                    series = section.get("series", [])
                    x_label = section.get("x_label", "")
                    y_label = section.get("y_axis", {}).get("label", "")
                    if data and series:
                        img = plot_stacked_bar_chart(data, series, x_label, y_label)
                        st.image(img, caption="Stacked Bar Chart")
                        st.checkbox("Include in PDF", key=visual_id, on_change=lambda v=visual_id, i=img: st.session_state.selected_visuals.update({v: {"include": st.session_state[v], "image": i}}))

    st.markdown("---")
    st.button("📥 Generate PDF from Selected Visuals", on_click=generate_pdf)
