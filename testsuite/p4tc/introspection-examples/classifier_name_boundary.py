# SPDX-License-Identifier: GPL-2.0-or-later
"""Check classifier names at the kernel boundary in an isolated tdc namespace."""

import json
import socket
import struct
import subprocess
import sys


def attr(kind, value):
    length = 4 + len(value)
    return struct.pack('HH', length, kind) + value + bytes(-length % 4)


def request(device, name, pipeid):
    options = attr(3, name.encode() + b'\0')
    if pipeid:
        options += attr(4, struct.pack('I', pipeid))
    payload = struct.pack('BBHiIII', 0, 0, 0, socket.if_nametoindex(device),
                          1, 0xfffffff2, (1 << 16) | socket.htons(3))
    payload += attr(1, b'p4\0') + attr(0x8002, options)
    message = struct.pack('IHHII', 16 + len(payload), 44, 0x605, 701, 0) + payload
    with socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, socket.NETLINK_ROUTE) as sock:
        sock.settimeout(5)
        sock.setsockopt(270, 10, 1)
        sock.setsockopt(270, 11, 1)
        sock.bind((0, 0))
        sock.sendto(message, (0, 0))
        while True:
            reply = sock.recv(65536)
            offset = 0
            while offset < len(reply):
                size, kind, flags, sequence, _ = struct.unpack_from('IHHII', reply, offset)
                assert size >= 16 and offset + size <= len(reply)
                data = reply[offset + 16:offset + size]
                offset += (size + 3) & ~3
                if kind != 2 or sequence != 701:
                    continue
                error = struct.unpack_from('i', data)[0]
                start = 20
                if error and not flags & 0x100:
                    start = 4 + ((struct.unpack_from('I', data, 4)[0] + 3) & ~3)
                messages = []
                if flags & 0x200:
                    while start < len(data):
                        length, atype = struct.unpack_from('HH', data, start)
                        assert length >= 4 and start + length <= len(data)
                        if atype & 0x3fff == 1:
                            messages.append(data[start + 4:start + length].rstrip(b'\0').decode())
                        start += (length + 3) & ~3
                return error, messages


def main():
    tc, device, length, pipeid = sys.argv[1:]
    length, pipeid = int(length), int(pipeid)
    valid = 'p' * min(length, 32)

    def run(*args):
        process = subprocess.run([tc, *args], capture_output=True, text=True)
        assert process.returncode == 0, (args, process.stdout, process.stderr)
        return json.loads(process.stdout)

    if length >= 32:
        for arguments in [('create', 'pipeline/' + valid, 'pipeid', '22', 'numtables', '0'),
                          ('update', 'pipeline/' + valid, 'state', 'ready')]:
            process = subprocess.run([tc, 'p4template', *arguments], capture_output=True, text=True)
            assert process.returncode == 0, (arguments, process.returncode, process.stderr)
    before = run('-j', 'p4template', 'get', 'pipeline/' + valid)
    assert run('-j', 'filter', 'show', 'dev', device, 'ingress') == []
    error, messages = request(device, 'p' * length, pipeid)
    print(json.dumps(dict(name_bytes=length, pipeid=pipeid, errno=error, extack=messages)), flush=True)
    filters = run('-j', 'filter', 'show', 'dev', device, 'ingress')
    assert before == run('-j', 'p4template', 'get', 'pipeline/' + valid)
    if length <= 32:
        assert error == 0 and filters, (error, messages, filters)
        assert any(item.get('options', {}).get('pname') == valid for item in filters), filters
        print('VALID_ATTACHMENT')
    else:
        assert error in (-22, -34), (error, messages, filters)
        assert any('policy validation' in message for message in messages), messages
        assert not filters, filters
        print('POLICY_REJECTION_UNCHANGED')


if __name__ == '__main__':
    main()
