import re

lines = [
    "ORIGIN ETD 17-Oct-25 DESTINATION ETA 13-Nov-25",
    "G",
    "VNSGN = Ho Chi Minh City, Viet Nam AUMEL = Melbourne, Australia",
    "VNSGN = Ho Chi Minh City, Viet Nam AUSYD = Sydney, Australia"
]

def parse(lines):
    origin = ""
    destination = ""
    for i, line in enumerate(lines):
        if "ORIGIN" in line and "DESTINATION" in line:
            # Look ahead a few lines for the line with "="
            found_loc_line = False
            for j in range(1, 4):
                if i + j < len(lines):
                    cand = lines[i+j].strip()
                    # Check for pattern CODE = ... CODE = ...
                    # Assume codes are 5 chars? VNSGN, AUMEL.
                    if "=" in cand:
                         # Regex to parse: Code = Loc Code = Loc
                         # The second code is usually identifying start of second part
                         match = re.search(r'([A-Z0-9]{3,5})\s*=\s*(.+?)\s+([A-Z0-9]{3,5})\s*=\s*(.+)', cand)
                         if match:
                             print(f"Matched line: {cand}")
                             print(f"Groups: {match.groups()}")
                             origin = match.group(2).strip()
                             destination = match.group(4).strip()
                             found_loc_line = True
                             break
            if found_loc_line:
                break
    return origin, destination

print("Test 1:")
print(parse(lines[:3]))
print("\nTest 2:")
print(parse([lines[0], lines[3]]))
