
import streamlit as st
import json
import pandas as pd
import matplotlib.pyplot as plt
import uuid
from io import BytesIO
from pathlib import Path
from PIL import Image
from fpdf import FPDF

st.set_page_config(layout="wide")
st.title("📊 JSON Report Viewer & PDF Exporter")

def render_table(rows, columns):
    data = []
    col_titles = [col["title"] for col in columns]

    for row in rows:
        if isinstance(row, dict):
            data.append([
                row.get(col["field"], {}).get("v", "") for col in columns
            ])
        else:
            data.append(["?" for _ in columns])

    df = pd.DataFrame(data, columns=col_titles)
    return df

def fig_to_image(fig):
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    return buf

def add_image_to_pdf(pdf, image_buf):
    pdf.add_page()
    img = Image.open(image_buf)
    width, height = img.size
    max_width = 180
    ratio = max_width / width
    new_height = height * ratio
    image_path = f"/tmp/{uuid.uuid4()}.png"
    img.save(image_path)
    pdf.image(image_path, x=10, y=10, w=max_width, h=new_height)

uploaded_file = st.file_uploader("Upload JSON report", type="json")

if uploaded_file:
    try:
        report = json.load(uploaded_file)
    except Exception as e:
        st.error(f"Failed to parse JSON: {e}")
        st.stop()

    visuals_to_export = []

    for sheet_idx, sheet in enumerate(report["report"]["sheets"]):
        st.header(f"📄 {sheet.get('header', 'Untitled Sheet')}")
        for section_idx, section in enumerate(sheet.get("sections", [])):
            section_type = section.get("type")
            header = section.get("header", f"Section {section_idx}")
            key_base = f"{sheet_idx}_{section_type}_{header.replace(' ', '_')}_{section_idx}"
            include = st.checkbox(f"Include '{header}' ({section_type}) in PDF", key=f"include_{key_base}")

            if section_type == "table":
                for group_idx, group in enumerate(section.get("data", [])):
                    rows = group.get("rows", [])
                    columns = section.get("columns", [])
                    df = render_table(rows, columns)
                    st.markdown(f"**{group.get('header', '')}**")
                    st.dataframe(df)
                    if include:
                        fig, ax = plt.subplots(figsize=(min(16, 1 + len(columns)), 0.5 + 0.3 * len(df)))
                        ax.axis("off")
                        table = ax.table(cellText=df.values, colLabels=df.columns, loc="center", cellLoc='center')
                        table.auto_set_font_size(False)
                        table.set_fontsize(8)
                        table.scale(1, 1.3)
                        buf = fig_to_image(fig)
                        visuals_to_export.append(buf)
                        plt.close(fig)

            elif section_type == "map_table":
                data = section.get("rows", [])
                df = pd.DataFrame([{row["name"]: row.get("v", "")} for row in data])
                st.dataframe(df.T)
                if include:
                    fig, ax = plt.subplots(figsize=(6, 0.5 + 0.3 * len(df)))
                    ax.axis("off")
                    table = ax.table(cellText=df.values, colLabels=df.columns, rowLabels=df.index, loc="center")
                    table.auto_set_font_size(False)
                    table.set_fontsize(8)
                    table.scale(1, 1.2)
                    buf = fig_to_image(fig)
                    visuals_to_export.append(buf)
                    plt.close(fig)

            elif section_type == "pie_chart":
                labels = [v["title"] for v in section.get("values", [])]
                sizes = [v["raw"] for v in section.get("values", [])]
                colors = [v.get("color") for v in section.get("values", [])]
                fig, ax = plt.subplots()
                ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%')
                st.pyplot(fig)
                if include:
                    buf = fig_to_image(fig)
                    visuals_to_export.append(buf)
                    plt.close(fig)

            elif section_type == "stacked_bar_chart":
                data = section.get("data", [])
                x_labels = [d["x"]["v"] for d in data]
                series = section.get("series", [])
                fig, ax = plt.subplots()
                bottoms = [0] * len(data)
                for s in series:
                    vals = [d["bars"][s["field"]]["raw"] for d in data]
                    ax.bar(x_labels, vals, bottom=bottoms, label=s["title"], color=s.get("color"))
                    bottoms = [sum(x) for x in zip(bottoms, vals)]
                ax.set_ylabel(section.get("y_axis", {}).get("label", "Value"))
                ax.legend()
                st.pyplot(fig)
                if include:
                    buf = fig_to_image(fig)
                    visuals_to_export.append(buf)
                    plt.close(fig)

            elif section_type == "separator":
                st.markdown("---")

    if visuals_to_export:
        if st.button("📥 Export selected visuals to PDF"):
            pdf = FPDF()
            for image_buf in visuals_to_export:
                add_image_to_pdf(pdf, image_buf)
            output_path = "/mnt/data/visual_report.pdf"
            pdf.output(output_path)
            st.success("✅ PDF generated successfully!")
            st.download_button("Download PDF", data=open(output_path, "rb"), file_name="visual_report.pdf", mime="application/pdf")

