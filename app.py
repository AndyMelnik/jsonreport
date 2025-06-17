import streamlit as st
import pandas as pd
import json
import matplotlib.pyplot as plt
from fpdf import FPDF
from io import BytesIO
from PIL import Image

# ---------- Sanitization ----------

def sanitize_text(text):
    """Ensure text is safely encodable in latin-1 (used by FPDF)."""
    if isinstance(text, str):
        return text.encode("latin-1", errors="replace").decode("latin-1")
    return str(text)

# ---------- PDF Utilities ----------

def save_chart_as_image(fig):
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    return buf

def add_text_to_pdf(text):
    st.session_state.pdf_contents.append({"type": "text", "content": sanitize_text(text)})

def add_image_to_pdf(image_buf):
    st.session_state.pdf_contents.append({"type": "image", "content": image_buf})

def generate_pdf():
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)

    for item in st.session_state.pdf_contents:
        if item["type"] == "text":
            pdf.add_page()
            pdf.multi_cell(0, 10, item["content"])
        elif item["type"] == "image":
            pdf.add_page()
            img = Image.open(item["content"])
            temp_path = "/tmp/tmp_chart.png"
            img.save(temp_path)
            pdf.image(temp_path, x=10, y=20, w=180)

    # ✅ Safe encoding
    return pdf.output(dest="S").encode("latin-1", errors="replace")

# ---------- Renderers ----------

def render_table(section, sheet_idx, sec_idx):
    for entry_idx, entry in enumerate(section.get("data", [])):
        header = entry.get("header")
        rows = entry.get("rows", [])
        columns = section.get("columns", [])

        table_data = []
        for row in rows:
            row_data = {
                sanitize_text(col.get("title") or col["field"]): sanitize_text(row.get(col["field"], {}).get("v", ""))
                for col in columns
            }
            table_data.append(row_data)

        if header:
            st.markdown(f"**{sanitize_text(header)}**")
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True)

        if st.button("➕ Add Table to PDF", key=f"table_{sheet_idx}_{sec_idx}_{entry_idx}"):
            add_text_to_pdf(df.to_string(index=False))


def render_map_table(section, sheet_idx, sec_idx):
    rows = section.get("rows", [])
    df = pd.DataFrame([{sanitize_text(r["name"]): sanitize_text(r["v"])} for r in rows])
    st.dataframe(df, use_container_width=True)

    if st.button("➕ Add Map Table to PDF", key=f"map_{sheet_idx}_{sec_idx}"):
        add_text_to_pdf(df.to_string(index=False))


def render_pie_chart(section, sheet_idx, sec_idx):
    values = section.get("values", [])
    labels = [sanitize_text(v["title"]) for v in values]
    sizes = [v["raw"] for v in values]
    colors = [v.get("color") for v in values]

    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%", startangle=140)
    ax.axis("equal")
    st.pyplot(fig)

    if st.button("➕ Add Pie Chart to PDF", key=f"pie_{sheet_idx}_{sec_idx}"):
        add_image_to_pdf(save_chart_as_image(fig))


def render_stacked_bar_chart(section, sheet_idx, sec_idx):
    data = section.get("data", [])
    series = section.get("series", [])
    x_labels = [sanitize_text(item["x"]["v"]) for item in data]
    bar_data = {
        s["field"]: [item["bars"][s["field"]]["raw"] for item in data] for s in series
    }
    df = pd.DataFrame(bar_data, index=x_labels)

    fig, ax = plt.subplots()
    bottom = None
    for s in series:
        values = df[s["field"]]
        ax.bar(df.index, values, label=sanitize_text(s["title"]), color=s["color"], bottom=bottom)
        bottom = values if bottom is None else bottom + values

    y_label = sanitize_text(section.get("y_axis", {}).get("label", ""))
    ax.set_ylabel(y_label)
    ax.set_title(sanitize_text(section.get("header", "Stacked Bar Chart")))
    ax.legend()
    st.pyplot(fig)

    if st.button("➕ Add Stacked Bar Chart to PDF", key=f"stackbar_{sheet_idx}_{sec_idx}"):
        add_image_to_pdf(save_chart_as_image(fig))


def render_section(section, sheet_idx, sec_idx):
    sec_type = section.get("type")
    if sec_type == "table":
        render_table(section, sheet_idx, sec_idx)
    elif sec_type == "map_table":
        render_map_table(section, sheet_idx, sec_idx)
    elif sec_type == "pie_chart":
        render_pie_chart(section, sheet_idx, sec_idx)
    elif sec_type == "stacked_bar_chart":
        render_stacked_bar_chart(section, sheet_idx, sec_idx)
    elif sec_type == "separator":
        st.markdown("---")
        if st.button("➕ Add Divider to PDF", key=f"sep_{sheet_idx}_{sec_idx}"):
            add_text_to_pdf("\n----------------------------\n")
    else:
        st.warning(f"Unsupported section type: {sec_type}")


def render_sheet(sheet, sheet_idx):
    st.header(f"📄 {sanitize_text(sheet.get('header', f'Sheet {sheet_idx + 1}'))}")
    for sec_idx, section in enumerate(sheet.get("sections", [])):
        header = section.get("header")
        if header:
            st.subheader(sanitize_text(header))
        render_section(section, sheet_idx, sec_idx)


def render_report(data):
    report = data.get("report", {})
    st.title(sanitize_text(report.get("title", "Report")))
    st.markdown(f"**Created:** {sanitize_text(report.get('created'))}")
    st.markdown(f"**Report ID:** {sanitize_text(report.get('id'))}")
    tf = report.get("time_filter", {})
    st.markdown(f"**Time Filter:** {tf.get('from')} – {tf.get('to')} | Weekdays: {tf.get('weekdays')}")

    for i, sheet in enumerate(report.get("sheets", [])):
        render_sheet(sheet, i)

# ---------- Main ----------

def main():
    st.set_page_config(page_title="Report Viewer + PDF Export", layout="wide")

    if "pdf_contents" not in st.session_state:
        st.session_state.pdf_contents = []

    st.sidebar.title("📁 Upload JSON Report")
    uploaded_file = st.sidebar.file_uploader("Upload a JSON file", type="json")

    if uploaded_file:
        try:
            json_data = json.load(uploaded_file)
            render_report(json_data)

            if st.session_state.pdf_contents:
                pdf_data = generate_pdf()
                st.download_button("📥 Download PDF Report", pdf_data, file_name="report.pdf", mime="application/pdf")
        except Exception as e:
            st.error(f"Failed to parse JSON: {e}")
    else:
        st.info("Upload a report JSON file to begin.")

if __name__ == "__main__":
    main()
