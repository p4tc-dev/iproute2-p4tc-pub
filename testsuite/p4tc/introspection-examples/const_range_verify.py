# SPDX-License-Identifier: GPL-2.0-or-later
"""Check the compiler-generated mixed range/mask constant-entry fixture."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from objects(child)


def number(value):
    return int(value, 0) if isinstance(value, str) else value


def main():
    tc = sys.argv[1]
    command = [tc, '-j', 'p4ctrl', 'get', 'const_range/table/cb/ranges']
    expected = [([1, 3, 7, 0xab], [255] * 4, 21)]
    for left, left_mask in [(1, 255), (2, 254), (4, 252), (8, 255)]:
        for right, right_mask in [(3, 255), (4, 254)]:
            expected.append(([left, right, 7, 0xa0], [left_mask, right_mask, 255, 240], 23))
    expected += [([0, 0, 7, 0], [2, 0, 255, 0], 26),
                 ([0, 0, 7, 0], [0, 0, 255, 0], 31)]
    names = ['hdr.fields.left', 'hdr.fields.right', 'hdr.fields.selector', 'hdr.fields.flags']
    entries = []
    for priority, (values, masks, _) in enumerate(expected, 1):
        query = command + ['filter', 'prio', '==', str(priority)]
        result = subprocess.run(query, capture_output=True, text=True)
        assert result.returncode == 0, (query, result.stdout, result.stderr)
        found = [obj for obj in objects(json.loads(result.stdout)) if 'tmpl_created' in obj]
        assert len(found) == 1, result
        entries += found
    for priority, (entry, (values, masks, action_value)) in enumerate(zip(entries, expected), 1):
        assert entry['prio'] == priority, entry
        assert entry['permissions'] == '-R------R--X--', entry
        assert str(entry['tmpl_created']).lower() == 'true', entry
        keys = entry['key']
        assert [key['keyfield'] for key in keys] == names, entry
        assert [key['match_type'] for key in keys] == ['range', 'range', 'exact', 'ternary'], entry
        for key, value, mask in zip(keys, values, masks):
            actual_value, actual_mask = key['fieldval'].split('/')
            assert (number(actual_value), number(actual_mask)) == (value, mask), entry
        actions = list(objects(entry['actions']))
        assert any(obj.get('kind', '').endswith('/cb/hit') for obj in actions), entry
        params = [obj for obj in actions if obj.get('name') == 'value' and 'value' in obj]
        assert len(params) == 1 and number(params[0]['value']) == action_value, entry

    metadata = json.loads((Path(os.environ['INTROSPECTION']) / 'const_range.json').read_text())
    with tempfile.TemporaryDirectory() as directory:
        metadata['tables'][0]['keyfields'][0]['match_type'] = 'optional'
        (Path(directory) / 'const_range.json').write_text(json.dumps(metadata))
        optional = subprocess.run(query, check=True, capture_output=True, text=True,
                                  env=dict(os.environ, INTROSPECTION=directory))
        keys = [obj for obj in objects(json.loads(optional.stdout))
                if obj.get('keyfield') == 'hdr.fields.left']
        assert len(keys) == 1 and keys[0]['match_type'] == 'optional', optional
    metadata['tables'][0]['keyfields'][0]['match_type'] = 'not_a_match_kind'
    with tempfile.TemporaryDirectory() as directory:
        (Path(directory) / 'const_range.json').write_text(json.dumps(metadata))
        environment = dict(os.environ, INTROSPECTION=directory)
        invalid = subprocess.run([tc, 'p4ctrl', 'create', 'const_range/table/cb/ranges',
                                  'hdr.fields.left', '20', 'hdr.fields.right', '20',
                                  'hdr.fields.selector', '7', 'hdr.fields.flags', '0',
                                  'action', 'const_range/cb/hit', 'param', 'value', '99'],
                                 env=environment, capture_output=True, text=True)
        assert invalid.returncode != 0, invalid
        assert 'Unknown match type not_a_match_kind' in invalid.stderr, invalid
    after = subprocess.run([tc, '-j', 'p4template', 'get', 'table/const_range/cb/ranges'],
                           check=True, capture_output=True, text=True)
    tables = [obj for obj in objects(json.loads(after.stdout)) if obj.get('tname') == 'cb/ranges']
    assert len(tables) == 1 and tables[0]['entries'] == 11 and tables[0]['masks'] == 9, after
    print('CONSTANT_RANGE_ENTRIES_VERIFIED')


if __name__ == '__main__':
    main()
