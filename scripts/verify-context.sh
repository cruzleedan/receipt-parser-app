#!/usr/bin/env bash
# Validate the repository's work-item records without optional Python dependencies.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import re
from pathlib import Path
statuses = {'proposed','accepted','building','shipped','operating','superseded','rejected','abandoned'}
items = list(Path('context/work').glob('[0-9][0-9][0-9][0-9]-*.md'))
ids = set()
for path in items:
    text = path.read_text()
    if path.name.startswith('0000-'):
        continue
    front = text.split('---',2)[1]
    fields = dict(re.findall(r'^([\w-]+):\s*([^\n#]+)',front,re.M))
    ident = path.name[:4]
    assert fields['id'].strip().strip('"\'') == ident, path
    assert ident not in ids, path
    ids.add(ident)
    assert fields['status'].strip() in statuses, path
    for heading in ('## Problem','## Decision','## Definition of done','## Log'):
        assert heading in text, (path,heading)
    assert f'# WORK-{ident}' in text, path
    if fields['status'].strip() in ('shipped','operating'):
        dod = text.split('## Definition of done',1)[1].split('\n## ',1)[0]
        assert '- [ ]' not in dod, (path,'unchecked shipped definition of done')
print(f'Context valid: {len(ids)} work items')
PY
