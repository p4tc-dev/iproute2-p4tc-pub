# SPDX-License-Identifier: GPL-2.0-or-later
"""Send a frozen boundary request inside the isolated tdc guest namespace."""

from pathlib import Path
import socket
import struct
import sys


def main():
    packet = bytearray(Path(sys.argv[1]).read_bytes())
    length, kind, flags, _, _ = struct.unpack_from('IHHII', packet)
    assert length == len(packet)
    sequence = 701
    struct.pack_into('IHHII', packet, 0, length, kind, (flags | 5) & ~8, sequence, 0)
    with socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, socket.NETLINK_ROUTE) as sock:
        sock.settimeout(5)
        sock.setsockopt(270, 10, 1)  # NETLINK_CAP_ACK
        sock.setsockopt(270, 11, 1)  # NETLINK_EXT_ACK
        sock.bind((0, 0))
        sock.sendto(packet, (0, 0))
        while True:
            reply = sock.recv(65536)
            offset = 0
            while offset < len(reply):
                size, rkind, rflags, seq, _ = struct.unpack_from('IHHII', reply, offset)
                assert size >= 16 and offset + size <= len(reply)
                payload = reply[offset + 16:offset + size]
                offset += (size + 3) & ~3
                if seq != sequence or rkind != 2:
                    continue
                error = struct.unpack_from('i', payload)[0]
                start = 20
                if error and not rflags & 0x100:
                    original_length = struct.unpack_from('I', payload, 4)[0]
                    start = 4 + ((original_length + 3) & ~3)
                messages = []
                if rflags & 0x200:
                    while start < len(payload):
                        alen, atype = struct.unpack_from('HH', payload, start)
                        assert alen >= 4 and start + alen <= len(payload)
                        if atype & 0x3fff == 1:
                            messages.append(payload[start + 4:start + alen].rstrip(b'\0').decode())
                        start += (alen + 3) & ~3
                print('errno:', error, 'extack:', messages)
                assert error in (-22, -34), (error, messages)
                assert any(('policy validation' in message or 'component length' in message or 'single NUL' in message) for message in messages), messages
                print('POLICY_REJECTED')
                return


if __name__ == '__main__':
    main()
