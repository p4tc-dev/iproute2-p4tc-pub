#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
import json
import subprocess
import sys

tc, mode = sys.argv[1], sys.argv[2]
result = subprocess.run([tc, '-j', 'p4template', 'get', 'table/ptables/cb/tname'],
                        capture_output=True, text=True)
assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
after = json.loads(result.stdout)
assert len(after) == 1, after
if mode == 'hit':
    assert 'default_hit' not in after[0], after
elif mode == 'miss':
    assert 'default_miss' not in after[0], after
elif mode == 'mixed-hit':
    before = json.load(open(sys.argv[3]))
    assert after == before, (before, after)
else:
    raise AssertionError(mode)
print('absent')
