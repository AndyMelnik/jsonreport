
import streamlit as st
import pandas as pd
import json
import io
from PIL import Image
import matplotlib.pyplot as plt
import tempfile
from reportlab.platypus import SimpleDocTemplate, Image as RLImage, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from pathlib import Path

st.set_page_config(layout="wide")

st.title("JSON Report Viewer & PDF Generator")

def render_table(rows, columns):
    data = []
    col_titles = []
    used_titles = set()
    for col in columns:
        title = col["title"].strip() or col["field"]
        # Ensure column names are unique
        while title in used_titles:
            title += "_"
        used_titles.add(title)
        col_titles.append(title)

    for row in rows:
        if isinstance(row, dict):
            data.append([
                row.get(col["field"], {}).get("v", "") for col in columns
            ])
        else:
            data.append(["?" for _ in columns])

    df = pd.DataFrame(data, columns=col_titles)
    return df

def render_chart_as_image(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf

uploaded_file = st.file_uploader("Upload your JSON report", type="json")

if uploaded_file:
    try:
        report_json = json.load(uploaded_file)
    except Exception as e:
        st.error(f"Failed to parse JSON: {e}")
        st.stop()

    report = report_json.get("report", {})
    sheets = report.get("sheets", [])
    st.header(report.get("title", "Report"))

    pdf_elements = []
    export_options = []

    for si, sheet in enumerate(sheets):
        st.subheader(f"📄 {sheet.get('header', 'Untitled Sheet')}")
        for sec_i, section in enumerate(sheet.get("sections", [])):
            st.markdown(f"**Section {sec_i+1}: {section.get('type', 'Unknown')} - {section.get('header', '')}**")

            unique_prefix = f"{si}_{sec_i}"

            if section["type"] == "table":
                for data_group in section.get("data", []):
                    rows = data_group.get("rows", [])
                    if not rows:
                        continue
                    df = render_table(rows, section["columns"])
                    st.dataframe(df)
                    if st.checkbox("Include above table in PDF", key=f"include_{unique_prefix}_{id(df)}"):
                        fig, ax = plt.subplots(figsize=(10, min(0.5 + 0.3 * len(df), 10)))
                        ax.axis('off')
                        tbl = ax.table(cellText=df.values, colLabels=df.columns, loc='center')
                        tbl.scale(1, 1.5)
                        buf = render_chart_as_image(fig)
                        pdf_elements.append(buf)

            elif section["type"] == "pie_chart":
                labels = [v["title"] for v in section["values"]]
                sizes = [v["raw"] for v in section["values"]]
                colors = [v.get("color", "#cccccc") for v in section["values"]]
                fig, ax = plt.subplots()
                ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=140)
                ax.axis('equal')
                st.pyplot(fig)
                if st.checkbox("Include above pie chart in PDF", key=f"include_pie_{unique_prefix}"):
                    buf = render_chart_as_image(fig)
                    pdf_elements.append(buf)

            elif section["type"] == "stacked_bar_chart":
                x = [d["x"]["v"] for d in section["data"]]
                fig, ax = plt.subplots()
                bottom = [0]*len(x)
                for series in section["series"]:
                    y = [d["bars"][series["field"]]["raw"] for d in section["data"]]
                    ax.bar(x, y, bottom=bottom, label=series["title"], color=series.get("color"))
                    bottom = [i+j for i,j in zip(bottom, y)]
                ax.set_ylabel(section["y_axis"].get("label", "Value"))
                ax.legend()
                st.pyplot(fig)
                if st.checkbox("Include above bar chart in PDF", key=f"include_bar_{unique_prefix}"):
                    buf = render_chart_as_image(fig)
                    pdf_elements.append(buf)

    if pdf_elements and st.button("Generate PDF"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmpfile:
            doc = SimpleDocTemplate(tmpfile.name, pagesize=A4)
            story = []
            for img_buf in pdf_elements:
                img = RLImage(img_buf, width=6.5*inch)
                story.append(img)
                story.append(Spacer(1, 0.2 * inch))
            doc.build(story)
            st.success("PDF generated!")
            with open(tmpfile.name, "rb") as f:
                st.download_button("📄 Download PDF", f, file_name="report.pdf")
