#!/usr/bin/env python
import base64
import os
import json
from dash import Dash, dcc, html, Input, Output, State, no_update, dash_table
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import dash
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
 
# Chatbot icon
with open(r"C:\Users\excel\Downloads\Senior_Design_Dashboard_Attachies\Chat_Bot.png", "rb") as f:
    _b64 = base64.b64encode(f.read()).decode("utf-8")
chat_icon_src = f"data:image/png;base64,{_b64}"
 
# API Key and client initialization with Gooogle Gemini
from google import genai
client = genai.Client(api_key="") # ← your Gemini key here
 
 
###############################################################################
# GLOBAL STYLE DEFINITION
###############################################################################
global_style = {
    'fontFamily': '"Segoe UI", "Roboto", sans-serif',
    'color': '#2c3e50',
    'backgroundColor': '#f8fafc',
    'overflowX': 'hidden',
    'margin': '0',
    'padding': '0',
    'minHeight': '100vh'
}
 
###############################################################################
# 1) LOGO ENCODING
###############################################################################
logo_path = r"C:\Users\excel\Downloads\Senior_Design_Dashboard_Attachies\Aerospace-Logo.png"
encoded_image = None
if os.path.exists(logo_path):
    with open(logo_path, 'rb') as f:
        encoded_image = base64.b64encode(f.read()).decode('utf-8')
else:
    print(f"Warning: {logo_path} not found. The header image will not be displayed.")
###############################################################################
# 3) TABLE OF CONTENTS & SEARCH INDEX (Not used in this layout)
###############################################################################
search_index = [
    {"label": "Model Description", "href": "/#model-description"},
    {"label": "Dashboard", "href": "/dashboard"}
]
toc_structure = []
flat_toc_order = []
 
