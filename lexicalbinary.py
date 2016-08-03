import struct
import StringIO

def continued_fraction(result, numerator, denominator):
    a, b = divmod(numerator, denominator)
    result.append(a)
    if b:
        continued_fraction(result, denominator, b)
    return result


def write8(stream, value, xor):
    stream.write(struct.pack(">B", value ^ xor))
    return stream


def encode_term(stream, value, continued, xor):
    if value < 16:
        return write8(stream, 0x80 | (value << 1) | continued, xor)

    exp = value.bit_length() - 1
    exp_bits = exp.bit_length()
    exp_bytes = (exp_bits + 2) // 7

    if exp_bytes == 0:
        write8(stream, 0xA0 | exp, xor)
    elif exp_bytes < 6:
        b0 = (0xA0, 0xB0, 0xB8, 0xBC, 0xBE)[exp_bytes]
        b0 |= exp >> (exp_bytes * 8)
        write8(stream, b0, xor)
        for i in range(exp_bytes):
            write8(stream, 0xFF & (exp >> (8 * (exp_bytes - 1 - i))), xor)
    else:
        # In theory the encoding format supports numbers larger than
        # 2 ^ (2 ^ 33). However it's unlikely that it will be necessary
        # to do so.
        raise ValueError("Number is too large")

    value <<= (7 - ((exp - 6) % 7)) % 7
    shift = value.bit_length() - 7
    mask = (1 << (shift + 6)) - 1
    value &= mask
    while True:
        b = (value >> shift) << 2
        mask >>= 6
        shift -= 1
        value &= mask
        if not value:
            return write8(stream, b | continued, xor)
        b |= 2 | (value >> shift)
        shift -= 6
        mask >>= 1
        value &= mask
        write8(stream, b, xor)

def encode_ratio(stream, value, xor):
    numerator, denominator = value
    terms = continued_fraction([], numerator, denominator)
    for term in terms[:-1]:
        encode_term(stream, term, 1, xor)
        xor ^= 0xFF
    return encode_term(stream, terms[-1], 0, xor)

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
