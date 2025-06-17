
import streamlit as st
import pandas as pd
import json
import io
import matplotlib.pyplot as plt
from fpdf import FPDF
from PIL import Image
import tempfile

st.set_page_config(page_title="JSON Report Visualizer", layout="wide")

# Store selected visuals
if "selected_visuals" not in st.session_state:
    st.session_state.selected_visuals = {}

st.title("📊 JSON Report Visualizer with PDF Export")

uploaded_file = st.file_uploader("Upload your JSON report file", type=["json"])

def render_table_image(df, title):
    fig, ax = plt.subplots(figsize=(min(12, len(df.columns) * 1.5), 0.6 + len(df) * 0.5))
    ax.axis('tight')
    ax.axis('off')
    table = ax.table(cellText=df.values, colLabels=df.columns, cellLoc='center', loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.5)
    buf = io.BytesIO()
    plt.title(title, fontsize=12)
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf

def add_image_to_pdf(pdf, image_data):
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(image_data.read())
        tmp_path = tmp.name
    pdf.add_page()
    pdf.image(tmp_path, x=10, y=10, w=190)
    Path(tmp_path).unlink(missing_ok=True)

def render_section(section, sheet_idx, section_idx):
    section_type = section.get("type", "")
    key_base = f"{section_type}_{sheet_idx}_{section_idx}"
    if section_type == "table":
        for block_idx, block in enumerate(section.get("data", [])):
            rows = block.get("rows", [])
            if rows:
                df = pd.DataFrame([{col["field"]: row.get(col["field"], {}).get("v", "") for col in section["columns"]} for row in rows])
                title = f"{section.get('header', '')} - {block.get('header', '')}".strip(" -")
                st.subheader(title)
                st.dataframe(df)
                checkbox_id = f"{key_base}_block_{block_idx}"
                st.session_state.selected_visuals[checkbox_id] = st.checkbox("Include in PDF", key=checkbox_id, value=False)
                if "rendered_tables" not in st.session_state:
                    st.session_state.rendered_tables = {}
                st.session_state.rendered_tables[checkbox_id] = render_table_image(df, title)

    elif section_type == "map_table":
        rows = section.get("rows", [])
        if rows:
            df = pd.DataFrame([{k: v.get("v", "") if isinstance(v, dict) else v for k, v in row.items()} for row in rows])
            title = section.get("header", "Map Table")
            st.subheader(title)
            st.dataframe(df)
            checkbox_id = key_base
            st.session_state.selected_visuals[checkbox_id] = st.checkbox("Include in PDF", key=checkbox_id, value=False)
            if "rendered_tables" not in st.session_state:
                st.session_state.rendered_tables = {}
            st.session_state.rendered_tables[checkbox_id] = render_table_image(df, title)

    elif section_type == "pie_chart":
        values = section.get("values", [])
        if values:
            labels = [v.get("title", "") for v in values]
            sizes = [v.get("raw", 0) for v in values]
            fig, ax = plt.subplots()
            ax.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=90)
            ax.axis("equal")
            title = section.get("header", "Pie Chart")
            st.subheader(title)
            st.pyplot(fig)
            chart_buf = io.BytesIO()
            fig.savefig(chart_buf, format="png", bbox_inches='tight')
            chart_buf.seek(0)
            checkbox_id = key_base
            st.session_state.selected_visuals[checkbox_id] = st.checkbox("Include in PDF", key=checkbox_id, value=False)
            if "rendered_charts" not in st.session_state:
                st.session_state.rendered_charts = {}
            st.session_state.rendered_charts[checkbox_id] = chart_buf
            plt.close(fig)

    elif section_type == "stacked_bar_chart":
        data = section.get("data", [])
        series = section.get("series", [])
        if data and series:
            x_labels = [x.get("x", {}).get("v", "") for x in data]
            fig, ax = plt.subplots()
            bottoms = [0] * len(data)
            for s in series:
                values = [x["bars"].get(s["field"], {}).get("raw", 0) for x in data]
                ax.bar(x_labels, values, label=s.get("title", ""), bottom=bottoms)
                bottoms = [sum(x) for x in zip(bottoms, values)]
            ax.legend()
            title = section.get("header", "Stacked Bar Chart")
            st.subheader(title)
            st.pyplot(fig)
            chart_buf = io.BytesIO()
            fig.savefig(chart_buf, format="png", bbox_inches='tight')
            chart_buf.seek(0)
            checkbox_id = key_base
            st.session_state.selected_visuals[checkbox_id] = st.checkbox("Include in PDF", key=checkbox_id, value=False)
            if "rendered_charts" not in st.session_state:
                st.session_state.rendered_charts = {}
            st.session_state.rendered_charts[checkbox_id] = chart_buf
            plt.close(fig)

if uploaded_file:
    try:
        report_json = json.load(uploaded_file)
        sheets = report_json.get("report", {}).get("sheets", [])
        st.markdown("### 📄 Report Preview")
        for sheet_idx, sheet in enumerate(sheets):
            st.header(sheet.get("header", f"Sheet {sheet_idx+1}"))
            for section_idx, section in enumerate(sheet.get("sections", [])):
                if isinstance(section, dict):
                    render_section(section, sheet_idx, section_idx)

        if st.button("📥 Download PDF"):
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            for key, selected in st.session_state.selected_visuals.items():
                if selected:
                    if key in st.session_state.get("rendered_tables", {}):
                        add_image_to_pdf(pdf, st.session_state.rendered_tables[key])
                    elif key in st.session_state.get("rendered_charts", {}):
                        add_image_to_pdf(pdf, st.session_state.rendered_charts[key])
            pdf_output = io.BytesIO()
            pdf.output(pdf_output)
            pdf_output.seek(0)
            st.download_button("📎 Click to Download PDF", data=pdf_output, file_name="report.pdf", mime="application/pdf")

    except Exception as e:
        st.error(f"❌ Failed to parse JSON: {e}")
