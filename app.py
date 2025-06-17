
import streamlit as st
import json
import pandas as pd
from io import BytesIO
from PIL import Image
import matplotlib.pyplot as plt
from reportlab.platypus import SimpleDocTemplate, Image as RLImage, Spacer
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
import uuid

st.set_page_config(layout="wide")

st.title("📊 JSON Report Visualizer")

def render_table(rows, columns):
    data = []
    for row in rows:
        r = []
        for col in columns:
            val = row.get(col["field"], {})
            r.append(val.get("v", ""))
        data.append(r)
    headers = [col["title"] for col in columns]
    return pd.DataFrame(data, columns=headers)

def render_map_table(rows):
    data = {item["name"]: item["v"] for item in rows}
    return pd.DataFrame([data])

def render_pie_chart(values, header, chart_id):
    labels = [v["title"] for v in values]
    sizes = [v["raw"] for v in values]
    colors = [v["color"] for v in values]
    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%", startangle=90)
    ax.axis("equal")
    st.pyplot(fig)
    buf = BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    return buf

def render_stacked_bar(data, series, header, chart_id):
    dates = [d["x"]["v"] for d in data]
    values = {s["field"]: [d["bars"][s["field"]]["raw"] for d in data] for s in series}
    fig, ax = plt.subplots()
    bottom = [0] * len(dates)
    for s in series:
        ax.bar(dates, values[s["field"]], bottom=bottom, label=s["title"], color=s["color"])
        bottom = [bottom[i] + values[s["field"]][i] for i in range(len(dates))]
    ax.set_ylabel("Hours")
    ax.legend()
    st.pyplot(fig)
    buf = BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    return buf

uploaded_file = st.file_uploader("Upload JSON report file", type="json")
if uploaded_file:
    try:
        json_data = json.load(uploaded_file)
    except Exception as e:
        st.error(f"Failed to parse JSON: {e}")
        st.stop()

    report = json_data.get("report", {})
    st.header(report.get("title", "Untitled Report"))

    pdf_buffers = []
    inclusion_flags = []

    for i, sheet in enumerate(report.get("sheets", [])):
        st.subheader(sheet.get("header", f"Sheet {i+1}"))
        for j, section in enumerate(sheet.get("sections", [])):
            s_type = section.get("type")
            header = section.get("header", "")
            unique_prefix = f"{i}_{j}_{uuid.uuid4().hex[:8]}"

            if s_type == "table":
                for data_group in section["data"]:
                    rows = data_group.get("rows", [])
                    columns = section["columns"]
                    df = render_table(rows, columns)
                    st.markdown(f"**{data_group.get('header', '')}**")
                    st.dataframe(df)
                    include = st.checkbox("Include above table in PDF", key=f"table_{unique_prefix}")
                    if include:
                        fig, ax = plt.subplots(figsize=(len(df.columns)*1.2, len(df)*0.5 + 1))
                        ax.axis("off")
                        tbl = ax.table(cellText=df.values, colLabels=df.columns, loc='center', cellLoc='left')
                        tbl.auto_set_font_size(False)
                        tbl.set_fontsize(8)
                        tbl.scale(1, 1.5)
                        buf = BytesIO()
                        fig.savefig(buf, format="png", bbox_inches='tight')
                        buf.seek(0)
                        pdf_buffers.append(buf)
            elif s_type == "map_table":
                df = render_map_table(section["rows"])
                st.markdown(f"**{header}**")
                st.dataframe(df)
                include = st.checkbox("Include map table in PDF", key=f"map_table_{unique_prefix}")
                if include:
                    fig, ax = plt.subplots(figsize=(len(df.columns)*1.2, len(df)*0.5 + 1))
                    ax.axis("off")
                    tbl = ax.table(cellText=df.values, colLabels=df.columns, loc='center', cellLoc='left')
                    tbl.auto_set_font_size(False)
                    tbl.set_fontsize(8)
                    tbl.scale(1, 1.5)
                    buf = BytesIO()
                    fig.savefig(buf, format="png", bbox_inches='tight')
                    buf.seek(0)
                    pdf_buffers.append(buf)
            elif s_type == "pie_chart":
                st.markdown(f"**{header}**")
                pie_buf = render_pie_chart(section["values"], header, chart_id=unique_prefix)
                include = st.checkbox("Include pie chart in PDF", key=f"pie_chart_{unique_prefix}")
                if include:
                    pdf_buffers.append(pie_buf)
            elif s_type == "stacked_bar_chart":
                st.markdown(f"**{header}**")
                bar_buf = render_stacked_bar(section["data"], section["series"], header, chart_id=unique_prefix)
                include = st.checkbox("Include bar chart in PDF", key=f"bar_chart_{unique_prefix}")
                if include:
                    pdf_buffers.append(bar_buf)
            elif s_type == "separator":
                st.markdown("---")
                include = st.checkbox("Include divider in PDF", key=f"separator_{unique_prefix}")
                if include:
                    sep_buf = BytesIO()
                    fig, ax = plt.subplots(figsize=(6, 0.2))
                    ax.axis("off")
                    ax.axhline(0.5, color="black", linewidth=2)
                    fig.savefig(sep_buf, format="png", bbox_inches='tight')
                    sep_buf.seek(0)
                    pdf_buffers.append(sep_buf)

    if pdf_buffers and st.button("📄 Generate PDF"):
        output = BytesIO()
        doc = SimpleDocTemplate(output, pagesize=letter)
        elements = []
        for buf in pdf_buffers:
            img = RLImage(buf, width=6.5 * inch)
            elements.append(img)
            elements.append(Spacer(1, 0.2 * inch))
        doc.build(elements)
        st.download_button("📥 Download PDF", data=output.getvalue(), file_name="report.pdf", mime="application/pdf")
