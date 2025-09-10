#!/usr/bin/env python3
import json
import sys
from collections import defaultdict

if len(sys.argv) != 3:
    print("Usage: compare_complexity.py base.json pr.json")
    sys.exit(1)

with open(sys.argv[1]) as f:
    base = json.load(f)

with open(sys.argv[2]) as f:
    pr = json.load(f)

def key(entry):
    return f"{entry['path']}::{entry['function_name']}"

base_map = {key(e): e["complexity"] for e in base}
pr_map   = {key(e): e["complexity"] for e in pr}

all_keys = set(base_map) | set(pr_map)

total_base = sum(base_map.values())
total_pr   = sum(pr_map.values())

print(f"Total Cognitive Complexity: base={total_base}, pr={total_pr}, Δ={total_pr - total_base}\n")

for k in sorted(all_keys):
    b = base_map.get(k)
    p = pr_map.get(k)
    if b != p:
        if b is None:
            print(f"+ {k} added with complexity {p}")
        elif p is None:
            print(f"- {k} removed (was {b})")
        else:
            print(f"~ {k} changed from {b} → {p} (Δ={p - b})")
