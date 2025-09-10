import json
import sys

def main(file_path: str):
    # Load the JSON file
    with open(file_path, "r") as f:
        data = json.load(f)

    # Filter only functions with complexity > 0
    filtered = [item for item in data if item["complexity"] > 0]

    # Sort by complexity DESC, then path ASC
    filtered.sort(key=lambda x: (-x["complexity"], x["path"]))

    # Print markdown table header
    print("| Path | Function | Complexity |")
    print("|------|----------|------------|")

    total_complexity = 0
    for item in filtered:
        path = item["path"]
        function = item["function_name"]
        complexity = item["complexity"]
        total_complexity += complexity
        print(f"| {path} | {function} | {complexity} |")

    # Print total complexity
    print(f"\n**Total Cognitive Complexity: {total_complexity}**")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python complexity_table.py <complexipy.json>")
    else:
        main(sys.argv[1])
