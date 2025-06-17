
import streamlit as st
import pandas as pd
import json
import io
import matplotlib.pyplot as plt
from fpdf import FPDF
from PIL import Image

# Setup session state for selected visuals
if "visuals" not in st.session_state:
    st.session_state.visuals = []
if "selected_visuals" not in st.session_state:
    st.session_state.selected_visuals = set()

def sanitize_text(text, encoding="latin-1", replacement="?"):
    if isinstance(text, str):
        return text.encode(encoding, errors="replace").decode(encoding).replace("�", replacement)
    return str(text)

def save_chart_as_image(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches='tight')
    buf.seek(0)
    return buf

def df_to_image(df, title=None):
    num_rows, num_cols = df.shape
    fig_width = min(20, max(6, num_cols * 1.2))
    fig_height = min(20, max(3, num_rows * 0.4))

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    ax.axis('off')

    table = ax.table(
        cellText=df.values,
        colLabels=df.columns,
        cellLoc='center',
        loc='center'
    )

    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(0.8, 0.8)

    if title:
        plt.title(sanitize_text(title), fontsize=10, pad=16)

    return save_chart_as_image(fig)

def add_table_to_gui_and_pdf(table_data, section_key, table_key, header):
    rows = table_data.get("rows", [])
    columns = table_data.get("columns", [])
    if not rows or not columns:
        return

    headers = [sanitize_text(col.get("title", "")) for col in columns]
    for group in rows:
        visual_id = f"table_{section_key}_{table_key}_{group.get('header', '')}"
        with st.expander(group.get("header", "Table")):
            st.markdown(f"#### {header}")
            data = []
            for row in group["rows"]:
                parsed_row = []
                for col in columns:
                    val = row.get(col["field"], {})
                    parsed_row.append(val.get("v", ""))
                data.append(parsed_row)

            df = pd.DataFrame(data, columns=headers)
            st.dataframe(df)

            include = st.checkbox("Include in PDF", key=f"check_{visual_id}")
            if include:
                img_buf = df_to_image(df, title=group.get("header", "Table"))
                st.session_state.visuals.append(("image", img_buf))

def add_map_table_to_gui_and_pdf(map_table, section_key):
    rows = map_table.get("rows", [])
    if not rows:
        return

    data = []
    labels = []
    for row in rows:
        labels.append(sanitize_text(row.get("name", "")))
        data.append(sanitize_text(row.get("v", "")))

    df = pd.DataFrame([data], columns=labels)
    st.markdown(f"#### {map_table.get('header', 'Map Table')}")
    st.dataframe(df.T)

    visual_id = f"map_table_{section_key}"
    include = st.checkbox("Include in PDF", key=f"check_{visual_id}")
    if include:
        img_buf = df_to_image(df.T, title=map_table.get("header", "Map Table"))
        st.session_state.visuals.append(("image", img_buf))

def add_pie_chart_to_gui_and_pdf(chart, section_key, chart_key):
    labels = [sanitize_text(v["title"]) for v in chart["values"]]
    sizes = [v["raw"] for v in chart["values"]]
    colors = [v.get("color", None) for v in chart["values"]]

    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
    ax.axis('equal')
    st.pyplot(fig)

    visual_id = f"pie_{section_key}_{chart_key}"
    include = st.checkbox("Include in PDF", key=f"check_{visual_id}")
    if include:
        img_buf = save_chart_as_image(fig)
        st.session_state.visuals.append(("image", img_buf))

def add_stacked_bar_chart_to_gui_and_pdf(chart, section_key, chart_key):
    data = chart["data"]
    series = chart["series"]
    labels = [d["x"]["v"] for d in data]
    fig, ax = plt.subplots()

    bottoms = [0] * len(labels)
    for s in series:
        values = [d["bars"][s["field"]]["raw"] for d in data]
        ax.bar(labels, values, bottom=bottoms, label=s["title"], color=s.get("color", None))
        bottoms = [bottoms[i] + values[i] for i in range(len(values))]

    ax.set_ylabel(chart.get("y_axis", {}).get("label", ""))
    ax.legend()
    st.pyplot(fig)

    visual_id = f"bar_{section_key}_{chart_key}"
    include = st.checkbox("Include in PDF", key=f"check_{visual_id}")
    if include:
        img_buf = save_chart_as_image(fig)
        st.session_state.visuals.append(("image", img_buf))

def process_section(section, section_key, sheet_title):
    section_type = section["type"]
    if section_type == "table":
        add_table_to_gui_and_pdf(section["data"], section_key, section.get("header", "0"), section.get("header", ""))
    elif section_type == "map_table":
        add_map_table_to_gui_and_pdf(section, section_key)
    elif section_type == "pie_chart":
        add_pie_chart_to_gui_and_pdf(section, section_key, section.get("header", "0"))
    elif section_type == "stacked_bar_chart":
        add_stacked_bar_chart_to_gui_and_pdf(section, section_key, section.get("header", "0"))
    elif section_type == "separator":
        st.markdown("---")

def generate_pdf():
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    for content_type, content in st.session_state.visuals:
        pdf.add_page()
        if content_type == "image":
            image = Image.open(content)
            image_path = f"/tmp/img_{id(content)}.png"
            image.save(image_path)
            pdf.image(image_path, x=10, y=10, w=190)

    pdf_output = io.BytesIO()
    pdf.output(pdf_output)
    pdf_output.seek(0)
    return pdf_output

# --- Streamlit App ---
st.title("JSON Report Visualizer and Export to PDF")

uploaded_file = st.file_uploader("Upload JSON report file", type=["json"])

if uploaded_file:
    try:
        report_json = json.load(uploaded_file)
        report = report_json.get("report", {})
        st.subheader(f"Report: {report.get('title', 'Untitled')}")
        sheets = report.get("sheets", [])

        st.session_state.visuals = []  # Reset visuals list

        for sheet_idx, sheet in enumerate(sheets):
            with st.expander(f"📄 Sheet: {sheet.get('header', f'Sheet {sheet_idx+1}')}"):
                sections = sheet.get("sections", [])
                for sec_idx, section in enumerate(sections):
                    process_section(section, f"{sheet_idx}_{sec_idx}", sheet.get("header", ""))

        if st.button("📥 Download PDF with selected visuals"):
            pdf_file = generate_pdf()
            st.download_button(
                label="Download PDF",
                data=pdf_file,
                file_name="report.pdf",
                mime="application/pdf"
            )

    except Exception as e:
        st.error(f"Failed to parse JSON: {e}")