###############################################################################
# 4) REQUIREMENTS TABLE FROM HTML (WITH SUBTABLES)
###############################################################################
def parse_requirements_html(html_file_path):
    """
    Parse the requirements HTML file and return (scope_text, desc_text, df_reqs).
    If a cell has a nested <table>, we append the raw HTML of that sub-table to the cell text.
    """
    if not os.path.exists(html_file_path):
        print(f"Warning: {html_file_path} not found; using default requirements.")
        return "Default Scope Text", "Default Description Text", pd.DataFrame(columns=["ID", "Requirement"])
   
    with open(html_file_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
   
    scope_text = "Default Scope Text"
    desc_text = "Default Description Text"
    scope_header = soup.find(lambda tag: tag.name in ["h2", "h3"] and "Scope" in tag.get_text())
    if scope_header and scope_header.find_next_sibling():
        scope_text = scope_header.find_next_sibling().get_text(strip=True)
    desc_header = soup.find(lambda tag: tag.name in ["h2", "h3"] and "Description" in tag.get_text())
    if desc_header and desc_header.find_next_sibling():
        desc_text = desc_header.find_next_sibling().get_text(strip=True)
   
    table = soup.find("table")
    if not table:
        print("No table found in the requirements HTML.")
        return scope_text, desc_text, pd.DataFrame(columns=["ID", "Requirement"])
   
    rows = table.find_all("tr")
    if not rows:
        return scope_text, desc_text, pd.DataFrame(columns=["ID", "Requirement"])
   
    header_cells = [cell.get_text(strip=True) for cell in rows[0].find_all(["th","td"])]
    data_list = []
    for row in rows[1:]:
        cells = row.find_all(["th","td"])
        row_vals = []
        for cell in cells:
            sub_table = cell.find("table")
            if sub_table:
                raw_sub_html = str(sub_table)
                sub_table.decompose()
                cell_text = cell.get_text(strip=True)
                combined = cell_text + "\n" + raw_sub_html
                row_vals.append(combined)
            else:
                row_vals.append(cell.get_text(strip=True))
        if len(row_vals) < len(header_cells):
            row_vals += [""] * (len(header_cells) - len(row_vals))
        row_vals = row_vals[:len(header_cells)]
        data_list.append(row_vals)
    df_reqs = pd.DataFrame(data_list, columns=header_cells)
   
    try:
        row_scope = df_reqs[df_reqs["Name"].str.lower() == "scope"]
        if not row_scope.empty and "Text" in df_reqs.columns:
            scope_text = row_scope["Text"].iloc[0]
    except Exception:
        pass
 
    try:
        row_general = df_reqs[df_reqs["Name"].str.lower() == "mpm general description"]
        if not row_general.empty and "Text" in df_reqs.columns:
            desc_text = row_general["Text"].iloc[0]
    except Exception:
        pass
 
    return scope_text, desc_text, df_reqs
 
requirements_html_path = r"C:\Users\excel\Downloads\Senior_Design_Dashboard_Attachies\reqtrypart2.html"
html_scope, html_desc, df_html_reqs = parse_requirements_html(requirements_html_path)
scope_text = html_scope
desc_text = html_desc
df_csv = df_html_reqs
 
###############################################################################
# 5B) (Optional CSV Fallback if needed) ...
###############################################################################
 
###############################################################################
# 6) LOAD AND PROCESS DIAGRAM HIERARCHY JSON
###############################################################################
json_file_path = r"C:\Users\excel\Downloads\Senior_Design_Dashboard_Attachies\DiagramUsageReport_Enhanced41526part1234.json"
if os.path.exists(json_file_path):
    with open(json_file_path, 'r') as f:
        diagram_report = json.load(f)
else:
    diagram_report = []
    print(f"Warning: {json_file_path} not found. The diagram hierarchy table will be empty.")
 
###############################################################################
# 7) HELPER FUNCTIONS FOR DIAGRAMS
###############################################################################
def build_name_to_id_map_by_name(items, name_to_id=None):
    if name_to_id is None:
        name_to_id = {}
    for it in items:
        raw_id = it.get("id", "")
        raw_name = it.get("name", it.get("element_name", ""))
        type_val = it.get("type", it.get("element_type", "").lower())
        image_val = it.get("image", "").lower()
        if raw_id and (("diagram" in type_val) or image_val.endswith(".png")):
            name_to_id[raw_name] = raw_id
        if "children" in it and it["children"]:
            build_name_to_id_map_by_name(it["children"], name_to_id)
    return name_to_id
 
name_to_id_by_name = build_name_to_id_map_by_name(diagram_report)
 
def find_item_by_name(search_name, items):
    for it in items:
        if it.get("name", "").strip().lower() == search_name.strip().lower():
            return it
        if "children" in it and it["children"]:
            res = find_item_by_name(search_name, it["children"])
            if res:
                return res
    return None
 
def process_item(item):
    rows = []
    raw_id = item.get("id", "")
    raw_name = item.get("name", item.get("element_name", ""))
    type_val = item.get("type", item.get("element_type", ""))
 
    path_str = item.get("profile", "")
    if not path_str:
        path_str = item.get("path", "")
    if path_str:
        path_str = path_str.replace(u"\u2192", " --> ")
 
    if raw_id and (("diagram" in type_val.lower()) or item.get("image", "").lower().endswith(".png")):
        name_val = html.A(raw_name, href=f"/diagram/{raw_id}",
                          style={"color": "blue", "textDecoration": "underline"})
    else:
        name_val = raw_name
    shown_dict = item.get("elements_shown", {})
    elements_shown_str = ", ".join([f"{k}: {v}" for k, v in shown_dict.items()]) if shown_dict else ""
   
    nested_list_components = []
    if "Diagram" in type_val and "element_details" in item:
        nested_names = [d.get("name", "") for d in item["element_details"] if "diagram" in d.get("type", "").lower()]
        for idx, diag_name in enumerate(nested_names):
            if diag_name in name_to_id_by_name:
                diag_id = name_to_id_by_name[diag_name]
                link_comp = html.A(diag_name, href=f"/diagram/{diag_id}",
                                   style={"color": "blue", "textDecoration": "underline"})
                nested_list_components.append(link_comp)
            else:
                nested_list_components.append(diag_name)
            if idx < len(nested_names) - 1:
                nested_list_components.append(", ")
    nested_list = nested_list_components if nested_list_components else ""
   
    used_in_list = []
    if "used_in" in item and isinstance(item["used_in"], list):
        used_in_list = [u.get("name", "") for u in item["used_in"]]
    used_in_str = ", ".join(used_in_list)
   
    row_data = {
        "Name": name_val,
        "Type": type_val,
        "Path": path_str,
        "Elements Shown": elements_shown_str,
        "Nested Diagrams": nested_list,
        "Used In": used_in_str
    }
    rows.append(row_data)
    if "children" in item and item["children"]:
        for child_item in item["children"]:
            rows.extend(process_item(child_item))
    return rows
 
def generate_html_table_from_df(df):
    header = html.Tr([
        html.Th(col, style={
            "border": "1px solid #e1e8ed",
            "padding": "16px",
            "backgroundColor": "#2c3e50",
            "color": "white",
            "fontSize": "15px",
            "fontWeight": "600",
            "letterSpacing": "0.3px"
        }) for col in df.columns
    ])
   
    table_rows = []
    for idx, row in df.iterrows():
        cells = []
        for col in df.columns:
            cell_val = row[col]
            cell_style = {
                "border": "1px solid #e1e8ed",
                "padding": "14px 16px",
                "fontSize": "14px",
                "color": "#2c3e50",
                "backgroundColor": "#ffffff" if idx % 2 == 0 else "#f8fafc",
                "transition": "background-color 0.2s ease"
            }
           
            if isinstance(cell_val, (str, int, float)):
                cell = html.Td(str(cell_val), style=cell_style)
            else:
                if isinstance(cell_val, html.A):
                    cell_val.style = {
                        "color": "#3498db",
                        "textDecoration": "none",
                        "fontWeight": "500",
                        "transition": "color 0.2s ease",
                        ":hover": {
                            "color": "#2980b9",
                            "textDecoration": "underline"
                        }
                    }
                cell = html.Td(cell_val, style=cell_style)
            cells.append(cell)
        table_rows.append(html.Tr(cells))
   
    return html.Table(
        [html.Thead(header), html.Tbody(table_rows)],
        style={
            "width": "100%",
            "borderCollapse": "separate",
            "borderSpacing": "0",
            "borderRadius": "8px",
            "overflow": "hidden",
            "backgroundColor": "white",
            "boxShadow": "0 4px 6px rgba(0, 0, 0, 0.05), 0 1px 3px rgba(0, 0, 0, 0.1)",
            "fontFamily": '"Segoe UI", "Roboto", sans-serif'
        }
    )
 
all_rows = []
for top_item in diagram_report:
    all_rows.extend(process_item(top_item))
 
df_diagram_hierarchy = pd.DataFrame(
    all_rows,
    columns=["Name", "Type", "Path", "Elements Shown", "Nested Diagrams", "Used In"]
)
diagram_hierarchy_table_html = generate_html_table_from_df(df_diagram_hierarchy)
 
def override_link_white(comp):
    if hasattr(comp, "props") and "href" in comp.props:
        return html.A(comp.props["children"], href=comp.props["href"],
                      style={"color": "white", "textDecoration": "underline"})
    return comp

def build_diagram_sidebar_from_table(df):
    sidebar_items = []
    sidebar_items.append(html.H3("Diagram Types", style={
        "color": "white",
        "marginBottom": "15px",
        "marginLeft": "15px",  # Reverted to previous value
        "paddingLeft": "35px"  # Reverted to previous value
    }))
    all_types = df["Type"].unique()
    for diag_type in all_types:
        group = df[df["Type"] == diag_type]
        li_list = []
        for _, row in group.iterrows():
            li_list.append(html.Li(
                override_link_white(row["Name"]),
                style={
                    "marginLeft": "15px",  # Reverted to previous value
                    "paddingLeft": "45px",  # Reverted to previous value
                    "listStyleType": "none",
                    "padding": "5px"
                }
            ))
        sidebar_items.append(html.Details([
            html.Summary(diag_type, style={
                "cursor": "pointer",
                "fontSize": "16px",
                "marginBottom": "5px",
                "color": "white",
                "marginLeft": "15px",  # Reverted to previous value
                "paddingLeft": "35px"  # Reverted to previous value
            }),
            html.Ul(li_list, style={
                "padding": "0",
                "margin": "0",
                "marginLeft": "15px",  # Reverted to previous value
                "paddingLeft": "35px"  # Reverted to previous value
            })
        ], open=False))
    return sidebar_items
 
sidebar_diagram_content = build_diagram_sidebar_from_table(df_diagram_hierarchy)
 
def find_item_by_name(search_name, items):
    for it in items:
        if it.get("name", "").strip().lower() == search_name.strip().lower():
            return it
        if "children" in it and it["children"]:
            res = find_item_by_name(search_name, it["children"])
            if res:
                return res
    return None
 
images_base_dir = r"C:\Users\excel\Desktop\DiagramExport_Enhanced_20250420_181358\images"
model_nav_item = find_item_by_name("Model Navigation", diagram_report)
if model_nav_item and "image" in model_nav_item:
    nav_img_filename = os.path.basename(model_nav_item["image"])
    model_nav_image_path = os.path.join(images_base_dir, nav_img_filename)
    if os.path.exists(model_nav_image_path):
        with open(model_nav_image_path, 'rb') as f:
            nav_encoded = base64.b64encode(f.read()).decode('utf-8')
        model_nav_img_src = f"data:image/png;base64,{nav_encoded}"
    else:
        print(f"Warning: {model_nav_image_path} not found. Model Navigation image will not be displayed.")
        model_nav_img_src = ""
    nested_links = []
    if "element_details" in model_nav_item and model_nav_item["element_details"]:
        nested_names = [d.get("name", "") for d in model_nav_item["element_details"] if "diagram" in d.get("type", "").lower()]
        for idx, diag_name in enumerate(nested_names):
            if diag_name in name_to_id_by_name:
                diag_id = name_to_id_by_name[diag_name]
                link = html.A(diag_name, href=f"/diagram/{diag_id}",
                              style={"color": "blue", "textDecoration": "underline"})
                nested_links.append(link)
            else:
                nested_links.append(diag_name)
            if idx < len(nested_names) - 1:
                nested_links.append(", ")
    else:
        nested_links = []
else:
    model_nav_img_src = ""
    nested_links = []
 
model_nav_section = html.Div([
    html.H2("Model Navigation", style={'marginBottom': '10px', 'textAlign': 'center'}),
    html.Img(src=model_nav_img_src,
             style={"maxWidth": "100%", "height": "auto", "display": "block", "margin": "0 auto"}),
    html.Div([
         html.H3("Nested Diagrams", style={"textAlign": "center", "marginTop": "10px"}),
         html.Div(nested_links, style={"textAlign": "center"})
    ])
], style={"marginTop": "20px", "width": "100%", "marginLeft": "auto", "marginRight": "auto"})
 
def build_name_map(items):
    mapping = {}
    for it in items:
        rid = it.get("id", "")
        nm = it.get("name", it.get("element_name", ""))
        if rid:
            mapping[rid] = nm
        if "children" in it and it["children"]:
            mapping.update(build_name_map(it["children"]))
    return mapping
 
diagram_name_map = build_name_map(diagram_report)

def generate_elements_shown_table(elements_shown_dict):
    header = html.Tr([
        html.Th("Element", style={"border": "1px solid black", "padding": "8px"}),
        html.Th("Count", style={"border": "1px solid black", "padding": "8px"})
    ])
    rows = []
    for k, v in elements_shown_dict.items():
        rows.append(html.Tr([
            html.Td(k, style={"border": "1px solid black", "padding": "8px"}),
            html.Td(str(v), style={"border": "1px solid black", "padding": "8px"})
        ]))
    return html.Table([html.Thead(header), html.Tbody(rows)],
                      style={"width": "100%", "borderCollapse": "collapse"})
 
def generate_element_details_table(details_list):
    header = html.Tr([
        html.Th("Type", style={"border": "1px solid black", "padding": "8px"}),
        html.Th("Name", style={"border": "1px solid black", "padding": "8px"}),
        html.Th("Image", style={"border": "1px solid black", "padding": "8px"})
    ])
    rows = []
    element_images_dir = r"C:\Users\excel\Desktop\DiagramExport_Enhanced_20250420_181358\element_images"
    for detail in details_list:
        image_filename = os.path.basename(detail.get("image", ""))
        element_image_path = os.path.join(element_images_dir, image_filename)
        if os.path.exists(element_image_path):
            with open(element_image_path, 'rb') as f:
                encoded_img = base64.b64encode(f.read()).decode('utf-8')
            img_tag = html.Img(src=f"data:image/png;base64,{encoded_img}",
                               style={"maxWidth": "100px", "height": "auto"})
        else:
            img_tag = "Image not found"
        rows.append(html.Tr([
            html.Td(detail.get("type", ""), style={"border": "1px solid black", "padding": "8px"}),
            html.Td(detail.get("name", ""), style={"border": "1px solid black", "padding": "8px"}),
            html.Td(img_tag, style={"border": "1px solid black", "padding": "8px"})
        ]))
    return html.Table([html.Thead(header), html.Tbody(rows)],
                      style={"width": "100%", "borderCollapse": "collapse"})
 
# New helper function to layout the extra diagram details
def extra_diagram_layout(diagram_id):
    images_base_dir = r"C:\Users\excel\Desktop\DiagramExport_Enhanced_20250420_181358\images"
    file_path = os.path.join(images_base_dir, diagram_id + ".png")
    if os.path.exists(file_path):
        with open(file_path, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode('utf-8')
        img_src = f"data:image/png;base64,{encoded}"
    else:
        img_src = ""
    displayed_name = diagram_name_map.get(diagram_id, diagram_id)

    def find_diagram_item(diagram_id, items):
        for it in items:
            if it.get("id") == diagram_id:
                return it
            if "children" in it and it["children"]:
                found = find_diagram_item(diagram_id, it["children"])
                if found:
                    return found
        return None

    item = find_diagram_item(diagram_id, diagram_report)
    details_div = html.Div()
    if item is not None:
        elements_table = None
        if "elements_shown" in item and item["elements_shown"]:
            elements_table = generate_elements_shown_table(item["elements_shown"])
        details_table = None
        if "element_details" in item and item["element_details"]:
            details_table = generate_element_details_table(item["element_details"])
        details_div = html.Div([
            html.H4("Elements Shown", style={
                "textAlign": "center",
                "marginTop": "25px",
                "color": "#2c3e50",
                "fontSize": "18px",
                "fontWeight": "600",
                "letterSpacing": "0.3px"
            }),
            elements_table if elements_table else html.Div("No elements shown data."),
            html.H4("Element Details", style={
                "textAlign": "center",
                "marginTop": "25px",
                "color": "#2c3e50",
                "fontSize": "18px",
                "fontWeight": "600",
                "letterSpacing": "0.3px"
            }),
            details_table if details_table else html.Div("No element details data.")
        ], style={
            "marginTop": "25px",
            "padding": "20px",
            "backgroundColor": "white",
            "borderRadius": "8px",
            "boxShadow": "0 2px 8px rgba(0,0,0,0.05)"
        })

    return html.Div([
        html.H3(
            f"Extra Diagram: {displayed_name}",
            style={
                "textAlign": "center",
                "color": "#2c3e50",
                "fontSize": "20px",
                "fontWeight": "600",
                "marginBottom": "20px",
                "letterSpacing": "0.3px"
            }
        ),
        html.Div(
            html.Img(
                src=img_src,
                style={
                    "maxWidth": "100%",
                    "height": "auto",
                    "display": "block",
                    "margin": "0 auto",
                    "borderRadius": "8px",
                    "boxShadow": "0 2px 8px rgba(0,0,0,0.1)"
                }
            ),
            style={
                "backgroundColor": "#f8fafc",
                "padding": "20px",
                "borderRadius": "8px",
                "marginBottom": "20px"
            }
        ),
        details_div
    ], style={
        "backgroundColor": "white",
        "borderRadius": "8px",
        "padding": "20px",
        "boxShadow": "0 2px 8px rgba(0,0,0,0.05)",
        "height": "fit-content"
    })
 
# Modified diagram_page_layout with extra diagram dropdown placed next to main diagram
def diagram_page_layout(diagram_id):
    images_base_dir = r"C:\Users\excel\Desktop\DiagramExport_Enhanced_20250420_181358\images"
    file_path = os.path.join(images_base_dir, diagram_id + ".png")
    if os.path.exists(file_path):
        with open(file_path, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode('utf-8')
        img_src = f"data:image/png;base64,{encoded}"
    else:
        img_src = ""
    displayed_name = diagram_name_map.get(diagram_id, diagram_id)

    def find_diagram_item(diagram_id, items):
        for it in items:
            if it.get("id") == diagram_id:
                return it
            if "children" in it and it["children"]:
                found = find_diagram_item(diagram_id, it["children"])
                if found:
                    return found
        return None

    item = find_diagram_item(diagram_id, diagram_report)
    details_div = html.Div()
    if item:
        elements_table = generate_elements_shown_table(item["elements_shown"]) if "elements_shown" in item else None
        details_table = generate_element_details_table(item["element_details"]) if "element_details" in item else None
        details_div = html.Div([
            html.H3("Elements Shown", style={
                "textAlign": "center",
                "marginTop": "30px",
                "color": "#2c3e50",
                "fontSize": "20px",
                "fontWeight": "600",
                "letterSpacing": "0.3px"
            }),
            elements_table if elements_table else html.Div("No elements shown data."),
            html.H3("Element Details", style={
                "textAlign": "center",
                "marginTop": "30px",
                "color": "#2c3e50",
                "fontSize": "20px",
                "fontWeight": "600",
                "letterSpacing": "0.3px"
            }),
            details_table if details_table else html.Div("No element details data.")
        ], style={
            "marginTop": "40px",
            "padding": "20px",
            "backgroundColor": "white",
            "borderRadius": "8px",
            "boxShadow": "0 2px 8px rgba(0,0,0,0.05)"
        })

    # Panel styling with improved aesthetics
    panel_style = {
        "width": "48%",
        "minWidth": "600px",
        "backgroundColor": "white",
        "borderRadius": "12px",
        "boxShadow": "0 4px 12px rgba(0,0,0,0.08)",
        "padding": "25px",
        "transition": "all 0.3s ease",
        "height": "fit-content"
    }

    # Improved dropdown styling
    extra_dropdown = dcc.Dropdown(
        id="extra-diagram-dropdown",
        options=[{"label": v, "value": k} for k, v in diagram_name_map.items()],
        placeholder="Select diagram to compare...",
        searchable=True,
        style={
            "width": "100%",
            "marginBottom": "20px",
            "borderRadius": "6px",
            "border": "1px solid #e1e8ed",
            "boxShadow": "0 2px 4px rgba(0,0,0,0.05)"
        }
    )

    # Container for the extra diagram
    extra_container = html.Div(
        id="extra-diagram-container",
        style={
            "marginTop": "20px",
            "minHeight": "200px"
        }
    )

    # Main diagram panel with enhanced styling
    main_diagram_div = html.Div([
        html.H2(
            f"Diagram: {displayed_name}",
            style={
                "textAlign": "center",
                "color": "#2c3e50",
                "fontSize": "24px",
                "fontWeight": "600",
                "marginBottom": "25px",
                "letterSpacing": "0.3px"
            }
        ),
        html.Div(
            html.Img(
                src=img_src,
                style={
                    "maxWidth": "100%",
                    "height": "auto",
                    "display": "block",
                    "margin": "0 auto",
                    "borderRadius": "8px",
                    "boxShadow": "0 2px 8px rgba(0,0,0,0.1)"
                }
            ),
            style={
                "backgroundColor": "#f8fafc",
                "padding": "20px",
                "borderRadius": "8px",
                "marginBottom": "20px"
            }
        ),
        details_div
    ], style=panel_style)

    # Extra diagram panel with matching styling
    extra_diagram_div = html.Div([
        html.H3(
            "Compare with Extra Diagram",
            style={
                "textAlign": "center",
                "color": "#2c3e50",
                "fontSize": "22px",
                "fontWeight": "600",
                "marginBottom": "25px",
                "letterSpacing": "0.3px"
            }
        ),
        extra_dropdown,
        extra_container
    ], style=panel_style)

    # Container for both panels with improved layout
    content_container = html.Div([
        html.Div(
            [main_diagram_div, extra_diagram_div],
            style={
                "display": "flex",
                "justifyContent": "center",
                "alignItems": "flex-start",
                "gap": "30px",
                "padding": "20px",
                "maxWidth": "100%",
                "margin": "0 auto",
                "overflowX": "auto",
                "minWidth": "1250px"
            }
        )
    ], style={
        "backgroundColor": "#f8fafc",
        "minHeight": "calc(100vh - 70px)",
        "paddingTop": "90px",
        "paddingBottom": "40px",
        "overflowX": "auto"
    })

    return html.Div([
        build_blue_header(back_href="/dashboard", enter_href="/enter"),
        content_container
    ])

def toc_page_layout(title):
    return html.Div([
        html.H1(f"TOC Page: {title}", style={'textAlign': 'center', 'marginBottom': '20px'}),
        html.P("Placeholder for Table of Contents page.", style={'textAlign': 'center'})
    ], style=global_style)
diagram_counts_by_type = df_diagram_hierarchy['Type'].value_counts().to_dict()
total_diagram_count = sum(diagram_counts_by_type.values())
 
diagram_counts_by_type = df_diagram_hierarchy['Type'].value_counts().to_dict()
total_diagram_count = sum(diagram_counts_by_type.values())
 
def generate_diagram_counter(df):
    diagram_counts = df["Type"].value_counts().to_dict()
    total_count = sum(diagram_counts.values())
 
    # Optional icons per type (placeholder bar chart)
    icon_map = {
        "Content Diagram": "📊",
        "Glossary Table": "📚",
        "Generic Table": "📝",
        "Activity Diagram": "🔄",
        "SysML Sequence Diagram": "🔁",
        "SysML State Machine Diagram": "🎛️",
        "SysML Activity Diagram": "🏃",
        "SysML Internal Block Diagram": "📦",
        "SysML Block Definition Diagram": "🧱",
        "SysML Parametric Diagram": "📐",
        "User Interface Modeling Diagram": "🖥️",
        "Simulation Configuration Diagram": "🧪",
        "Profile Diagram": "👤",
        "Requirement Table": "✅",
        "SysML Use Case Diagram": "📎",
        "SysML Package Diagram": "📂",
        "Model": "🧩"
    }
 
    diagram_tiles = [
        html.Div([
            html.Span(icon_map.get(diag_type, "📈"), style={"fontSize": "24px", "marginRight": "12px"}),
            html.Span(f"{diag_type}:", style={"fontWeight": "500", "color": "#2c3e50"}),
            html.Span(f"{count}", style={"fontWeight": "600", "color": "#3498db", "marginLeft": "8px"})
        ], style={
            "padding": "16px 24px",
            "margin": "8px",
            "border": "1px solid #e1e8ed",
            "borderRadius": "12px",
            "backgroundColor": "white",
            "boxShadow": "0 2px 8px rgba(0,0,0,0.05)",
            "display": "flex",
            "alignItems": "center",
            "transition": "transform 0.2s ease, box-shadow 0.2s ease",
            "fontSize": "15px",
            ":hover": {
                "transform": "translateY(-2px)",
                "boxShadow": "0 4px 12px rgba(0,0,0,0.1)"
            }
        }) for diag_type, count in diagram_counts.items()
    ]
 
    diagram_tiles.append(
        html.Div([
            html.Span("🧮", style={"fontSize": "24px", "marginRight": "12px"}),
            html.Span("Total Diagrams:", style={"fontWeight": "600", "color": "#2c3e50"}),
            html.Span(f"{total_count}", style={"fontWeight": "bold", "color": "#3498db", "marginLeft": "8px", "fontSize": "18px"})
        ], style={
            "padding": "20px 30px",
            "margin": "12px",
            "border": "2px solid #3498db",
            "borderRadius": "12px",
            "backgroundColor": "white",
            "boxShadow": "0 4px 12px rgba(52, 152, 219, 0.15)",
            "display": "flex",
            "alignItems": "center",
            "fontSize": "16px"
        })
    )
 
    return html.Div([
        html.H2("Model Summary", style={
            "textAlign": "center",
            "marginBottom": "30px",
            "color": "#2c3e50",
            "fontSize": "28px",
            "fontWeight": "600",
            "letterSpacing": "0.5px"
        }),
        html.Div(diagram_tiles, style={
            "display": "flex",
            "flexWrap": "wrap",
            "justifyContent": "center",
            "gap": "16px"
        })
    ], style={
        "padding": "40px",
        "borderRadius": "16px",
        "backgroundColor": "#f8fafc",
        "boxShadow": "0 4px 20px rgba(0,0,0,0.05)",
        "width": "95%",
        "margin": "40px auto"
    })
 
 
 
# ADDED REQUIREMENTS APPROVAL FEATURE:
page2_layout = html.Div([
    html.Div([
        html.H1("MPM Dashboard", style={
            'marginBottom': '30px',
            'textAlign': 'center',
            'color': '#2c3e50',
            'fontSize': '32px',
            'fontWeight': '600',
            'letterSpacing': '0.5px'
        }),

        # Add Model Title Section
        html.Div([
            html.H2("MOSA Payload Manager (MPM)", style={
                "textAlign": "center",
                "color": "#2c3e50",
                "fontSize": "28px",
                "fontWeight": "600",
                "marginBottom": "30px",
                "letterSpacing": "0.5px",
                "borderBottom": "3px solid #3498db",
                "paddingBottom": "15px",
                "width": "fit-content",
                "margin": "0 auto 40px"
            })
        ]),

        html.Div([
            html.Div([
                html.H2("Description", style={
                    "borderBottom": "2px solid #3498db",
                    "paddingBottom": "10px",
                    "color": "#2c3e50",
                    "fontSize": "24px",
                    "fontWeight": "600"
                }),
                html.Div(desc_text, style={
                    "whiteSpace": "pre-wrap",
                    "marginBottom": "20px",
                    "lineHeight": "1.8",
                    "textAlign": "left",
                    "color": "#34495e",
                    "padding": "20px",
                    "backgroundColor": "white",
                    "borderRadius": "8px",
                    "boxShadow": "0 2px 8px rgba(0,0,0,0.05)"
                })
            ], style={"flex": "1", "marginRight": "20px"}),
            html.Div([
                html.H2("Scope", style={
                    "borderBottom": "2px solid #3498db",
                    "paddingBottom": "10px",
                    "color": "#2c3e50",
                    "fontSize": "24px",
                    "fontWeight": "600"
                }),
                html.Div(scope_text, style={
                    "whiteSpace": "pre-wrap",
                    "marginBottom": "20px",
                    "lineHeight": "1.8",
                    "textAlign": "left",
                    "color": "#34495e",
                    "padding": "20px",
                    "backgroundColor": "white",
                    "borderRadius": "8px",
                    "boxShadow": "0 2px 8px rgba(0,0,0,0.05)"
                })
            ], style={"flex": "1", "marginLeft": "20px"})
        ], style={
            "display": "flex",
            "marginBottom": "40px",
            "flexWrap": "wrap",
            "justifyContent": "center",
            "gap": "30px"
        }),

        generate_diagram_counter(df_diagram_hierarchy),
        model_nav_section,

        # Requirements Table Section
        html.Div([
            html.H2("Requirements Table", style={
                'marginTop': '40px',
                'marginBottom': '20px',
                'textAlign': 'center',
                'color': '#2c3e50',
                'fontSize': '28px',
                'fontWeight': '600'
            }),
            html.Div([
                html.Div("Approval Progress", style={
                    "fontWeight": "600",
                    "marginRight": "20px",
                    "color": "#2c3e50",
                    "fontSize": "16px"
                }),
                html.Div(id="progress-text", style={
                    "marginRight": "20px",
                    "color": "#3498db",
                    "fontWeight": "500"
                }),
                html.Progress(id="progress-bar", value="0", max="100", style={
                    "width": "200px",
                    "height": "12px",
                    "marginRight": "20px",
                    "borderRadius": "6px",
                    "::-webkit-progress-bar": {
                        "backgroundColor": "#f0f3f6",
                        "borderRadius": "6px"
                    },
                    "::-webkit-progress-value": {
                        "backgroundColor": "#3498db",
                        "borderRadius": "6px"
                    }
                })
            ], style={
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "padding": "20px",
                "margin": "0 auto 30px",
                "width": "fit-content",
                "backgroundColor": "white",
                "borderRadius": "12px",
                "boxShadow": "0 2px 12px rgba(0,0,0,0.08)"
            }),

            # Search Input
            dcc.Input(
                id='requirements-search',
                type='text',
                placeholder='Search Requirements...',
                style={
                    'marginBottom': '20px',
                    'padding': '12px 16px',
                    'width': '300px',
                    'borderRadius': '8px',
                    'border': '1px solid #e1e8ed',
                    'fontSize': '14px',
                    'boxShadow': '0 2px 6px rgba(0,0,0,0.05)',
                    ':focus': {
                        'outline': 'none',
                        'borderColor': '#3498db',
                        'boxShadow': '0 0 0 3px rgba(52, 152, 219, 0.2)'
                    }
                }
            ),

            # Requirements DataTable
            dash_table.DataTable(
                id='requirements-table',
                columns=[{"name": col, "id": col, "presentation": "markdown"} for col in df_csv.columns],
                data=df_csv.to_dict('records'),
                row_selectable="multi",
                page_action='none',
                style_table={
                    'overflowX': 'auto',
                    'overflowY': 'auto',
                    'maxHeight': '700px',
                    'width': '100%',
                    'minWidth': '1200px',
                    'borderRadius': '12px',
                    'boxShadow': '0 4px 16px rgba(0,0,0,0.08)'
                },
                style_cell={
                    'whiteSpace': 'pre-line',
                    'textAlign': 'left',
                    'padding': '16px',
                    'fontFamily': '"Segoe UI", "Roboto", sans-serif',
                    'fontSize': '14px',
                    'color': '#2c3e50'
                },
                style_header={
                    'backgroundColor': '#2c3e50',
                    'color': 'white',
                    'fontWeight': '600',
                    'textAlign': 'left',
                    'padding': '16px'
                },
                style_data={
                    'backgroundColor': 'white',
                    'borderBottom': '1px solid #e1e8ed'
                },
                style_data_conditional=[{
                    'if': {'row_index': 'odd'},
                    'backgroundColor': '#f8fafc'
                }],
                markdown_options={"html": True},
            )
        ], style={"marginBottom": "40px"}),

        # Diagram Hierarchy Table
        html.Div([
            html.H2("Diagram Hierarchy", style={
                'marginBottom': '20px',
                'textAlign': 'center',
                'color': '#2c3e50',
                'fontSize': '28px',
                'fontWeight': '600'
            }),
            html.Div(
                diagram_hierarchy_table_html,
                style={
                    "backgroundColor": "white",
                    "borderRadius": "12px",
                    "boxShadow": "0 4px 16px rgba(0,0,0,0.08)",
                    "padding": "24px",
                    "overflowX": "auto"
                }
            )
        ], style={
            "marginTop": "40px",
            "width": "100%",
            "marginLeft": "auto",
            "marginRight": "auto"
        })
    ], id="main-container", style={
        "maxWidth": "1400px",
        "margin": "0 auto",
        "padding": "40px 20px 80px",
        "textAlign": "center"
    })
], style=global_style)
# END ADDED REQUIREMENTS APPROVAL FEATURE
 
sidebar_style_closed = {
    "position": "fixed",
    "top": "0",
    "left": "-265px",
    "width": "250px",
    "height": "100%",
    "backgroundColor": "#2c3e50",
    "color": "white",
    "overflowY": "auto",
    "overflowX": "hidden",
    "transition": "left 0.3s ease",
    "zIndex": "2000",
    "padding": "20px",
    "boxShadow": "2px 0 10px rgba(0,0,0,0.1)"
}

sidebar_style_open = {
    **sidebar_style_closed,
    "left": "0"
}

toggle_button_style_closed = {
    "position": "fixed",
    "top": "50%",
    "left": "5px",  # Half the button (40px/2) overlapping the edge
    "transform": "translateY(-80%)",
    "width": "40px",
    "height": "40px",
    "borderRadius": "50%",
    "backgroundColor": "#2c3e50",
    "color": "white",
    "textAlign": "center",
    "lineHeight": "40px",
    "cursor": "pointer",
    "zIndex": "2100",
    "boxShadow": "2px 0 8px rgba(0,0,0,0.2)",
    "transition": "all 0.3s ease"
}

toggle_button_style_open = {
    **toggle_button_style_closed,
    "left": "268px"  # Place it right at the edge of the sidebar when open
}

header_style = {
    'background': 'linear-gradient(135deg, #2c3e50, #3498db)',
    'height': '70px',
    'width': '100%',
    'display': 'flex',
    'justifyContent': 'space-between',
    'alignItems': 'center',
    'padding': '0 2rem',
    'position': 'fixed',
    'top': '0',
    'zIndex': '1000',
    'boxShadow': '0 2px 10px rgba(0,0,0,0.1)'
}
button_style = {
    "padding": "10px 20px",
    "fontSize": "15px",
    "border": "none",
    "borderRadius": "6px",
    "backgroundColor": "rgba(255, 255, 255, 0.9)",
    "color": "#2c3e50",
    "cursor": "pointer",
    "transition": "all 0.3s ease",
    "marginRight": "12px",
    "boxShadow": "0 2px 6px rgba(0,0,0,0.1)",
    "fontWeight": "500",
    "letterSpacing": "0.3px"
}
def build_blue_header(back_href="/dashboard", enter_href="/enter"):
    left_buttons = html.Div([
        dcc.Link(html.Button("Help", style=button_style), href="/help"),
        dcc.Link(html.Button("Dashboard", style=button_style), href="/dashboard")
    ], id="header-left", style={'display': 'flex', 'alignItems': 'center'})
    if encoded_image:
        center_col = html.Div(
            html.Img(src=f"data:image/png;base64,{encoded_image}",
                     style={'height': '50px', 'objectFit': 'contain'}),
            style={'textAlign': 'center'}
        )
    else:
        center_col = html.Div(
            html.H3("Aerospace Logo Missing", style={'color': 'white','margin':'0'}),
            style={'textAlign': 'center'}
        )
    right_col = html.Div(
        dcc.Dropdown(
            id='search-results-dropdown',
            options=[{'label': item['label'], 'value': item['href']} for item in search_index],
            placeholder="Search...",
            style={'width': '200px','borderRadius':'5px','padding':'5px'}
        ),
        style={'display': 'flex','alignItems': 'center','position':'relative','left':'-65px'}
    )
    return html.Div([left_buttons, center_col, right_col], style=header_style)
 
app = Dash(__name__, suppress_callback_exceptions=True)
 
# Chatbot Modal
chatbot_modal = html.Div(
        id="chatbot-modal",
        children=[
            html.Div([
                html.Div("Ask CameoGPT", style={"fontSize": "20px", "fontWeight": "bold", "marginBottom": "10px"}),
                dcc.Textarea(
                    id="chatbot-input",
                    placeholder="Type your question here...",
                    style={"width": "100%", "height": "80px"}
                ),
                html.Div([
                    html.Button("Send", id="chatbot-send", style={"marginTop": "10px"}),
                    html.Button("Close", id="chatbot-close", style={"marginTop": "10px", "marginLeft": "10px"})
                ]),
                html.Div(id="chatbot-response", style={"marginTop": "20px", "whiteSpace": "pre-wrap"})
            ],  style={
                "backgroundColor": "white",
                "padding": "20px",
                "borderRadius": "5px",
                "width": "400px",
                "boxShadow": "0 2px 10px rgba(0,0,0,0.2)",
                "marginTop": "20px",
                "whiteSpace": "pre-wrap",
                "maxHeight": "60vh",     # up to 60% of viewport
                "overflowY": "auto",
                "paddingRight":"10px"      # optional, to give room for scrollbar
            })
        ],
        style={
            "position": "fixed",
            "top": "50%",
            "left": "50%",
            "transform": "translate(-50%, -50%)",
            "zIndex": "3000",
            "maxHeight": "80vh", # never exceed 80% of viewport height
            "maxWidth":  "90vw", # never exceed 90% of viewport width
            "overflowY": "auto", # scroll if content is taller
            "display": "none"  # Hidden by default
        }
    )  
 
app.layout = html.Div([
    dcc.Markdown('''
<style>
    a.sidebar-link, a.sidebar-link:visited, a.sidebar-link:hover, a.sidebar-link:active {
        color: white !important;
        text-decoration: underline !important;
    }
</style>
''', dangerously_allow_html=True),
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='history-store', data=[]),
    dcc.Store(id='sidebar-state', data=False),
    build_blue_header(),
    html.Div(id="sidebar", children=sidebar_diagram_content, style=sidebar_style_closed),
    html.Div("☰", id="sidebar-toggle", style=toggle_button_style_closed),
    html.Div(
        id='main-container',
        children=[html.Div(id='page-content')],
        style={"marginLeft": "96px","transition":"margin-left 0.3s ease",
               "maxWidth":"1400px","margin":"0 auto","paddingBottom":"60px"}
    ),
 
    #Chatbot Modal
    chatbot_modal,
 
    #Button
    html.Button(
        html.Img(
            src=chat_icon_src,
            style={
                "width": "60%",  # Reduced from 100% to create padding
                "height": "60%",  # Reduced from 100% to create padding
                "objectFit": "contain",
                "margin": "20%"  # Added margin to center the icon
            }
        ),
        id="chatbot-button",
        style={
            "position": "fixed",
            "bottom": "60px",
            "right": "20px",
            "width": "60px",  # Made slightly smaller for better proportion
            "height": "60px",  # Made equal to width for perfect circle
            "borderRadius": "50%",
            "backgroundColor": "white",  # Added white background
            "border": "2px solid #e1e8ed",  # Added subtle border
            "padding": "0",
            "margin": "0",
            "cursor": "pointer",
            "zIndex": 3001,
            "boxShadow": "0 2px 10px rgba(0,0,0,0.1)",
            "transition": "all 0.2s ease",
            ":hover": {
                "transform": "scale(1.05)",
                "boxShadow": "0 4px 15px rgba(0,0,0,0.15)"
            }
        }
    ),
    html.Footer(
        "© 2025 Aerospace Inc. All rights reserved.",
        style={
            "backgroundColor": "#2c3e50",
            "color": "white",
            "textAlign": "center",
            "padding": "15px",
            "position": "fixed",
            "bottom": "0",
            "width": "100%",
            "fontSize": "14px",
            "boxShadow": "0 -2px 10px rgba(0,0,0,0.1)",
            "letterSpacing": "0.5px"
        }
    )
], style=global_style)
 
###############################################################################
# CALLBACKS
###############################################################################
 
# Chatbot Callbacks
 
# Toggle Modal Visibility
@app.callback(
    Output("chatbot-modal", "style"),
    [Input("chatbot-button", "n_clicks"), Input("chatbot-close", "n_clicks")],
    [State("chatbot-modal", "style")],
    prevent_initial_call=True
)
def toggle_chatbot(open_click, close_click, current_style):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate
    triggered = ctx.triggered[0]['prop_id'].split('.')[0]
    new_style = current_style.copy() if current_style else {}
    if triggered == "chatbot-button":
        new_style["display"] = "block"
    else:  # chatbot-close
        new_style["display"] = "none"
    return new_style
 
# Process Query via Google GenAI
@app.callback(
    Output("chatbot-response", "children"),
    Input("chatbot-send", "n_clicks"),
    State("chatbot-input", "value"),
    prevent_initial_call=True
)
def process_chatbot_query(n_clicks, query):
    if not query or not query.strip():
        return "Please enter a question."
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=[query],
            #temperature=0.3,
            #max_output_tokens=200
        )
        # return answer
        return response.text
    except Exception as e:
        return f"Error: {e}"
   
@app.callback(Output('page-content', 'children'), Input('url', 'pathname'))
def display_page(pathname):
    if pathname in ['/dashboard','/', '', None]:
        return page2_layout
    elif pathname == '/help':
        return help_page_layout()
    elif pathname.startswith("/toc/"):
        page_key = pathname.split("/toc/")[-1]
        page_title = " ".join(word.capitalize() for word in page_key.split("-"))
        return toc_page_layout(page_title)
    elif pathname.startswith("/diagram/"):
        diagram_id = pathname.split("/diagram/")[-1]
        return diagram_page_layout(diagram_id)
    else:
        return page2_layout
 
@app.callback(
    [Output('url', 'pathname'), Output('history-store', 'data')],
    [Input('search-results-dropdown', 'value')],
    [State('url', 'pathname'), State('history-store', 'data')])
def navigation_callback(search_value, current_path, history):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if history is None:
        history = []
    new_history = history.copy()
    new_url = current_path
 
    if triggered_id == 'search-results-dropdown':
        if search_value:
            new_url = search_value
            if not new_history or new_history[-1] != new_url:
                new_history.append(new_url)
 
 
    return new_url, new_history
 
@app.callback(Output("main-container", "style"), Input("sidebar-state", "data"))
def update_main_container(sidebar_state):
    if sidebar_state:
        return {
            "marginLeft":"250px",
            "transition":"margin-left 0.3s ease",
            "maxWidth":"1400px",
            "margin":"0 auto",
            "paddingBottom":"60px"
        }
    else:
        return {
            "marginLeft":"96px",
            "transition":"margin-left 0.3s ease",
            "maxWidth":"1400px",
            "margin":"0 auto",
            "paddingBottom":"60px"
        }
 
@app.callback(Output("header-left", "style"), Input("sidebar-state", "data"))
def update_header_left(sidebar_open):
    if sidebar_open:
        return {'display':'flex','alignItems':'center','marginLeft':'260px'}
    else:
        return {'display':'flex','alignItems':'center','marginLeft':'0px'}
 
@app.callback(
    [Output("sidebar", "style"), Output("sidebar-toggle", "style"), Output("sidebar-state", "data")],
    [Input("sidebar-toggle", "n_clicks")],
    [State("sidebar-state", "data")],
    prevent_initial_call=True
)
def toggle_sidebar(n_clicks, is_open):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    if not is_open:
        return sidebar_style_open, toggle_button_style_open, True
    else:
        return sidebar_style_closed, toggle_button_style_closed, False
 
@app.callback(
    Output('requirements-table', 'data'),
    Input('requirements-search', 'value')
)
def update_requirements_table_data(search_value):
    if search_value:
        filtered_df = df_csv[df_csv.apply(lambda row: row.astype(str).str.contains(search_value, case=False).any(), axis=1)]
    else:
        filtered_df = df_csv
    return filtered_df.to_dict('records')
 
@app.callback(
    [Output('progress-text', 'children'),
     Output('progress-bar', 'value'),
     Output('progress-bar', 'max')],
    Input('requirements-table', 'selected_rows')
)
def update_progress(selected_rows):
    total = len(df_csv)
    approved = len(selected_rows) if selected_rows is not None else 0
    progress_text = f"{approved} requirements approved / {total} requirements total"
    return progress_text, str(approved), str(total)
 
# NEW CALLBACK: Update the extra diagram container when a diagram is selected from the extra dropdown.
@app.callback(
    Output("extra-diagram-container", "children"),
    Input("extra-diagram-dropdown", "value")
)
def update_extra_diagram(extra_diagram_id):
    if extra_diagram_id:
        return extra_diagram_layout(extra_diagram_id)
    return ""

def help_page_layout():
    return html.Div([
        build_blue_header(),
        html.Div([
            html.H1("Dashboard Help & Documentation", style={
                "textAlign": "center",
                "color": "#2c3e50",
                "fontSize": "32px",
                "fontWeight": "600",
                "marginBottom": "40px",
                "letterSpacing": "0.5px"
            }),

            # Navigation Section
            html.Div([
                html.H2("Navigation", style={
                    "color": "#2c3e50",
                    "fontSize": "24px",
                    "fontWeight": "600",
                    "marginBottom": "20px"
                }),
                html.Ul([
                    html.Li("The top navigation bar contains quick access to Help and Dashboard pages"),
                    html.Li("Use the search dropdown in the top-right to quickly navigate to specific sections"),
                    html.Li("The sidebar toggle (☰) on the left provides quick access to all diagrams")
                ], style={"lineHeight": "1.8", "marginBottom": "30px"})
            ], style={"marginBottom": "40px"}),

            # Dashboard Overview Section
            html.Div([
                html.H2("Dashboard Overview", style={
                    "color": "#2c3e50",
                    "fontSize": "24px",
                    "fontWeight": "600",
                    "marginBottom": "20px"
                }),
                html.Ul([
                    html.Li("Description and Scope sections provide context about the MPM model"),
                    html.Li("Model Summary shows a count of different diagram types with intuitive icons"),
                    html.Li("The Model Navigation diagram provides a high-level view of the system structure"),
                    html.Li("Requirements Table allows tracking and approval of system requirements"),
                    html.Li("Diagram Hierarchy Table shows relationships between different diagrams")
                ], style={"lineHeight": "1.8", "marginBottom": "30px"})
            ], style={"marginBottom": "40px"}),

            # Features Section
            html.Div([
                html.H2("Key Features", style={
                    "color": "#2c3e50",
                    "fontSize": "24px",
                    "fontWeight": "600",
                    "marginBottom": "20px"
                }),
               
                # Requirements Management
                html.H3("Requirements Management", style={
                    "color": "#3498db",
                    "fontSize": "20px",
                    "marginBottom": "15px"
                }),
                html.Ul([
                    html.Li("Search through requirements using the search box"),
                    html.Li("Select requirements to mark them as approved"),
                    html.Li("Track approval progress with the progress bar"),
                    html.Li("View requirement details in a structured table format")
                ], style={"lineHeight": "1.8", "marginBottom": "20px"}),

                # Diagram Viewing
                html.H3("Diagram Viewing", style={
                    "color": "#3498db",
                    "fontSize": "20px",
                    "marginBottom": "15px"
                }),
                html.Ul([
                    html.Li("View diagrams in full detail with associated metadata"),
                    html.Li("Compare two diagrams side by side using the extra diagram feature"),
                    html.Li("See element counts and details for each diagram"),
                    html.Li("Navigate between related diagrams using embedded links")
                ], style={"lineHeight": "1.8", "marginBottom": "20px"}),

                # Interactive Features
                html.H3("Interactive Features", style={
                    "color": "#3498db",
                    "fontSize": "20px",
                    "marginBottom": "15px"
                }),
                html.Ul([
                    html.Li("Collapsible sidebar for quick diagram access"),
                    html.Li("Interactive progress tracking for requirements"),
                    html.Li("Real-time search functionality"),
                    html.Li("Responsive layout that adapts to different screen sizes")
                ], style={"lineHeight": "1.8", "marginBottom": "20px"})
            ], style={"marginBottom": "40px"}),

            # Tips Section
            html.Div([
                html.H2("Tips & Best Practices", style={
                    "color": "#2c3e50",
                    "fontSize": "24px",
                    "fontWeight": "600",
                    "marginBottom": "20px"
                }),
                html.Ul([
                    html.Li("Use the search function to quickly find specific requirements or diagrams"),
                    html.Li("Toggle the sidebar for a cleaner view when not actively navigating"),
                    html.Li("Compare related diagrams side by side for better understanding"),
                    html.Li("Track requirement approval progress regularly using the progress bar"),
                    html.Li("Utilize the Model Navigation diagram for understanding system structure")
                ], style={"lineHeight": "1.8"})
            ], style={"marginBottom": "40px"}),

            # Comprehensive SysML Guide Section
            html.Div([
                html.H2("Understanding SysML Diagrams", style={
                    "color": "#2c3e50",
                    "fontSize": "24px",
                    "fontWeight": "600",
                    "marginBottom": "20px"
                }),

                # Introduction to SysML
                html.H3("Introduction to SysML", style={
                    "color": "#3498db",
                    "fontSize": "20px",
                    "marginBottom": "15px"
                }),
                html.P([
                    "SysML (Systems Modeling Language) is a visual modeling language that supports the specification, analysis, design, and verification of complex systems. It extends UML (Unified Modeling Language) with systems engineering capabilities, allowing engineers to model:",
                    html.Ul([
                        html.Li("System requirements and their relationships"),
                        html.Li("System behavior and functionality"),
                        html.Li("Physical system structure and components"),
                        html.Li("Constraints and equations governing system properties"),
                        html.Li("Allocations between behavior, structure, and requirements")
                    ], style={"marginLeft": "20px", "marginTop": "10px", "marginBottom": "20px"})
                ]),

                # Diagram Types Overview with Extended Explanations
                html.H3("Diagram Types", style={
                    "color": "#3498db",
                    "fontSize": "20px",
                    "marginBottom": "15px"
                }),
                html.Div([
                    html.H4("Structure Diagrams", style={"color": "#2c3e50", "fontSize": "16px", "marginBottom": "10px"}),
                    html.Div([
                        html.H5("Block Definition Diagrams (BDD)", style={"color": "#34495e", "fontSize": "15px", "marginBottom": "8px"}),
                        html.P([
                            "Block Definition Diagrams define the system's hierarchical structure and classifications. They show:",
                            html.Ul([
                                html.Li("System decomposition and component relationships"),
                                html.Li("Type hierarchies and classifications"),
                                html.Li("Associations between blocks with multiplicity and role names"),
                                html.Li("Properties, operations, and constraints of blocks"),
                                html.Li("Value types and unit definitions")
                            ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                        ]),
                       
                        html.H5("Internal Block Diagrams (IBD)", style={"color": "#34495e", "fontSize": "15px", "marginBottom": "8px"}),
                        html.P([
                            "Internal Block Diagrams show the internal structure of a block and how its parts are connected. They include:",
                            html.Ul([
                                html.Li("Part properties showing internal components"),
                                html.Li("Ports defining interaction points"),
                                html.Li("Connectors showing how parts are wired together"),
                                html.Li("Item flows indicating what flows between parts"),
                                html.Li("Reference properties showing usage of external blocks")
                            ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                        ]),

                        html.H5("Package Diagrams", style={"color": "#34495e", "fontSize": "15px", "marginBottom": "8px"}),
                        html.P([
                            "Package Diagrams organize model elements into manageable groups. They show:",
                            html.Ul([
                                html.Li("Model organization and structure"),
                                html.Li("Dependencies between packages"),
                                html.Li("Package containment and nesting"),
                                html.Li("Model libraries and views"),
                                html.Li("Namespace relationships")
                            ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                        ])
                    ], style={"marginLeft": "15px", "marginBottom": "20px"}),

                    html.H4("Behavior Diagrams", style={"color": "#2c3e50", "fontSize": "16px", "marginBottom": "10px"}),
                    html.Div([
                        html.H5("Activity Diagrams", style={"color": "#34495e", "fontSize": "15px", "marginBottom": "8px"}),
                        html.P([
                            "Activity Diagrams model the flow of actions and data in a system. Key elements include:",
                            html.Ul([
                                html.Li("Actions: Fundamental units of behavior (rounded rectangles)"),
                                html.Li("Control flows: Show execution sequence (dashed arrows)"),
                                html.Li("Object flows: Show data/object movement (solid arrows)"),
                                html.Li("Decision/merge nodes: Show alternative paths (diamonds)"),
                                html.Li("Fork/join nodes: Show parallel paths (thick bars)"),
                                html.Li("Input/output pins: Show data inputs/outputs on actions"),
                                html.Li("Parameter nodes: Show activity inputs/outputs"),
                                html.Li("Partitions: Group actions by responsibility")
                            ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                        ]),

                        html.H5("Sequence Diagrams", style={"color": "#34495e", "fontSize": "15px", "marginBottom": "8px"}),
                        html.P([
                            "Sequence Diagrams show interactions between parts over time. They include:",
                            html.Ul([
                                html.Li("Lifelines: Represent participating blocks/parts (vertical lines)"),
                                html.Li("Messages: Show communication between lifelines (arrows)"),
                                html.Li("Execution specifications: Show when behavior is active (rectangles)"),
                                html.Li("Combined fragments: Group messages for conditions/loops"),
                                html.Li("Time constraints: Show timing requirements"),
                                html.Li("State invariants: Show required states during interaction")
                            ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                        ]),

                        html.H5("State Machine Diagrams", style={"color": "#34495e", "fontSize": "15px", "marginBottom": "8px"}),
                        html.P([
                            "State Machine Diagrams describe system states and transitions. Elements include:",
                            html.Ul([
                                html.Li("States: System conditions (rounded rectangles)"),
                                html.Li("Transitions: State changes (arrows with triggers/guards/effects)"),
                                html.Li("Initial/final states: Start/end points"),
                                html.Li("Composite states: States containing sub-states"),
                                html.Li("Choice points: Dynamic conditional branching"),
                                html.Li("Entry/exit/do behaviors: State-specific actions"),
                                html.Li("History pseudostates: Remember previous sub-state")
                            ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                        ])
                    ], style={"marginLeft": "15px", "marginBottom": "20px"}),

                    html.H4("Requirements Diagrams", style={"color": "#2c3e50", "fontSize": "16px", "marginBottom": "10px"}),
                    html.P([
                        "Requirements Diagrams visualize system requirements and their relationships. They show:",
                        html.Ul([
                            html.Li("Text-based requirements with unique IDs"),
                            html.Li("Derive relationships: Requirements derived from others"),
                            html.Li("Satisfy relationships: Design elements that fulfill requirements"),
                            html.Li("Verify relationships: Test cases that verify requirements"),
                            html.Li("Refine relationships: More detailed requirements"),
                            html.Li("Trace relationships: General dependencies"),
                            html.Li("Copy/containment relationships between requirements")
                        ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                    ]),

                    html.H4("Parametric Diagrams", style={"color": "#2c3e50", "fontSize": "16px", "marginBottom": "10px"}),
                    html.P([
                        "Parametric Diagrams express constraints and equations. They include:",
                        html.Ul([
                            html.Li("Constraint blocks: Reusable mathematical relationships"),
                            html.Li("Constraint parameters: Input/output variables"),
                            html.Li("Binding connectors: Connect parameters to properties"),
                            html.Li("Value properties: System quantities being constrained"),
                            html.Li("Nested constraint uses: Complex mathematical models")
                        ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                    ])
                ], style={"marginBottom": "30px", "paddingLeft": "20px"}),

                # Flows and Behaviors with Extended Details
                html.H3("Flows and Behaviors", style={
                    "color": "#3498db",
                    "fontSize": "20px",
                    "marginBottom": "15px"
                }),
                html.Div([
                    html.H4("Control Flows", style={"color": "#2c3e50", "fontSize": "16px", "marginBottom": "10px"}),
                    html.P([
                        "Control flows guide the execution order of actions in activity diagrams:",
                        html.Ul([
                            html.Li("Represented by dashed arrows between actions"),
                            html.Li("Can have guards (conditions) controlling flow"),
                            html.Li("Can be interrupted by interruptible regions"),
                            html.Li("Support concurrent execution through forks/joins"),
                            html.Li("Can be controlled by decision/merge nodes")
                        ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                    ]),

                    html.H4("Object Flows", style={"color": "#2c3e50", "fontSize": "16px", "marginBottom": "10px"}),
                    html.P([
                        "Object flows show data and object movement:",
                        html.Ul([
                            html.Li("Solid arrows carrying typed objects/data"),
                            html.Li("Can have transformation behaviors"),
                            html.Li("Support streaming and non-streaming"),
                            html.Li("Can be buffered or unbuffered"),
                            html.Li("May have selection and transformation behaviors")
                        ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                    ]),

                    html.H4("Behaviors", style={"color": "#2c3e50", "fontSize": "16px", "marginBottom": "10px"}),
                    html.P([
                        "System behaviors are modeled in several ways:",
                        html.Ul([
                            html.Li("Activities: Complex behaviors with control/object flows"),
                            html.Li("Operations: Services provided by blocks with parameters"),
                            html.Li("State Actions: Entry/do/exit behaviors in states"),
                            html.Li("Interactions: Message exchanges between parts"),
                            html.Li("Use Cases: High-level system functions")
                        ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                    ])
                ], style={"marginBottom": "30px", "paddingLeft": "20px"}),

                # Properties and Values with Extended Information
                html.H3("Properties and Values", style={
                    "color": "#3498db",
                    "fontSize": "20px",
                    "marginBottom": "15px"
                }),
                html.Div([
                    html.H4("Property Types", style={"color": "#2c3e50", "fontSize": "16px", "marginBottom": "10px"}),
                    html.P([
                        "Different types of properties serve different modeling purposes:",
                        html.Ul([
                            html.Li(["Value Properties: ", html.Br(),
                                   "- Quantifiable characteristics with units", html.Br(),
                                   "- Can be typed by value types or blocks", html.Br(),
                                   "- May have default values and constraints"]),
                            html.Li(["Part Properties: ", html.Br(),
                                   "- Define block composition", html.Br(),
                                   "- Have multiplicity defining number of instances", html.Br(),
                                   "- Can be composite or shared"]),
                            html.Li(["Reference Properties: ", html.Br(),
                                   "- Reference other blocks without ownership", html.Br(),
                                   "- Used for loose coupling between blocks", html.Br(),
                                   "- Can represent shared resources"]),
                            html.Li(["Flow Properties: ", html.Br(),
                                   "- Define what can flow through ports", html.Br(),
                                   "- Specify direction (in/out/inout)", html.Br(),
                                   "- Typed by blocks or value types"])
                        ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                    ]),

                    html.H4("Property Features", style={"color": "#2c3e50", "fontSize": "16px", "marginBottom": "10px"}),
                    html.P([
                        "Properties can have various features:",
                        html.Ul([
                            html.Li(["Multiplicities: ", html.Br(),
                                   "- Specify allowed number of values/instances", html.Br(),
                                   "- Format: [lower..upper]", html.Br(),
                                   "- Special values: * (many), 1 (exactly one)"]),
                            html.Li(["Derived Properties: ", html.Br(),
                                   "- Calculated from other properties", html.Br(),
                                   "- Marked with '/'", html.Br(),
                                   "- May have derivation rules"]),
                            html.Li(["Constraints: ", html.Br(),
                                   "- Restrict property values", html.Br(),
                                   "- Can be simple expressions or complex rules", html.Br(),
                                   "- May reference other properties"])
                        ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                    ])
                ], style={"marginBottom": "30px", "paddingLeft": "20px"}),

                # Relationships with Extended Details
                html.H3("Relationships", style={
                    "color": "#3498db",
                    "fontSize": "20px",
                    "marginBottom": "15px"
                }),
                html.Div([
                    html.H4("Structure Relationships", style={"color": "#2c3e50", "fontSize": "16px", "marginBottom": "10px"}),
                    html.P([
                        "Structural relationships define system organization:",
                        html.Ul([
                            html.Li(["Composition (filled diamond): ", html.Br(),
                                   "- Strong ownership", html.Br(),
                                   "- Part lifecycle tied to owner", html.Br(),
                                   "- Part cannot be shared"]),
                            html.Li(["Aggregation (empty diamond): ", html.Br(),
                                   "- Weak ownership", html.Br(),
                                   "- Parts can exist independently", html.Br(),
                                   "- Parts can be shared"]),
                            html.Li(["Generalization (triangle arrow): ", html.Br(),
                                   "- Inheritance relationship", html.Br(),
                                   "- Subtype inherits features", html.Br(),
                                   "- Can be multiple inheritance"]),
                            html.Li(["Association (line): ", html.Br(),
                                   "- General relationship", html.Br(),
                                   "- Can have role names and multiplicities", html.Br(),
                                   "- Can be directed or bidirectional"])
                        ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                    ]),

                    html.H4("Behavior Relationships", style={"color": "#2c3e50", "fontSize": "16px", "marginBottom": "10px"}),
                    html.P([
                        "Relationships between behavioral elements:",
                        html.Ul([
                            html.Li(["Control Flow: ", html.Br(),
                                   "- Shows execution sequence", html.Br(),
                                   "- Can have guards and weights", html.Br(),
                                   "- Used in activity diagrams"]),
                            html.Li(["Object Flow: ", html.Br(),
                                   "- Shows data/object movement", html.Br(),
                                   "- Can have transformation behaviors", html.Br(),
                                   "- Used in activity diagrams"]),
                            html.Li(["Message: ", html.Br(),
                                   "- Shows communication", html.Br(),
                                   "- Can be synchronous or asynchronous", html.Br(),
                                   "- Used in sequence diagrams"])
                        ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                    ])
                ], style={"marginBottom": "30px", "paddingLeft": "20px"}),

                # Advanced Concepts
                html.H3("Advanced Concepts", style={
                    "color": "#3498db",
                    "fontSize": "20px",
                    "marginBottom": "15px"
                }),
                html.Div([
                    html.H4("Allocations", style={"color": "#2c3e50", "fontSize": "16px", "marginBottom": "10px"}),
                    html.P([
                        "Allocations show relationships between different model aspects:",
                        html.Ul([
                            html.Li("Behavior to structure allocation"),
                            html.Li("Requirements to design elements"),
                            html.Li("Logical to physical architecture"),
                            html.Li("Software to hardware mapping")
                        ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                    ]),

                    html.H4("Viewpoints", style={"color": "#2c3e50", "fontSize": "16px", "marginBottom": "10px"}),
                    html.P([
                        "Different perspectives on the system:",
                        html.Ul([
                            html.Li("Operational: How the system is used"),
                            html.Li("Functional: What the system does"),
                            html.Li("Physical: How the system is built"),
                            html.Li("Performance: How well the system performs")
                        ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                    ]),

                    html.H4("Model Organization", style={"color": "#2c3e50", "fontSize": "16px", "marginBottom": "10px"}),
                    html.P([
                        "Best practices for organizing SysML models:",
                        html.Ul([
                            html.Li("Package hierarchy for logical grouping"),
                            html.Li("Model libraries for reusable elements"),
                            html.Li("Views and viewpoints for stakeholder perspectives"),
                            html.Li("Consistent naming conventions"),
                            html.Li("Clear separation of concerns")
                        ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                    ])
                ], style={"marginBottom": "30px", "paddingLeft": "20px"}),

                # Visual Notation Guide (New Section)
                html.H3("Visual Notation Guide", style={
                    "color": "#3498db",
                    "fontSize": "20px",
                    "marginBottom": "15px"
                }),
                html.Div([
                    html.H4("Common Visual Elements", style={"color": "#2c3e50", "fontSize": "16px", "marginBottom": "10px"}),
                    html.P([
                        "Key visual elements you'll encounter in diagrams:",
                        html.Ul([
                            html.Li(["Blocks: ", html.Br(),
                                    "- Rectangular boxes with name in bold", html.Br(),
                                    "- Compartments for properties/operations", html.Br(),
                                    "- Stereotypes shown in «angle brackets»"]),
                            html.Li(["Ports: ", html.Br(),
                                    "- Small squares on block boundaries", html.Br(),
                                    "- Flow ports shown with arrows", html.Br(),
                                    "- Standard ports with provided/required interfaces"]),
                            html.Li(["Actions: ", html.Br(),
                                    "- Rounded rectangles", html.Br(),
                                    "- Input/output pins as small squares", html.Br(),
                                    "- Action name inside"]),
                            html.Li(["States: ", html.Br(),
                                    "- Rounded rectangles with name at top", html.Br(),
                                    "- Internal behaviors in compartments", html.Br(),
                                    "- Entry/exit points as circles on boundary"]),
                            html.Li(["Requirements: ", html.Br(),
                                    "- Rectangles with «requirement» stereotype", html.Br(),
                                    "- ID and text in separate compartments", html.Br(),
                                    "- Additional properties in lower compartments"])
                        ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                    ]),

                    html.H4("Connector Styles", style={"color": "#2c3e50", "fontSize": "16px", "marginBottom": "10px"}),
                    html.P([
                        "Different types of connectors and their meanings:",
                        html.Ul([
                            html.Li(["Association Lines: ", html.Br(),
                                    "- Solid lines between elements showing relationships", html.Br(),
                                    "- Arrowheads indicate which element is accessing the other", html.Br(),
                                    "- Numbers near ends show how many elements can be connected (e.g., 1..* means one-to-many)", html.Br(),
                                    "- Names near connection points describe the role each element plays (e.g., 'owner', 'parts')"]),
                            html.Li(["Control Flows: ", html.Br(),
                                    "- Dashed lines with open arrowheads showing sequence of actions", html.Br(),
                                    "- Guards in square brackets specify conditions that must be true (e.g., [speed > 50])", html.Br(),
                                    "- Weights in curly braces indicate how many tokens flow (e.g., {3} means three items)"]),
                            html.Li(["Object Flows: ", html.Br(),
                                    "- Solid lines with filled arrowheads showing data/object movement", html.Br(),
                                    "- Object type labeled on flow shows what's being transferred (e.g., 'SensorData')", html.Br(),
                                    "- Selection behaviors specify which objects to transfer (e.g., 'select valid readings')", html.Br(),
                                    "- Transformation behaviors show how objects change during flow (e.g., 'convert to metric')"]),
                            html.Li(["Containment: ", html.Br(),
                                    "- Elements nested inside other elements show they belong to the container", html.Br(),
                                    "- Composition diamond (filled) shows strong ownership (child cannot exist without parent)", html.Br(),
                                    "- Example: A car engine (child) cannot exist without the car (parent)"]),
                            html.Li(["Transitions: ", html.Br(),
                                    "- Solid lines with open arrowheads showing state changes", html.Br(),
                                    "- Format: trigger[guard]/behavior", html.Br(),
                                    "- Trigger: Event causing the transition (e.g., 'buttonPressed')", html.Br(),
                                    "- Guard: Condition that must be true (e.g., [system_active])", html.Br(),
                                    "- Behavior: Action performed during transition (e.g., /turnOnLight)", html.Br(),
                                    "- Example: buttonPressed[system_active]/turnOnLight"]),
                            html.Li(["Dependencies: ", html.Br(),
                                    "- Dashed lines with open arrowheads showing one element needs another", html.Br(),
                                    "- Arrow points from dependent to independent element", html.Br(),
                                    "- Can be labeled with stereotype (e.g., «use», «import»)", html.Br(),
                                    "- Example: A software module depending on a library"]),
                            html.Li(["Realizations: ", html.Br(),
                                    "- Dashed lines with hollow triangle showing implementation", html.Br(),
                                    "- Used when one element implements behavior defined by another", html.Br(),
                                    "- Common between interfaces and implementing classes", html.Br(),
                                    "- Example: A concrete class implementing an interface"])
                        ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                    ])
                ], style={"marginBottom": "30px", "paddingLeft": "20px"}),

                # Common Patterns Section (New)
                html.H3("Common Diagram Patterns", style={
                    "color": "#3498db",
                    "fontSize": "20px",
                    "marginBottom": "15px"
                }),
                html.Div([
                    html.H4("Block Definition Patterns", style={"color": "#2c3e50", "fontSize": "16px", "marginBottom": "10px"}),
                    html.P([
                        "Common patterns in BDD diagrams:",
                        html.Ul([
                            html.Li(["System Decomposition: ", html.Br(),
                                    "- Top-level system block at top", html.Br(),
                                    "- Parts connected with composition", html.Br(),
                                    "- Multiplicities show required instances"]),
                            html.Li(["Interface Definition: ", html.Br(),
                                    "- Interface blocks with required/provided", html.Br(),
                                    "- Port types and flow specifications", html.Br(),
                                    "- Signal and operation definitions"]),
                            html.Li(["Value Type Hierarchy: ", html.Br(),
                                    "- Base units at top", html.Br(),
                                    "- Derived units with conversions", html.Br(),
                                    "- Quantity kinds and dimensions"])
                        ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                    ]),

                    html.H4("Activity Patterns", style={"color": "#2c3e50", "fontSize": "16px", "marginBottom": "10px"}),
                    html.P([
                        "Common patterns in Activity diagrams:",
                        html.Ul([
                            html.Li(["Sequential Flow: ", html.Br(),
                                    "- Actions connected in sequence", html.Br(),
                                    "- Object flows between actions", html.Br(),
                                    "- Decision nodes for branching"]),
                            html.Li(["Parallel Processing: ", html.Br(),
                                    "- Fork node splits flow", html.Br(),
                                    "- Parallel action sequences", html.Br(),
                                    "- Join node synchronizes"]),
                            html.Li(["Exception Handling: ", html.Br(),
                                    "- Interruptible regions", html.Br(),
                                    "- Exception handlers", html.Br(),
                                    "- Structured activity nodes"])
                        ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                    ]),

                    html.H4("State Machine Patterns", style={"color": "#2c3e50", "fontSize": "16px", "marginBottom": "10px"}),
                    html.P([
                        "Common patterns in State Machine diagrams:",
                        html.Ul([
                            html.Li(["Mode Management: ", html.Br(),
                                    "- Operational modes as states", html.Br(),
                                    "- Mode transitions with guards", html.Br(),
                                    "- Entry/exit actions for setup/cleanup"]),
                            html.Li(["Error Handling: ", html.Br(),
                                    "- Error states", html.Br(),
                                    "- Recovery transitions", html.Br(),
                                    "- Default error handlers"]),
                            html.Li(["Hierarchical Behavior: ", html.Br(),
                                    "- Composite states", html.Br(),
                                    "- Orthogonal regions", html.Br(),
                                    "- History pseudostates"])
                        ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                    ])
                ], style={"marginBottom": "30px", "paddingLeft": "20px"}),

                # Best Practices Section (New)
                html.H3("Modeling Best Practices", style={
                    "color": "#3498db",
                    "fontSize": "20px",
                    "marginBottom": "15px"
                }),
                html.Div([
                    html.H4("Diagram Organization", style={"color": "#2c3e50", "fontSize": "16px", "marginBottom": "10px"}),
                    html.P([
                        "Tips for creating clear, maintainable diagrams:",
                        html.Ul([
                            html.Li("Keep diagrams focused on one aspect or concern"),
                            html.Li("Use consistent naming conventions"),
                            html.Li("Limit diagram size (use decomposition)"),
                            html.Li("Align elements for readability"),
                            html.Li("Use notes to explain complex parts"),
                            html.Li("Group related elements visually"),
                            html.Li("Maintain consistent level of detail")
                        ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                    ]),

                    html.H4("Common Pitfalls", style={"color": "#2c3e50", "fontSize": "16px", "marginBottom": "10px"}),
                    html.P([
                        "Issues to avoid in SysML modeling:",
                        html.Ul([
                            html.Li("Mixing abstraction levels in one diagram"),
                            html.Li("Overloading diagrams with too much information"),
                            html.Li("Inconsistent interface definitions"),
                            html.Li("Circular dependencies"),
                            html.Li("Ambiguous flow directions"),
                            html.Li("Missing multiplicities on associations"),
                            html.Li("Incomplete requirement traces")
                        ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                    ]),

                    html.H4("Model Validation", style={"color": "#2c3e50", "fontSize": "16px", "marginBottom": "10px"}),
                    html.P([
                        "Key points to check in your models:",
                        html.Ul([
                            html.Li("All requirements are traced to design elements"),
                            html.Li("Interfaces are completely specified"),
                            html.Li("Flow directions are consistent"),
                            html.Li("State machines are complete"),
                            html.Li("Activities have clear inputs/outputs"),
                            html.Li("Allocations are complete"),
                            html.Li("Constraints are satisfiable")
                        ], style={"marginLeft": "20px", "marginTop": "5px", "marginBottom": "15px"})
                    ])
                ], style={"marginBottom": "30px", "paddingLeft": "20px"}),

                # FAQ Section (New)
                html.H3("Frequently Asked Questions", style={
                    "color": "#3498db",
                    "fontSize": "20px",
                    "marginBottom": "15px"
                }),
                html.Div([
                    html.H4("General Questions", style={"color": "#2c3e50", "fontSize": "16px", "marginBottom": "10px"}),
                    html.Div([
                        html.Details([
                            html.Summary("How do I navigate between different diagrams?", style={
                                "cursor": "pointer",
                                "padding": "10px",
                                "backgroundColor": "#f8fafc",
                                "borderRadius": "6px",
                                "marginBottom": "8px",
                                "fontWeight": "500",
                                "color": "#2c3e50"
                            }),
                            html.Div([
                                "You can navigate diagrams in several ways:",
                                html.Ul([
                                    html.Li("Use the sidebar toggle (☰) to access the diagram navigation panel"),
                                    html.Li("Click on diagram links within the Diagram Hierarchy table"),
                                    html.Li("Use the search dropdown in the top-right corner"),
                                    html.Li("Click on nested diagram links within diagram details")
                                ])
                            ], style={"padding": "15px", "lineHeight": "1.6"})
                        ], style={"marginBottom": "15px"}),

                        html.Details([
                            html.Summary("How do I approve requirements?", style={
                                "cursor": "pointer",
                                "padding": "10px",
                                "backgroundColor": "#f8fafc",
                                "borderRadius": "6px",
                                "marginBottom": "8px",
                                "fontWeight": "500",
                                "color": "#2c3e50"
                            }),
                            html.Div([
                                "To approve requirements:",
                                html.Ul([
                                    html.Li("Navigate to the Requirements Table section"),
                                    html.Li("Select requirements by clicking their checkboxes"),
                                    html.Li("Track approval progress via the progress bar"),
                                    html.Li("Use the search box to filter specific requirements")
                                ])
                            ], style={"padding": "15px", "lineHeight": "1.6"})
                        ], style={"marginBottom": "15px"}),

                        html.Details([
                            html.Summary("How do I compare diagrams?", style={
                                "cursor": "pointer",
                                "padding": "10px",
                                "backgroundColor": "#f8fafc",
                                "borderRadius": "6px",
                                "marginBottom": "8px",
                                "fontWeight": "500",
                                "color": "#2c3e50"
                            }),
                            html.Div([
                                "To compare diagrams side by side:",
                                html.Ul([
                                    html.Li("Open your primary diagram"),
                                    html.Li("Use the 'Compare with Extra Diagram' dropdown"),
                                    html.Li("Select another diagram to view alongside"),
                                    html.Li("Both diagrams will be displayed side by side with their details")
                                ])
                            ], style={"padding": "15px", "lineHeight": "1.6"})
                        ], style={"marginBottom": "15px"}),

                        html.Details([
                            html.Summary("How do I understand diagram relationships?", style={
                                "cursor": "pointer",
                                "padding": "10px",
                                "backgroundColor": "#f8fafc",
                                "borderRadius": "6px",
                                "marginBottom": "8px",
                                "fontWeight": "500",
                                "color": "#2c3e50"
                            }),
                            html.Div([
                                "To understand diagram relationships:",
                                html.Ul([
                                    html.Li("Check the Diagram Hierarchy table for parent-child relationships"),
                                    html.Li("Look for 'Nested Diagrams' in diagram details"),
                                    html.Li("Review the 'Used In' section to see where diagrams are referenced"),
                                    html.Li("Use the Model Navigation diagram for a high-level view")
                                ])
                            ], style={"padding": "15px", "lineHeight": "1.6"})
                        ], style={"marginBottom": "15px"})
                    ]),

                    html.H4("SysML-Specific Questions", style={"color": "#2c3e50", "fontSize": "16px", "marginBottom": "10px", "marginTop": "20px"}),
                    html.Div([
                        html.Details([
                            html.Summary("What's the difference between different types of diagrams?", style={
                                "cursor": "pointer",
                                "padding": "10px",
                                "backgroundColor": "#f8fafc",
                                "borderRadius": "6px",
                                "marginBottom": "8px",
                                "fontWeight": "500",
                                "color": "#2c3e50"
                            }),
                            html.Div([
                                "Each diagram type serves a specific purpose:",
                                html.Ul([
                                    html.Li(["Block Definition Diagrams (BDD): ", html.Br(),
                                           "Define system structure, hierarchies, and relationships between components"]),
                                    html.Li(["Internal Block Diagrams (IBD): ", html.Br(),
                                           "Show internal connections and flows between parts within a block"]),
                                    html.Li(["Activity Diagrams: ", html.Br(),
                                           "Describe system behavior, workflows, and data/control flows"]),
                                    html.Li(["State Machine Diagrams: ", html.Br(),
                                           "Show system states, transitions, and responses to events"]),
                                    html.Li(["Sequence Diagrams: ", html.Br(),
                                           "Illustrate interactions between system components over time"]),
                                    html.Li(["Requirements Diagrams: ", html.Br(),
                                           "Display system requirements and their relationships"]),
                                    html.Li(["Parametric Diagrams: ", html.Br(),
                                           "Define constraints and equations governing system behavior"])
                                ])
                            ], style={"padding": "15px", "lineHeight": "1.6"})
                        ], style={"marginBottom": "15px"}),

                        html.Details([
                            html.Summary("How do I read complex diagrams effectively?", style={
                                "cursor": "pointer",
                                "padding": "10px",
                                "backgroundColor": "#f8fafc",
                                "borderRadius": "6px",
                                "marginBottom": "8px",
                                "fontWeight": "500",
                                "color": "#2c3e50"
                            }),
                            html.Div([
                                "Tips for reading complex diagrams:",
                                html.Ul([
                                    html.Li("Start with the diagram title and type to understand its purpose"),
                                    html.Li("Identify the main elements or top-level blocks first"),
                                    html.Li("Follow relationships and flows systematically"),
                                    html.Li("Use the Elements Shown table to understand diagram composition"),
                                    html.Li("Check for notes or constraints that provide additional context"),
                                    html.Li("Look for patterns described in the Common Diagram Patterns section")
                                ])
                            ], style={"padding": "15px", "lineHeight": "1.6"})
                        ], style={"marginBottom": "15px"}),

                        html.Details([
                            html.Summary("What do different relationship types mean?", style={
                                "cursor": "pointer",
                                "padding": "10px",
                                "backgroundColor": "#f8fafc",
                                "borderRadius": "6px",
                                "marginBottom": "8px",
                                "fontWeight": "500",
                                "color": "#2c3e50"
                            }),
                            html.Div([
                                "Common relationship types and their meanings:",
                                html.Ul([
                                    html.Li(["Composition (filled diamond): ", html.Br(),
                                           "Strong ownership where child elements cannot exist without parent"]),
                                    html.Li(["Aggregation (empty diamond): ", html.Br(),
                                           "Weak ownership where child elements can exist independently"]),
                                    html.Li(["Generalization (triangle arrow): ", html.Br(),
                                           "Inheritance relationship showing specialization"]),
                                    html.Li(["Association (line): ", html.Br(),
                                           "General relationship between elements"]),
                                    html.Li(["Dependency (dashed arrow): ", html.Br(),
                                           "One element depends on another"]),
                                    html.Li(["Flow (arrow with item): ", html.Br(),
                                           "Shows movement of items between elements"])
                                ])
                            ], style={"padding": "15px", "lineHeight": "1.6"})
                        ], style={"marginBottom": "15px"}),

                        # New FAQ Question about Paths
                        html.Details([
                            html.Summary("What does the Path column in the Diagram Hierarchy table mean?", style={
                                "cursor": "pointer",
                                "padding": "10px",
                                "backgroundColor": "#f8fafc",
                                "borderRadius": "6px",
                                "marginBottom": "8px",
                                "fontWeight": "500",
                                "color": "#2c3e50"
                            }),
                            html.Div([
                                "The Path column shows the diagram's location in the Cameo Systems Modeler project hierarchy:",
                                html.Ul([
                                    html.Li("It represents the navigation path to find the diagram in Cameo"),
                                    html.Li("Format: Package --> Sub-Package --> Diagram Name"),
                                    html.Li(["Example: ", html.Br(),
                                           "'Model --> System Architecture --> Physical View --> Hardware Components'", html.Br(),
                                           "This means the diagram is in the Hardware Components section, within the Physical View, ", html.Br(),
                                           "which is part of System Architecture in the main Model package"]),
                                    html.Li("Arrows (-->) indicate moving from a parent package to a child element"),
                                    html.Li("The path helps you locate diagrams in large models"),
                                    html.Li("It also shows the organizational structure of your model"),
                                    html.Li("Use this path to navigate to the diagram in Cameo's containment tree")
                                ])
                            ], style={"padding": "15px", "lineHeight": "1.6"})
                        ], style={"marginBottom": "15px"})
                    ])
                ], style={"marginBottom": "30px", "paddingLeft": "20px"})

            ], style={
                "backgroundColor": "white",
                "padding": "30px",
                "borderRadius": "8px",
                "boxShadow": "0 2px 8px rgba(0,0,0,0.05)",
                "marginBottom": "40px"
            })
        ], style={
            "maxWidth": "1200px",
            "margin": "90px auto 40px",
            "padding": "40px",
            "backgroundColor": "white",
            "borderRadius": "12px",
            "boxShadow": "0 4px 12px rgba(0,0,0,0.08)",
            "color": "#2c3e50",
            "fontSize": "16px"
        })
    ], style=global_style)

if __name__ == '__main__':
    app.run_server(debug=False, port=895)