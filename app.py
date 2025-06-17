import streamlit as st
import pandas as pd
import json
import matplotlib.pyplot as plt
from fpdf import FPDF
from io import BytesIO
from PIL import Image

# ---------- Helpers ----------

def sanitize_text(text, encoding="latin-1", replacement="?"):
    if isinstance(text, str):
        return text.encode(encoding, errors="replace").decode(encoding).replace("�", replacement)
    return str(text)

# ---------- PDF Management ----------

def save_chart_as_image(fig):
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    return buf

def add_text_to_pdf(text):
    safe_text = sanitize_text(text)
    st.session_state.pdf_contents.append({"type": "text", "content": safe_text})

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
            temp_path = "/tmp/img.png"
            img.save(temp_path)
            pdf.image(temp_path, x=10, y=20, w=180)

    return pdf.output(dest="S").encode("latin-1", errors="replace")

# ---------- Section Renderers ----------

def render_table(section, sheet_idx, sec_idx):
    for entry_idx, entry in enumerate(section.get("data", [])):
        header = entry.get("header")
        rows = entry.get("rows", [])
        columns = section.get("columns", [])

        table_data = []
        for row in rows:
            table_data.append({
                (col["title"] or col["field"]): row.get(col["field"], {}).get("v", "")
                for col in columns
            })

        if header:
            st.markdown(f"**{sanitize_text(header)}**")
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True)

        if st.button("➕ Add Table to PDF", key=f"table_{sheet_idx}_{sec_idx}_{entry_idx}"):
            add_text_to_pdf(df.to_string(index=False))


def render_map_table(section, sheet_idx, sec_idx):
    df = pd.DataFrame([{r["name"]: r["v"]} for r in section.get("rows", [])])
    st.dataframe(df, use_container_width=True)
    if st.button("➕ Add Map Table to PDF", key=f"maptable_{sheet_idx}_{sec_idx}"):
        add_text_to_pdf(df.to_string(index=False))


def render_pie_chart(section, sheet_idx, sec_idx):
    values = section.get("values", [])
    labels = [v["title"] for v in values]
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
    x_labels = [item["x"]["v"] for item in data]
    bar_data = {
        s["field"]: [item["bars"][s["field"]]["raw"] for item in data] for s in series
    }
    df = pd.DataFrame(bar_data, index=x_labels)

    fig, ax = plt.subplots()
    bottom = None
    for i, s in enumerate(series):
        values = df[s["field"]]
        ax.bar(df.index, values, label=s["title"], color=s["color"], bottom=bottom)
        bottom = values if bottom is None else bottom + values

    ax.set_ylabel(section.get("y_axis", {}).get("label", ""))
    ax.set_title(section.get("header", "Stacked Bar Chart"))
    ax.legend()
    st.pyplot(fig)

    if st.button("➕ Add Stacked Bar Chart to PDF", key=f"stackbar_{sheet_idx}_{sec_idx}"):
        add_image_to_pdf(save_chart_as_image(fig))


def render_section(section, sheet_idx, sec_idx):
    t = section.get("type")
    if t == "table":
        render_table(section, sheet_idx, sec_idx)
    elif t == "map_table":
        render_map_table(section, sheet_idx, sec_idx)
    elif t == "pie_chart":
        render_pie_chart(section, sheet_idx, sec_idx)
    elif t == "stacked_bar_chart":
        render_stacked_bar_chart(section, sheet_idx, sec_idx)
    elif t == "separator":
        st.markdown("---")
        if st.button("➕ Add Divider to PDF", key=f"sep_{sheet_idx}_{sec_idx}"):
            add_text_to_pdf("\n----------------------------\n")
    else:
        st.warning(f"Unsupported section type: {t}")

def render_sheet(sheet, sheet_idx):
    st.header(f"📄 {sanitize_text(sheet.get('header'))}")
    for sec_idx, section in enumerate(sheet.get("sections", [])):
        if header := section.get("header"):
            st.subheader(sanitize_text(header))
        render_section(section, sheet_idx, sec_idx)

def render_report(data):
    rpt = data.get("report", {})
    st.title(sanitize_text(rpt.get("title", "Report")))
    st.markdown(f"**Created:** {sanitize_text(rpt.get('created'))}")
    st.markdown(f"**Report ID:** {sanitize_text(rpt.get('id'))}")
    tf = rpt.get("time_filter", {})
    st.markdown(f"**Time Filter:** {tf.get('from')} – {tf.get('to')} | Weekdays: {tf.get('weekdays')}")

    for i, sheet in enumerate(rpt.get("sheets", [])):
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
                pdf_bytes = generate_pdf()
                if pdf_bytes:
                    st.download_button("📥 Download PDF Report", pdf_bytes, file_name="report.pdf", mime="application/pdf")
        except Exception as e:
            st.error(f"Failed to parse JSON: {e}")
    else:
        st.info("Upload a report JSON file to begin.")

if __name__ == "__main__":
    main()
