# SPDX-License-Identifier: GPL-2.0-or-later
"""Wait for the entry-age predicate before checking the recursion-limit filter."""

import json
import subprocess
import sys
import time


def main():
    command = [sys.argv[1], '-j', 'p4ctrl', 'get', 'ptables/table/cb/tname4',
               'filter', '(msecs_since', '>', '10', '&&', '(prio', '=', '64000',
               '&&', '(param.act.cb.send_nh2.dst_port', '=', 'lo', '&&',
               'param.act.cb.send_nh2.bit32_test', '=', '22', '&&',
               'key.randomKey1', '=', '255', '&&', 'key.randomKey2', '=', '92)))']
    deadline = time.monotonic() + 2
    attempts = 0
    while True:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stderr)
        data = json.loads(result.stdout)
        attempts += 1
        if any(reply.get('entries') for reply in data):
            print(result.stdout, end='')
            print(f'Entry-age filter polls: {attempts}', file=sys.stderr)
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('Entry-age filter did not match within two seconds: ' + result.stdout)
        time.sleep(0.02)


if __name__ == '__main__':
    main()
