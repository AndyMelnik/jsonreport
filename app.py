import streamlit as st
import json
import pandas as pd
from io import BytesIO
from PIL import Image
import matplotlib.pyplot as plt
from reportlab.platypus import SimpleDocTemplate, Image as RLImage, Spacer
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch

st.set_page_config(layout="wide")
st.title("📊 JSON Report Visualizer")

def deduplicate_columns(columns):
    seen = {}
    result = []
    for col in columns:
        title = col.get("title", col.get("field", "")).strip()
        if not title:
            title = col.get("field", "")
        new_title = title
        count = 1
        while new_title in seen:
            new_title = f"{title}_{count}"
            count += 1
        seen[new_title] = True
        result.append(new_title)
    return result

def render_table(rows, columns):
    data = []
    for row in rows:
        r = [row.get(col["field"], {}).get("v", "") for col in columns]
        data.append(r)
    headers = deduplicate_columns(columns)
    return pd.DataFrame(data, columns=headers)

def render_map_table(rows):
    data = {item["name"]: item["v"] for item in rows}
    return pd.DataFrame([data])

def render_pie_chart(values):
    labels = [v["title"] for v in values]
    sizes = [v["raw"] for v in values]
    colors = [v.get("color", "#cccccc") for v in values]
    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%", startangle=90)
    ax.axis("equal")
    st.pyplot(fig)
    buf = BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf

def render_stacked_bar(data, series):
    dates = [d["x"]["v"] for d in data]
    values = {s["field"]: [d["bars"][s["field"]]["raw"] for d in data] for s in series}
    fig, ax = plt.subplots()
    bottom = [0] * len(dates)
    for s in series:
        ax.bar(dates, values[s["field"]], bottom=bottom, label=s["title"], color=s.get("color"))
        bottom = [bottom[i] + values[s["field"]][i] for i in range(len(dates))]
    ax.set_ylabel("Hours")
    ax.legend()
    st.pyplot(fig)
    buf = BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf

def render_dataframe_image(df):
    fig, ax = plt.subplots(figsize=(len(df.columns) * 1.2, len(df) * 0.5 + 1))
    ax.axis("off")
    tbl = ax.table(cellText=df.values, colLabels=df.columns, loc='center', cellLoc='left')
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    tbl.scale(1, 1.5)
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf

def render_separator():
    fig, ax = plt.subplots(figsize=(6, 0.2))
    ax.axis("off")
    ax.axhline(0.5, color="black", linewidth=2)
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches='tight')
    plt.close(fig)
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

    for i, sheet in enumerate(report.get("sheets", [])):
        st.subheader(sheet.get("header", f"Sheet {i+1}"))

        for j, section in enumerate(sheet.get("sections", [])):
            s_type = section.get("type")
            header = section.get("header", f"Section {j+1}")

            if s_type == "table":
                for k, data_group in enumerate(section.get("data", [])):
                    rows = data_group.get("rows", [])
                    columns = section["columns"]
                    df = render_table(rows, columns)
                    st.markdown(f"**{data_group.get('header', '')}**")
                    st.dataframe(df)

                    if st.checkbox("Include above table in PDF", key=f"table_{i}_{j}_{k}"):
                        buf = render_dataframe_image(df)
                        pdf_buffers.append(buf)

            elif s_type == "map_table":
                df = render_map_table(section["rows"])
                st.markdown(f"**{header}**")
                st.dataframe(df)

                if st.checkbox("Include map table in PDF", key=f"map_table_{i}_{j}"):
                    buf = render_dataframe_image(df)
                    pdf_buffers.append(buf)

            elif s_type == "pie_chart":
                st.markdown(f"**{header}**")
                buf = render_pie_chart(section["values"])

                if st.checkbox("Include pie chart in PDF", key=f"pie_chart_{i}_{j}"):
                    pdf_buffers.append(buf)

            elif s_type == "stacked_bar_chart":
                st.markdown(f"**{header}**")
                buf = render_stacked_bar(section["data"], section["series"])

                if st.checkbox("Include bar chart in PDF", key=f"bar_chart_{i}_{j}"):
                    pdf_buffers.append(buf)

            elif s_type == "separator":
                st.markdown("---")
                if st.checkbox("Include divider in PDF", key=f"separator_{i}_{j}"):
                    buf = render_separator()
                    pdf_buffers.append(buf)

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
