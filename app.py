import streamlit as st
import pandas as pd
import json
import matplotlib.pyplot as plt
import io
from PIL import Image
from fpdf import FPDF
from pathlib import Path
import base64

st.set_page_config(layout="wide")

st.title("📊 JSON Report Visualizer & PDF Exporter")

def load_json(file):
    try:
        return json.load(file)
    except Exception as e:
        st.error(f"Failed to parse JSON: {e}")
        return None

def render_table(data, columns, title=None):
    df_data = []
    for row in data:
        flat_row = {}
        for col in columns:
            val = row.get(col["field"], {}).get("v", "")
            flat_row[col["title"] or col["field"]] = val
        df_data.append(flat_row)
    df = pd.DataFrame(df_data)
    return df

def df_to_image(df, title=None):
    fig, ax = plt.subplots(figsize=(min(20, len(df.columns)*2), 0.6*len(df) + 1.5))
    ax.axis('off')
    tbl = ax.table(cellText=df.values,
                   colLabels=df.columns,
                   loc='center',
                   cellLoc='center')
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    fig.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=200)
    buf.seek(0)
    img = Image.open(buf)
    plt.close(fig)
    return img

def chart_to_image(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches='tight', dpi=150)
    buf.seek(0)
    img = Image.open(buf)
    plt.close(fig)
    return img

def add_image_to_pdf(pdf, img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    temp_path = "/tmp/temp_chart.png"
    with open(temp_path, "wb") as f:
        f.write(buf.read())
    pdf.image(temp_path, x=10, w=190)

def generate_pdf(images):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    for img in images:
        pdf.add_page()
        add_image_to_pdf(pdf, img)
    output_path = Path("/mnt/data/generated_report.pdf")
    pdf.output(str(output_path))
    return output_path

uploaded_file = st.file_uploader("Upload JSON Report", type=["json"])

if uploaded_file:
    data = load_json(uploaded_file)
    if not data:
        st.stop()

    report = data.get("report", {})
    sheets = report.get("sheets", [])
    visuals = []

    st.subheader("📑 Report: " + report.get("title", "Untitled"))

    for sheet_idx, sheet in enumerate(sheets):
        st.markdown(f"## 📄 {sheet.get('header', 'Sheet')}")
        sections = sheet.get("sections", [])
        for section_idx, section in enumerate(sections):
            section_type = section.get("type")
            header = section.get("header", f"Section {section_idx}")
            unique_key = f"{sheet_idx}_{section_type}_{header}_{section_idx}"

            st.markdown(f"### 🔹 {header} ({section_type})")
            include = st.checkbox("Include in PDF", key=f"checkbox_{unique_key}")

            if section_type == "table":
                for data_block in section.get("data", []):
                    rows = data_block.get("rows", [])
                    columns = section.get("columns", [])
                    if rows:
                        df = render_table(rows, columns)
                        st.dataframe(df, use_container_width=True)
                        if include:
                            img = df_to_image(df)
                            visuals.append(img)

            elif section_type == "map_table":
                rows = section.get("rows", [])
                columns = [{"field": "name", "title": "Name"}] + [
                    {"field": "v", "title": "Value"}
                ]
                if rows:
                    df = render_table(rows, columns)
                    st.dataframe(df, use_container_width=True)
                    if include:
                        img = df_to_image(df)
                        visuals.append(img)

            elif section_type == "pie_chart":
                values = section.get("values", [])
                labels = [v.get("title", "") for v in values]
                sizes = [v.get("raw", 0) for v in values]
                colors = [v.get("color", "#cccccc") for v in values]
                fig, ax = plt.subplots()
                ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%')
                st.pyplot(fig)
                if include:
                    img = chart_to_image(fig)
                    visuals.append(img)

            elif section_type == "stacked_bar_chart":
                data_points = section.get("data", [])
                series = section.get("series", [])
                x_labels = [dp["x"]["v"] for dp in data_points]
                fig, ax = plt.subplots()
                bottom = [0] * len(x_labels)
                for serie in series:
                    field = serie["field"]
                    title = serie["title"]
                    color = serie["color"]
                    heights = [dp["bars"].get(field, {}).get("raw", 0) for dp in data_points]
                    ax.bar(x_labels, heights, bottom=bottom, label=title, color=color)
                    bottom = [sum(x) for x in zip(bottom, heights)]
                ax.set_ylabel("Hours")
                ax.set_xlabel(section.get("x_label", "Date"))
                ax.legend()
                st.pyplot(fig)
                if include:
                    img = chart_to_image(fig)
                    visuals.append(img)

            elif section_type == "separator":
                st.markdown("---")

    if visuals:
        if st.button("📥 Download PDF"):
            output_path = generate_pdf(visuals)
            with open(output_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
                href = f'<a href="data:application/octet-stream;base64,{b64}" download="report.pdf">Click here to download your PDF</a>'
                st.markdown(href, unsafe_allow_html=True)
    else:
        st.info("No visuals selected for PDF.")
