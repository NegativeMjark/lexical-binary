import struct
import io
import sys
import fractions
import math

ENCODE_SPECIAL = {
    None:          b"\x01\x81",
    float("-inf"): b"\x07\x87",
    float("inf"):  b"\x78\xF8",
}

END_OF_LIST = object()

DECODE_SPECIAL = {
    0x00: END_OF_LIST,
    0x01: None,
    0x02: False,
    0x03: True,
    0x06: float("nan"),
    0x07: float("-inf"),
    0x78: float("inf"),
}


def dumps(value):
    return encode(io.BytesIO(), value, 0)[0].getvalue()

def loads(data):
    return decode(data, 0)[0]

def encode(stream, value, previous_negative):
    negative = False
    if isinstance(value, list) or isinstance(value, tuple):
        stream.write(b"\x7B\xFB"[previous_negative])
        previous_negative = 0
        for v in value:
            stream, previous_negative = encode(stream, v, previous_negative)
        stream.write(b"\x00\x80"[previous_negative])
    elif isinstance(value, bytes):
        stream.write(b"\x7A\xFA"[previous_negative])
        encode_bytes(stream, value)
    elif isinstance(value, unicode):
        stream.write(b"\x79\xF9"[previous_negative])
        encode_string(stream, value)
    elif isinstance(value, bool):
        # We can't handle bools using ENCODE_SPECIAL because False == 0 and
        # 1 == True.
        stream.write((b"\x02\x82",b"\x03\x83")[value][previous_negative])
    elif value in ENCODE_SPECIAL:
        stream.write(ENCODE_SPECIAL[value][previous_negative])
    else:
        if isinstance(value, float):
            if math.isnan(value):
                # We handle NaN here rather than using ENCODE_SPECIAL since
                # NaN can't be used as a dictionary key since NaN != NaN.
                stream.write(b"\x06\x86"[previous_negative])
                return stream, False
            # Handle -0.0 by copying the sign to 1. We can't use ENCODE_SPECIAL
            # because -0.0 == 0.0.
            negative = math.copysign(1, value) < 0
        else:
            negative = value < 0

        value = fractions.Fraction(value)
        if negative:
            xor = 0xFF
            value = -value
            previous_negative = not(previous_negative)
        else:
            xor = 0

        encode_positive(
            stream, previous_negative, value.numerator, value.denominator, xor
        )
    return stream, negative


def decode(data, offset=0):
    first, = struct.unpack_from(">B", data, offset)
    first &= 0x7F
    if first in DECODE_SPECIAL:
        return (DECODE_SPECIAL[first], offset + 1)
    elif first == 0x3F:
        peek, = struct.unpack_from(">B", data, offset + 1)
        if peek & 0x80:
            return (float("-0"), offset + 1)
        else:
            return decode_number(data, offset, first)
    elif 0x8 <= first < 0x78:
        return decode_number(data, offset, first)
    elif first == 0x79:
        return decode_string(data, offset + 1)
    elif first == 0x7A:
        return decode_bytes(data, offset + 1)
    elif first == 0x7B:
        result = []
        offset += 1
        while True:
            value, offset = decode(data, offset)
            if value is END_OF_LIST:
                return tuple(result), offset
            else:
                result.append(value)
    else:
        raise ValueError("Invalid value byte %x at offset %d" % (first, offset))


## Numbers ##

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


def decode_bits(data, offset, xor):
    m = sys.maxsize
    nextFF = (data.find('\xff', offset) + m + 1) & m
    next00 = (data.find('\x00', offset) + m + 1) & m
    end = min(next00, nextFF) + 1
    values = bytearray(data[offset:end])
    result = 0
    for value in values:
        value ^= xor
        if value == 0x01:
            result <<= 7
        elif value == 0xFE:
            result <<= 7
            result |= 0x7F
        else:
            result <<= 8
            result |= value
    return (result, end)


def exp_golomb(value):
    count = value.bit_length()
    prefix = (1 << count) - 1
    return value ^ (prefix << (count - 1))


