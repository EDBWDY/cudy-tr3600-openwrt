"""Compare an installed ELF with its upstream binary after sstrip padding removal."""
import hashlib
import struct


def verify_stripped_elf(original, installed):
    if original[:6] != b'\x7fELF\x02\x01' or installed[:64] != original[:64]:
        raise ValueError('ELF64 little-endian headers differ')
    if struct.unpack_from('<H', original, 18)[0] != 183:
        raise ValueError('Expected AArch64')
    offset = struct.unpack_from('<Q', original, 32)[0]
    stride, count = struct.unpack_from('<HH', original, 54)
    if stride != 56 or offset + count * stride > len(installed):
        raise ValueError('Invalid ELF program header table')
    normalized = bytearray(installed)
    reductions = []
    for index in range(count):
        position = offset + index * stride
        before = struct.unpack_from('<IIQQQQQQ', original, position)
        after = struct.unpack_from('<IIQQQQQQ', installed, position)
        if before == after:
            continue
        # sstrip -z may shorten a LOAD segment's file-backed trailing zeros.
        if before[0] != 1 or before[:5] != after[:5] or before[6:] != after[6:]:
            raise ValueError('Unexpected ELF program header change')
        if not 0 <= after[5] < before[5]:
            raise ValueError('Unexpected segment size change')
        if any(original[before[2] + after[5]:before[2] + before[5]]):
            raise ValueError('Nonzero loaded bytes removed')
        struct.pack_into('<Q', normalized, position + 32, before[5])
        reductions.append(before[5] - after[5])
    if len(installed) > len(original) or normalized != original[:len(installed)]:
        raise ValueError('Program bytes changed beyond allowed padding removal')
    for index in range(count):
        position = offset + index * stride
        segment = struct.unpack_from('<IIQQQQQQ', original, position)
        if segment[0] == 1 and any(original[max(len(installed), segment[2]):segment[2] + segment[5]]):
            raise ValueError('Nonzero loaded tail removed')
    return {'upstream_sha256': hashlib.sha256(original).hexdigest(),
            'installed_sha256': hashlib.sha256(installed).hexdigest(),
            'removed_file_bytes': len(original) - len(installed),
            'removed_load_padding_bytes': sum(reductions),
            'result': 'All program bytes identical; only zero load padding and trailing nonloaded file data removed'}
