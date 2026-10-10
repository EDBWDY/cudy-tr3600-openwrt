"""Compare actual kernel code and DTB while accounting for known builder metadata."""
import hashlib
import lzma
import re
import struct
import zlib

KERNEL_SIZE = 13918216
HOST_OFFSETS = (9568422, 9568598, 10448430)
BUILD_ID_OFFSET = 12399900
BUILD_ID_HEADER = struct.pack('<III', 4, 20, 3) + b'GNU\0'
EXPECTED_NORMALIZED_SHA256 = 'e69d694352a478dd6d9efe7ee5602daeee1d854b75febe1f55401b17db9a31f9'
EXPECTED_DTB_SHA256 = '402789d03189463983a760cd2989380c02d85532b8ea8ee9205c19b91fdc209c'


def verify_kernel_bytes(kernel):
    if len(kernel) != KERNEL_SIZE:
        raise RuntimeError('Uncompressed kernel layout differs from audited baseline')
    hosts = [bytes(kernel[p:p + 13]) for p in HOST_OFFSETS]
    if len(set(hosts)) != 1 or not re.fullmatch(rb'runnervm[a-z0-9]{5}', hosts[0]):
        raise RuntimeError('Unexpected builder hostname metadata')
    if kernel[BUILD_ID_OFFSET:BUILD_ID_OFFSET + 16] != BUILD_ID_HEADER:
        raise RuntimeError('Known GNU build-id note layout changed')
    normalized = bytearray(kernel)
    for p in HOST_OFFSETS:
        normalized[p:p + 13] = b'runnervm00000'
    normalized[BUILD_ID_OFFSET + 16:BUILD_ID_OFFSET + 36] = bytes(20)
    digest = hashlib.sha256(normalized).hexdigest()
    if digest != EXPECTED_NORMALIZED_SHA256:
        raise RuntimeError('Kernel bytes changed beyond the three builder strings and GNU build-id')
    return digest


def fit_properties(data):
    if len(data) < 40:
        raise RuntimeError('Truncated FIT header')
    magic, total, off_struct, off_strings, _, version, _, _, strings_size, struct_size = struct.unpack_from('>10I', data)
    if magic != 0xd00dfeed or version != 17 or total > len(data):
        raise RuntimeError('Invalid FIT header')
    if off_strings + strings_size > total or off_struct + struct_size > total:
        raise RuntimeError('FIT sections exceed image')
    strings = data[off_strings:off_strings + strings_size]
    cursor, end, stack, props = off_struct, off_struct + struct_size, [], {}
    while cursor < end:
        token = struct.unpack_from('>I', data, cursor)[0]
        cursor += 4
        if token == 1:
            stop = data.index(b'\0', cursor, end)
            stack.append(data[cursor:stop].decode('ascii'))
            cursor = (stop + 4) & ~3
        elif token == 2:
            if not stack:
                raise RuntimeError('Invalid FIT node stack')
            stack.pop()
        elif token == 3:
            length, index = struct.unpack_from('>II', data, cursor)
            cursor += 8
            if not stack or cursor + length > end or index >= len(strings):
                raise RuntimeError('Invalid FIT property extent')
            name = strings[index:strings.index(b'\0', index)].decode('ascii')
            key = ('/'.join(stack), name)
            if key in props:
                raise RuntimeError('Duplicate FIT property')
            props[key] = data[cursor:cursor + length]
            cursor = (cursor + length + 3) & ~3
        elif token == 4:
            pass
        elif token == 9:
            if stack:
                raise RuntimeError('Unclosed FIT node')
            return props
        else:
            raise RuntimeError('Unknown FIT token')
    raise RuntimeError('Missing FIT end token')


def verify_fit_kernel(data):
    props = fit_properties(data)
    if props[('/images/kernel-1', 'compression')] != b'lzma\0' or props[('/images/kernel-1', 'arch')] != b'arm64\0':
        raise RuntimeError('Unexpected kernel architecture or compression')
    for node in ['/images/kernel-1', '/images/fdt-1']:
        payload = props[(node, 'data')]
        if props[(node + '/hash-1', 'algo')] != b'crc32\0' or props[(node + '/hash-2', 'algo')] != b'sha1\0':
            raise RuntimeError('Unexpected FIT payload checksum scheme')
        if props[(node + '/hash-1', 'value')] != struct.pack('>I', zlib.crc32(payload)) or props[(node + '/hash-2', 'value')] != hashlib.sha1(payload).digest():
            raise RuntimeError('FIT payload checksum mismatch')
    dtb = props[('/images/fdt-1', 'data')]
    if hashlib.sha256(dtb).hexdigest() != EXPECTED_DTB_SHA256:
        raise RuntimeError('TR3600 v1 device tree differs from independently audited hardware baseline')
    kernel = lzma.decompress(props[('/images/kernel-1', 'data')])
    digest = verify_kernel_bytes(kernel)
    return {'container_sha256': hashlib.sha256(data).hexdigest(),
            'normalized_kernel_sha256': digest, 'device_tree_sha256': EXPECTED_DTB_SHA256,
            'kernel_size': len(kernel),
            'comparison': 'All kernel bytes and full DTB identical to audited baseline except three builder hostname strings and the known GNU build-id note'}