def read_exp_golomb(value, bits=None):
    if bits is None:
        bits = value.bit_length()
    ones = bits - (value ^ ((1 << bits) - 1)).bit_length()
    size = ones * 2 + 1
    left = bits - size
    if left < 0:
        value <<= -left
        left = 0
    number = value >> left
    number |= 1 << ones
    number &= (1 << (ones + 1)) - 1
    return number, left

def exp2_golomb(value):
    count = value.bit_length()
    shift = count - 1
    value &= (1 << shift) - 1
    return (exp_golomb(count) << shift) | value

def read_exp2_golomb(value, bits=None):
    if bits is None:
        bits = value.bit_length()
    exponent, bits = read_exp_golomb(value, bits)
    shift = (exponent - 1 - bits)
    if shift > 0:
        value <<= shift
    else:
        value >>= -shift
    result = (1 << (exponent - 1))
    result |= value & (result - 1)
    return result

def encode_positive(stream, c, a, b, xor):
    c <<= 7
    if a < b:
        write8(stream, c | 0x40, xor)
    else:
        m, a = divmod(a, b)
        if m < 32:
            write8(stream, c | 0x40 + m, xor)
        elif m < 2048:
            write8(stream, c | 0x60 + (m >> 8), xor)
            write8(stream, m & 0xFF, xor)
        elif m < 1 << 64:
            write8(stream, c | 0x6F + ((m.bit_length() - 1)>> 3), xor)
            for i in range(((m.bit_length()-1) >> 3), -1, -1):
                write8(stream, 0xFF & (m >> (i << 3)), xor)
        else:
            write8(stream, c | 0x77, xor)
            encode_bits(stream, exp2_golomb(m), 0x00, xor)
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

def decode_number(data, offset, first):
    if first & 0x40:
        negative = False
        xor = 0x00
    else:
        negative = True
        xor = 0xFF
    first ^= xor
    first &= 0x7F
    if first < 0x77:
        if first < 0x60:
            value = first & 0x1F
            end = offset + 1
        elif first < 0x70:
            end = offset + 2
            value = first & 0xF
        else:
            end = offset + first - 0x6D
            value = 0
        for i in range(offset + 1, end):
            value <<= 8
            value |= xor ^ struct.unpack_from(">B", data, i)[0]
    else:
        value, end = decode_bits(data, offset + 1, xor)
        value = read_exp2_golomb(value)

    peek = xor ^ struct.unpack_from(">B", data, end)[0]
    if peek & 0x80:
        fraction, end = decode_bits(data, end, xor)
        left = fraction.bit_length() - 1
        mask = (1 << left) - 1
        fraction &= mask
        fraction ^= mask
        exponent, left = read_exp_golomb(fraction, left)
        terms = []
        fraction &= (1 << left) - 1
        while left:
            term, left = read_exp_golomb(fraction, left)
            if left:
                terms.append(term)
                mask = (1 << left) - 1
                fraction &= mask
                fraction ^= mask

        a, b = (0,1)
        for term in terms[::-1]:
            a, b = (b, term * b + a)

        a += b
        b <<= exponent
        z = a | b
        shift = ((z - 1) & ~z).bit_length()
        a >>= shift
        b >>= shift

        value += fractions.Fraction(a, b)

    if negative:
        value = -value

    return value, end


## Strings ##
# Encode strings by adding one to each byte of their UTF-8 encoding.
# End the string with a 0 byte.

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


## Bytes ##

def escape_bytes(value7_uint64be):
    """Escapes seven bytes to eight bytes.

    Args:
        value7_uint64be(int): Bytes as a 56-bit bigendian unsigned integer.
    Returns:
        int: Escaped bytes as a 64-bit bigendian unsigned integer.
    """
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
    """Unescapes seven bytes from eight bytes.

    Args:
        value8_uint64be(int): Bytes as a 64-bit bigendian unsigned integer.
    Returns:
        int: Unescaped bytes as a 56-bit bigendian unsigned integer.
    """
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
    """Encode the bytes to the stream"""
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


## Lists ##

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
