import streamlit as st
import pandas as pd
import json
import matplotlib.pyplot as plt
from fpdf import FPDF
from io import BytesIO
from PIL import Image
import os

# ---------- PDF Utility Functions ----------

FONT_PATH = "DejaVuSans.ttf"

def save_chart_as_image(fig):
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    return buf

def add_text_to_pdf(text):
    st.session_state.pdf_contents.append({"type": "text", "content": text})

def add_image_to_pdf(image_buf):
    st.session_state.pdf_contents.append({"type": "image", "content": image_buf})

def generate_pdf():
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Register a Unicode font
    if not os.path.exists(FONT_PATH):
        st.error(f"Font file '{FONT_PATH}' not found.")
        return None

    pdf.add_font("DejaVu", "", FONT_PATH, uni=True)
    pdf.set_font("DejaVu", size=12)

    for item in st.session_state.pdf_contents:
        if item["type"] == "text":
            pdf.add_page()
            pdf.multi_cell(0, 10, item["content"])
        elif item["type"] == "image":
            pdf.add_page()
            img = Image.open(item["content"])
            temp_path = "/tmp/temp_img.png"
            img.save(temp_path)
            pdf.image(temp_path, x=10, y=20, w=180)

    # Encode as bytes for download
    return pdf.output(dest="S").encode("utf-8")

# ---------- Section Renderers ----------

def render_table(section, sheet_index, section_index):
    for entry_index, entry in enumerate(section.get("data", [])):
        header = entry.get("header")
        rows = entry.get("rows", [])
        columns = section.get("columns", [])

        table_data = []
        for row in rows:
            row_data = {}
            for col in columns:
                field = col["field"]
                title = col["title"] or field
                row_data[title] = row.get(field, {}).get("v", "")
            table_data.append(row_data)

        if header:
            st.markdown(f"**{header}**")
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True)

        if st.button(f"➕ Add Table to PDF: {header or 'Unnamed'}", key=f"btn_table_{sheet_index}_{section_index}_{entry_index}"):
            add_text_to_pdf(df.to_string(index=False))


def render_map_table(section, sheet_index, section_index):
    rows = section.get("rows", [])
    df = pd.DataFrame([{r["name"]: r["v"]} for r in rows])
    st.dataframe(df, use_container_width=True)

    if st.button("➕ Add Map Table to PDF", key=f"btn_maptable_{sheet_index}_{section_index}"):
        add_text_to_pdf(df.to_string(index=False))


def render_pie_chart(section, sheet_index, section_index):
    values = section.get("values", [])
    labels = [item["title"] for item in values]
    sizes = [item["raw"] for item in values]
    colors = [item.get("color") for item in values]

    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%", startangle=140)
    ax.axis("equal")
    st.pyplot(fig)

    if st.button(f"➕ Add Pie Chart to PDF: {section.get('header', '')}", key=f"btn_pie_{sheet_index}_{section_index}"):
        img_buf = save_chart_as_image(fig)
        add_image_to_pdf(img_buf)


def render_stacked_bar_chart(section, sheet_index, section_index):
    data = section.get("data", [])
    series = section.get("series", [])
    x_labels = [item["x"]["v"] for item in data]
    bar_data = {s["field"]: [item["bars"][s["field"]]["raw"] for item in data] for s in series}
    bar_labels = [s["title"] for s in series]
    bar_colors = [s["color"] for s in series]

    df = pd.DataFrame(bar_data, index=x_labels)

    fig, ax = plt.subplots()
    bottom = None
    for i, (label, color) in enumerate(zip(bar_labels, bar_colors)):
        values = df.iloc[:, i]
        ax.bar(df.index, values, label=label, bottom=bottom, color=color)
        bottom = values if bottom is None else bottom + values

    ax.set_ylabel(section.get("y_axis", {}).get("label", ""))
    ax.set_title(section.get("header", "Stacked Bar Chart"))
    ax.legend()
    st.pyplot(fig)

    if st.button(f"➕ Add Stacked Bar Chart to PDF: {section.get('header', '')}", key=f"btn_stackbar_{sheet_index}_{section_index}"):
        img_buf = save_chart_as_image(fig)
        add_image_to_pdf(img_buf)


def render_section(section, sheet_index, section_index):
    section_type = section.get("type")
    if section_type == "table":
        render_table(section, sheet_index, section_index)
    elif section_type == "map_table":
        render_map_table(section, sheet_index, section_index)
    elif section_type == "pie_chart":
        render_pie_chart(section, sheet_index, section_index)
    elif section_type == "stacked_bar_chart":
        render_stacked_bar_chart(section, sheet_index, section_index)
    elif section_type == "separator":
        st.markdown("---")
        if st.button("➕ Add Divider to PDF", key=f"btn_separator_{sheet_index}_{section_index}"):
            add_text_to_pdf("\n----------------------------\n")
    else:
        st.warning(f"Unsupported section type: {section_type}")


def render_sheet(sheet, sheet_index):
    st.header(f"📄 {sheet.get('header')}")
    for section_index, section in enumerate(sheet.get("sections", [])):
        if header := section.get("header"):
            st.subheader(header)
        render_section(section, sheet_index, section_index)


def render_report(data):
    report = data.get("report", {})
    st.title(report.get("title", "Report"))
    st.markdown(f"**Created:** {report.get('created')}")
    st.markdown(f"**Report ID:** {report.get('id')}")

    time_filter = report.get("time_filter", {})
    st.markdown(f"**Time Filter:** {time_filter.get('from')} – {time_filter.get('to')} | Weekdays: {time_filter.get('weekdays')}")

    for sheet_index, sheet in enumerate(report.get("sheets", [])):
        render_sheet(sheet, sheet_index)

# ---------- Main App ----------

def main():
    st.set_page_config(page_title="Report Viewer & PDF Export", layout="wide")

    if "pdf_contents" not in st.session_state:
        st.session_state.pdf_contents = []

    st.sidebar.title("📁 Upload JSON Report")
    uploaded_file = st.sidebar.file_uploader("Upload a JSON file", type=["json"])

    if uploaded_file is not None:
        try:
            json_data = json.load(uploaded_file)
            render_report(json_data)

            if st.session_state.pdf_contents:
                pdf_data = generate_pdf()
                if pdf_data:
                    st.download_button("📥 Download PDF Report", pdf_data, file_name="report.pdf", mime="application/pdf")
        except Exception as e:
            st.error(f"Failed to parse JSON: {e}")
    else:
        st.info("Please upload a report JSON to begin.")

if __name__ == "__main__":
    main()
