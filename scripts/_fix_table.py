import re

path = 'knowledge/runbooks/partition-strategy-guidelines.md'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

def pad_pipe(match):
    return " | "

# Very naive replacement for demonstration, let's just do it directly.
lines = content.split('\n')
for i, line in enumerate(lines):
    if line.startswith('|') and '|' in line:
        # split by pipe and strip whitespace, then join with ' | '
        parts = line.split('|')
        if len(parts) > 2: # means it's a table row
            # don't mess with the header separator row
            if '---' in line:
                continue
            
            new_parts = []
            for j, p in enumerate(parts):
                if j == 0 or j == len(parts) - 1:
                    new_parts.append(p) # keep empty strings at start/end
                else:
                    new_parts.append(' ' + p.strip() + ' ')
            lines[i] = '|'.join(new_parts)

with open(path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
