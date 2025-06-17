from pathlib import Path
import streamlit as st
import pandas as pd
import json
from io import BytesIO
from fpdf import FPDF
import matplotlib.pyplot as plt
from PIL import Image

st.set_page_config(layout="wide")
st.title("📊 JSON Report Viewer & PDF Exporter")

# Helper: draw table as image
def render_table_as_image(df, title=None, scale=0.75):
    fig, ax = plt.subplots(figsize=(df.shape[1]*scale + 1, df.shape[0]*0.4 + 1))
    ax.axis('off')
    table = ax.table(cellText=df.values, colLabels=df.columns, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    fig.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return buf

# PDF helper
class PDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
        self.add_page()

    def add_image(self, img_data):
        self.image(img_data, x=10, w=190)

uploaded_file = st.file_uploader("📁 Upload your JSON report file", type="json")

if uploaded_file:
    try:
        report_json = json.load(uploaded_file)
        report = report_json.get("report", {})
        st.subheader(report.get("title", "Untitled Report"))
        selected_images = []

        for sheet_idx, sheet in enumerate(report.get("sheets", [])):
            st.markdown(f"## 📄 {sheet.get('header', 'Untitled Sheet')}")
            for sec_idx, section in enumerate(sheet.get("sections", [])):
                section_type = section.get("type")
                header = section.get("header", f"{section_type.title()} Section")
                include_key = f"include_{sheet_idx}_{sec_idx}"
                st.markdown(f"### {header}")

                if section_type == "table":
                    for rowset in section.get("data", []):
                        if isinstance(rowset, dict):
                            df_rows = rowset.get("rows", [])
                            if df_rows:
                                df = pd.DataFrame([{k: v['v'] if isinstance(v, dict) else v for k, v in row.items()} for row in df_rows])
                                st.dataframe(df, use_container_width=True)
                                if st.checkbox("Include in PDF", key=include_key):
                                    img = render_table_as_image(df, header)
                                    selected_images.append(img)

                elif section_type == "map_table":
                    rows = section.get("rows", [])
                    if rows:
                        df = pd.DataFrame([{k: v['v'] if isinstance(v, dict) else v for k, v in row.items()} for row in rows])
                        st.dataframe(df, use_container_width=True)
                        if st.checkbox("Include in PDF", key=include_key):
                            img = render_table_as_image(df, header)
                            selected_images.append(img)

                elif section_type == "pie_chart":
                    labels = [item["title"] for item in section.get("values", [])]
                    sizes = [item["raw"] for item in section.get("values", [])]
                    fig, ax = plt.subplots()
                    ax.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=90)
                    ax.axis("equal")
                    st.pyplot(fig)
                    if st.checkbox("Include in PDF", key=include_key):
                        buf = BytesIO()
                        fig.savefig(buf, format="png")
                        buf.seek(0)
                        selected_images.append(buf)
                        plt.close(fig)

                elif section_type == "stacked_bar_chart":
                    x_vals = [d["x"]["v"] for d in section["data"]]
                    series = section["series"]
                    bar_data = {s["title"]: [d["bars"][s["field"]]["raw"] for d in section["data"]] for s in series}
                    df = pd.DataFrame(bar_data, index=x_vals)
                    ax = df.plot(kind="bar", stacked=True, figsize=(8, 4))
                    plt.xlabel("Date")
                    plt.ylabel(section.get("y_axis", {}).get("label", "Value"))
                    plt.title(header)
                    st.pyplot(ax.figure)
                    if st.checkbox("Include in PDF", key=include_key):
                        buf = BytesIO()
                        ax.figure.savefig(buf, format="png")
                        buf.seek(0)
                        selected_images.append(buf)
                        plt.close(ax.figure)

        if selected_images:
            if st.button("📥 Download PDF"):
                pdf = PDF()
                for img in selected_images:
                    pdf.add_page()
                    img_path = Path("/tmp/visual.png")
                    with open(img_path, "wb") as f:
                        f.write(img.getbuffer())
                    pdf.add_image(str(img_path))
                pdf_buffer = BytesIO()
                pdf.output(pdf_buffer)
                pdf_buffer.seek(0)
                st.download_button("📄 Download PDF", data=pdf_buffer, file_name="report.pdf", mime="application/pdf")

    except Exception as e:
        st.error(f"❌ Failed to parse JSON: {e}")
