import json
import os
import re
 
def parse_diagram_report(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
 
    root = []
    stack = []
    current_diagram = None
    inside_used_in = False
    inside_elements = False
    inside_details = False
    current_element_detail = None
 
    def current_indent(line):
        return len(line) - len(line.lstrip(' '))
 
    for i, line in enumerate(lines):
        raw = line.rstrip('\n')
        stripped = raw.strip()
        indent = current_indent(raw)
 
        if not stripped:
            continue
 
        # Diagram start
        if stripped.startswith("Diagram: "):
            match = re.match(r"Diagram:\s+(.*?)\s+\[(.*?)\]", stripped)
            if match:
                current_diagram = {
                    "element_type": "Diagram",
                    "name": match.group(1),
                    "type": match.group(2),
                    "id": "",
                    "path": "",
                    "image": "",
                    "used_in": [],
                    "elements_shown": {},
                    "element_details": [],
                    "children": []
                }
                while stack and indent <= stack[-1]["_indent"]:
                    stack.pop()
                if stack:
                    stack[-1]["children"].append(current_diagram)
                else:
                    root.append(current_diagram)
 
                current_diagram["_indent"] = indent
                stack.append(current_diagram)
                inside_used_in = False
                inside_elements = False
                inside_details = False
            continue
 
        # Diagram Metadata
        if current_diagram:
            if stripped.startswith("ID:"):
                current_diagram["id"] = stripped.split("ID:")[1].strip()
            elif stripped.startswith("Path:"):
                current_diagram["path"] = stripped.split("Path:")[1].strip()
            elif stripped.startswith("Image Filename:"):
                current_diagram["image"] = stripped.split("Image Filename:")[1].strip()
            elif stripped.startswith("Used in:"):
                inside_used_in = True
                inside_elements = False
                inside_details = False
                if "(No references found)" in stripped:
                    current_diagram["used_in"] = []
            elif stripped.startswith("Elements Shown:"):
                inside_elements = True
                inside_used_in = False
                inside_details = False
            elif stripped.startswith("=== Element Details ==="):
                inside_details = True
                inside_elements = False
                inside_used_in = False
            elif inside_used_in and stripped.startswith("- "):
                match = re.match(r"-\s+(.*?)\s+\[(.*?)\]", stripped)
                if match:
                    current_diagram["used_in"].append({
                        "name": match.group(1),
                        "type": match.group(2)
                    })
            elif inside_elements and re.match(r"-\s+.*?:\s+\d+", stripped):
                es_match = re.match(r"-\s+(.*?):\s+(\d+)", stripped)
                if es_match:
                    key, count = es_match.groups()
                    current_diagram["elements_shown"][key.strip()] = int(count)
            elif inside_details and stripped.startswith("→ "):
                match = re.match(r"→\s+(.*?):\s*(.*?)\(ID:\s+(.*?)\)", stripped)
                if match:
                    current_element_detail = {
                        "type": match.group(1).strip(),
                        "name": match.group(2).strip(),
                        "id": match.group(3).strip(),
                        "image": None
                    }
                    current_diagram["element_details"].append(current_element_detail)
            elif inside_details and stripped.startswith("- Image:") and current_element_detail:
                current_element_detail["image"] = stripped.split("- Image:")[1].strip()
 
        # Fallback - general hierarchy
        elif re.match(r"^\w+Impl:.*", stripped):
            match = re.match(r"^(\w+)Impl:\s*(.*)", stripped)
            if match:
                element_type = match.group(1)
                element_name = match.group(2).strip() if match.group(2) else None
                node = {
                    "element_type": element_type,
                    "element_name": element_name if element_name else None,
                    "children": [],
                    "_indent": indent
                }
                while stack and indent <= stack[-1]["_indent"]:
                    stack.pop()
                if stack:
                    stack[-1]["children"].append(node)
                else:
                    root.append(node)
                stack.append(node)
 
    # Remove helper keys
    def clean(node):
        node.pop("_indent", None)
        for child in node.get("children", []):
            clean(child)
        return node
 
    return [clean(n) for n in root]
 
def export_to_json(input_txt_path, output_json_path):
    data = parse_diagram_report(input_txt_path)
    os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"✅ JSON exported to: {output_json_path}")
 
# Example usage
if __name__ == "__main__":
    input_path = r"C:\Users\excel\Desktop\DiagramExport_Enhanced_20250420_181358\DiagramUsageReport.txt"
    output_path = r"C:\Users\excel\Downloads\Senior_Design_Dashboard_Attachies\DiagramUsageReport_Enhanced41526part1234.json"
    export_to_json(input_path, output_path)
    
    