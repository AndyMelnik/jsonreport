import streamlit as st
import pandas as pd
import json
import matplotlib.pyplot as plt


def render_table(section):
    for entry in section.get("data", []):
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
        st.dataframe(pd.DataFrame(table_data), use_container_width=True)


def render_map_table(section):
    rows = section.get("rows", [])
    data = {row["name"]: row["v"] for row in rows}
    st.dataframe(pd.DataFrame(data.items(), columns=["Metric", "Value"]), use_container_width=True)


def render_pie_chart(section):
    values = section.get("values", [])
    labels = [item["title"] for item in values]
    sizes = [item["raw"] for item in values]
    colors = [item.get("color") for item in values]

    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%", startangle=140)
    ax.axis("equal")
    st.pyplot(fig)


def render_stacked_bar_chart(section):
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


def render_section(section):
    section_type = section.get("type")
    if section_type == "table":
        render_table(section)
    elif section_type == "map_table":
        render_map_table(section)
    elif section_type == "pie_chart":
        render_pie_chart(section)
    elif section_type == "stacked_bar_chart":
        render_stacked_bar_chart(section)
    elif section_type == "separator":
        st.markdown("---")
    else:
        st.warning(f"Unsupported section type: {section_type}")


def render_sheet(sheet):
    st.header(f"📄 {sheet.get('header')}")
    for section in sheet.get("sections", []):
        if header := section.get("header"):
            st.subheader(header)
        render_section(section)


def render_report(data):
    report = data.get("report", {})
    st.title(report.get("title", "Report"))
    st.markdown(f"**Created:** {report.get('created')}")
    st.markdown(f"**Report ID:** {report.get('id')}")

    time_filter = report.get("time_filter", {})
    st.markdown(f"**Time Filter:** {time_filter.get('from')} – {time_filter.get('to')} | Weekdays: {time_filter.get('weekdays')}")

    for sheet in report.get("sheets", []):
        render_sheet(sheet)


def main():
    st.sidebar.title("📁 Upload JSON Report")
    uploaded_file = st.sidebar.file_uploader("Upload a JSON file", type=["json"])

    if uploaded_file is not None:
        try:
            json_data = json.load(uploaded_file)
            render_report(json_data)
        except Exception as e:
            st.error(f"Failed to parse JSON: {e}")
    else:
        st.info("Please upload a report JSON to begin.")


if __name__ == "__main__":
    main()
