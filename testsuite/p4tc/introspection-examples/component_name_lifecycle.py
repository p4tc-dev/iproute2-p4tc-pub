# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise full-width identifiers and composite names in an isolated namespace."""

import json
import subprocess
import sys

TC, MODE = sys.argv[1:]
P, C, T, A, V = (letter * 32 for letter in 'pctav')
REL = '/'.join((C, T, A))
FULL = P + '/' + REL


def run(*args, status=0):
    process = subprocess.run([TC, *args], capture_output=True, text=True)
    assert process.returncode == status, (args, process.returncode, process.stdout, process.stderr)
    return process.stdout


def values(obj):
    if isinstance(obj, dict):
        for value in obj.values():
            yield from values(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from values(value)
    else:
        yield obj


def get(path, *args):
    return json.loads(run('-j', 'p4template', 'get', path, *args))


def nested(runtime):
    run('p4template', 'create', 'pipeline/' + P, 'pipeid', '22', 'numtables', '1')
    run('p4template', 'create', 'action/' + FULL, 'actid', '1',
        'param', V, 'type', 'bit32', 'id', '1')
    for length, ident in ((31, 2), (32, 3)):
        run('p4template', 'create', 'action/' + P + '/' + 'n' * length, 'actid', str(ident))
    before = get('action/' + FULL)
    assert FULL in set(values(before)), before
    assert V in set(values(before)), before
    for length in (31, 32):
        assert P + '/' + 'n' * length in set(values(get('action/' + P + '/' + 'n' * length)))
    for position in range(3):
        components = [C, T, A]
        components[position] += components[position][0]
        run('p4template', 'create', 'action/' + P + '/' + '/'.join(components),
            'actid', '4', status=255)
    assert before == get('action/' + FULL)
    run('p4template', 'update', 'action/' + FULL, 'num_prealloc_acts', '4')
    run('p4template', 'create', 'table/' + P + '/' + C + '/' + T, 'tblid', '1', 'keysz', '32',
        'table_acts', 'act', 'name', FULL)
    table = get('table/' + P + '/' + C + '/' + T)
    assert C + '/' + T in set(values(table)), table
    assert REL in set(values(table)), table
    assert FULL in set(values(get('action/' + P))), 'Full-width action missing from dump'
    if runtime:
        run('p4template', 'update', 'action/' + FULL, 'state', 'active')
        run('p4template', 'update', 'pipeline/' + P, 'state', 'ready')
        entry = P + '/table/' + C + '/' + T
        run('p4ctrl', 'create', entry, 'key', '7', 'action', FULL, 'param', V, '9')
        data = json.loads(run('-j', 'p4ctrl', 'get', entry))
        assert FULL in set(values(data)) and V in set(values(data)), data
        run('p4ctrl', 'update', entry, 'key', '7', 'action', FULL, 'param', V, '10')
        run('p4ctrl', 'del', entry, 'key', '7')
    else:
        run('p4template', 'del', 'table/' + P + '/' + C + '/' + T)
        run('p4template', 'del', 'action/' + FULL)
        run('p4template', 'create', 'action/' + FULL, 'actid', '1')
        assert FULL in set(values(get('action/' + FULL)))


def externs():
    ext, inst, param = 'E' * 32, 'i' * 32, 'v' * 255
    run('p4template', 'create', 'pipeline/' + P, 'pipeid', '22', 'numtables', '1')
    run('p4template', 'create', 'extern/root/' + ext, 'extid', '1', 'numinstances', '2')
    path = 'extern_inst/' + P + '/' + ext + '/' + inst
    run('p4template', 'create', path, 'instid', '1', 'control_path',
        'tc_key', 'index', 'ptype', 'bit32', 'param', param, 'ptype', 'bit32')
    obj = get(path)
    assert inst in set(values(obj)) and param in set(values(obj)), obj
    assert ext in set(values(get('extern/root/' + ext)))
    run('p4template', 'del', path)
    run('p4template', 'del', 'extern/root/' + ext)
    run('p4template', 'create', 'extern/root/DirectCounter', 'extid', '0x1A000000',
        'numinstances', '2', 'has_exec_method')
    path = 'extern_inst/' + P + '/DirectCounter/' + inst
    run('p4template', 'create', path, 'instid', '1', 'tc_numel', '4', 'tbl_bindable',
        'control_path', 'tc_key', 'index', 'ptype', 'bit32', 'param', 'pkts', 'ptype',
        'bit64', 'constructor', 'param', 'type', 'ptype', 'bit32', '0')
    run('p4template', 'create', 'table/' + P + '/cb/table', 'keysz', '16',
        'pna_direct_counter', 'DirectCounter/' + inst)
    table = get('table/' + P + '/cb/table')
    assert table[0]['counter_inst_path'] == inst, table
    assert inst in set(values(get(path)))
    run('p4template', 'del', 'table/' + P + '/cb/table')
    run('p4template', 'del', path)
    run('p4template', 'del', 'extern/root/DirectCounter')


if MODE in ('nested', 'runtime'):
    nested(MODE == 'runtime')
elif MODE == 'extern':
    externs()
else:
    raise ValueError(MODE)
print('COMPONENT_LIFECYCLE_OK')
