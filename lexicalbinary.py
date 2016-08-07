import struct
import StringIO

def write8(stream, value, xor):
    stream.write(struct.pack(">B", value ^ xor))
    return stream


def log2(a, b):
    s = a.bit_length() - b.bit_length()
    if s > 0:
        b <<= s
    if s < 0:
        a <<= -s
    if a < b:
        a <<= 1
        s -= 1
    return (s, a - b, b)


def encode_bits(stream, x, terminal, xor):
    if not terminal:
        x >>= ((x - 1) & ~x).bit_length()
    shift = x.bit_length()
    shift -= 8
    while shift >= 0:
        v = (x >> shift) & 0xFF
        if (v & 0xFE) == 0:
            write8(stream, 0x1, xor)
            shift -= 7
        elif (v & 0xFE) == 0xFE:
            write8(stream, 0xFE, xor)
            shift -= 7
        else:
            write8(stream, v, xor)
            shift -= 8
    if shift > -8:
        v = (((x << 8) | terminal) >> (8 + shift)) & 0xFF
        write8(stream, v, xor)
        if v == terminal:
            return stream
    return write8(stream, terminal, xor)


def exp_golomb(value):
    count = value.bit_length()
    prefix = (1 << count) - 1
    return value ^ (prefix << (count - 1))


def encode_positive(stream, c, a, b, xor):
    if a < b:
        write8(stream, c | 0x40, xor)
    else:
        m, a = divmod(a, b)
        if m < 32:
            write8(stream, c | 0x41 + m, xor)
        elif m < 2048:
            write8(stream, c | 0x60 + (m >> 8), xor)
            write8(stream, m & 0xFF, xor)
        elif m < 1 << 64:
            write8(stream, c | 0x6F + ((m.bit_length() - 1)>> 3), xor)
            for i in range(((m.bit_length()-1) >> 3), -1, -1):
                write8(stream, 0xFF & (m >> (i << 3)), xor)
        else:
            write8(stream, c | 0x77, xor)
            encode_bits(stream, exp_golomb(m.bit_length()), 0x00, xor)
            encode_bits(stream, m, 0x00, xor)
    if a:
        n, a, b = log2(a, b)
        fraction = 1
        mask = -1
        n = exp_golomb(-n)
        bits = n.bit_length() or 1
        fraction <<= bits
        fraction |= n ^ (mask & ((1 << bits) - 1))
        if a == 0:
            return encode_bits(stream, fraction, 0x00, xor)
        while a:
            x, y = divmod(b, a)
            x = exp_golomb(x)
            bits = x.bit_length() or 1
            fraction <<= bits
            fraction |= x ^ (mask & ((1 << bits) - 1))
            a, b = y, a
            mask =~ mask
        encode_bits(stream, fraction, 0xFF & ~mask, xor)

    return stream



def encode_string(stream, value):
    array = bytearray(value, "UTF-8")
    for i in range(len(array)):
        array[i] += 1
    stream.write(array)
    stream.write(b"\x00")
    return stream


def decode_string(data, offset):
    end_index = data.index("\x00", offset)
    array = bytearray(data[offset : end_index])
    for i in range(len(array)):
        array[i] -= 1
    return (array.decode("UTF-8"), end_index + 1)


def escape_bytes(value7_uint64be):
    x = value7_uint64be
    x0 = x & 0x000000000FFFFFFF
    x1 = x & 0x00FFFFFFF0000000
    x = x0 | (x1 << 4)
    x0 = x & 0x00003FFF00003FFF
    x1 = x & 0x0FFFC0000FFFC000
    x = x0 | (x1 << 2)
    x0 = x & 0x007F007F007F007F
    x1 = x & 0x3F803F803F803F80
    x = x0 | (x1 << 1) | 0x8080808080808080
    return x


def unescape_bytes(value8_uint64be):
    x = value8_uint64be
    x0 = x & 0x007F007F007F007F
    x1 = x & 0x7F007F007F007F00
    x = x0 | (x1 >> 1)
    x0 = x & 0x00003FFF00003FFF
    x1 = x & 0x3FFF00003FFF0000
    x = x0 | (x1 >> 2)
    x0 = x & 0x000000000FFFFFFF
    x1 = x & 0x0FFFFFFF00000000
    x = x0 | (x1 >> 4)
    return x


def encode_bytes(stream, value):
    input_buffer = bytearray(value)
    # Pad input for escaping
    input_buffer.extend(b"\x00" * 7)
    input_buffer = buffer(input_buffer)
    input_len = len(value)
    buffer_len = 8 * ((input_len + 6) // 7)
    output_len = 8 * (input_len // 7) + (input_len % 7) + 1
    output_buffer = bytearray(buffer_len)
    input_offset = 0
    output_offset = 0
    while input_offset < input_len:
        value7_uint64be, = struct.unpack_from(">Q", input_buffer, input_offset)
        value7_uint64be >>= 8
        value8_uint64be = escape_bytes(value7_uint64be)
        struct.pack_into(">Q", output_buffer, output_offset, value8_uint64be)
        input_offset += 7
        output_offset += 8
    stream.write(output_buffer[:output_len])
    stream.write(b"\x00")
    return stream


def decode_bytes(data, offset):
    end_index = data.index("\x00", offset)
    input_buffer = bytearray(data[offset : end_index])
    input_len = len(input_buffer)
    input_buffer.extend(b"\x00" * 7)
    input_buffer = buffer(input_buffer)
    buffer_len = 7 * ((input_len + 7) // 8)  + 1
    output_len = 7 * (input_len // 8) + ((input_len - 1) % 8)
    output_buffer = bytearray(buffer_len)
    input_offset = 0
    output_offset = 0
    while input_offset < input_len:
        value8_uint64be, = struct.unpack_from(">Q", input_buffer, input_offset)
        value7_uint64be = unescape_bytes(value8_uint64be)
        value7_uint64be <<= 8
        struct.pack_into(">Q", output_buffer, output_offset, value7_uint64be)
        input_offset += 8
        output_offset += 7
    return (bytes(output_buffer[:output_len]), end_index + 1)


def encode_list(stream, value):
    for child in value:
        dump(stream, child)
    stream.write("\x00")
    return stream


def decode_list(data, offset):
    result = []
    byte, = struct.unpack_from(">B", data, offset)
    while byte != 0x00:
        child, offset = decode(data, offset)
        result.append(child)
        byte, = struct.unpack_from(">B", data, offset)
    return (tuple(result), offset + 1)
