import struct
import StringIO

def dump(stream, value):
    if isinstance(value, bytes):
        return encode_bytes(stream, value)
    elif isinstance(value, unicode):
        return encode_string(stream, value)
    elif value is False:
        return encode_false(stream)
    elif value is True:
        return encode_true(stream)
    elif isinstance(value, (int, long)):
        return encode_integer(stream, value)
    elif isinstance(value, (tuple, list)):
        return encode_list(stream, value)
    elif isinstance(value, float):
        return encode_float(stream, value)
    elif value is None:
        return encode_none(stream)
    else:
        raise ValueError("Don't know how to encode " + str(type(value)))


def dumps(value):
    return dump(StringIO.StringIO(), value).getvalue()


def loads(data):
    return decode(data, 0)[0]


def decode(data, offset):
    decoders = {
        0x10: decode_none,
        0x11: decode_false,
        0x12: decode_true,
        0x20: decode_bytes,
        0x21: decode_list,
        0x22: decode_string, 
        0x23: decode_float,
        0x24: decode_negative_integer,
        0x25: decode_positive_integer,
    }
    code, = struct.unpack_from(">B", data, offset)
    return decoders[code](data, offset + 1)


def encode_none(stream):
    stream.write(b"\x10")
    return stream


def decode_none(data, offset):
    return (None, offset)


def encode_false(stream):
    stream.write(b"\x11")
    return stream


def decode_false(data, offset):
    return (False, offset)


def encode_true(stream):
    stream.write(b"\x12")
    return stream


def decode_true(data, offset):
    return (True, offset)


def encode_string(stream, value):
    stream.write(b"\x22")
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
    stream.write(b"\x20")
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


def encode_integer(stream, value):
    positive = value >= 0
    if not positive:
        value = -1 - value
    
    output_len = max(1, (value.bit_length() + 6) // 7) 
    output_buffer = bytearray(output_len)
    output_buffer[0] = value & 0x7F
    output_offset = 1
    value >>= 7
    while value:
        output_buffer[output_offset] = 0x80 | (value & 0x7F)
        output_offset += 1
        value >>= 7
    output_buffer.reverse()
    
    if positive:
        stream.write(b"\x25")
        stream.write(output_buffer)
    else:
        for i in range(output_len):
            output_buffer[i] ^= 0xFF        
        stream.write(b"\x24")
        stream.write(output_buffer)
    return stream


def decode_positive_integer(data, offset):
    byte, = struct.unpack_from(">B", data, offset)
    value = byte & 0x7F
    while byte & 0x80:
        offset += 1
        byte, = struct.unpack_from(">B", data, offset)
        value <<= 7
        value |= byte & 0x7F
    return (value, offset + 1)


def decode_negative_integer(data, offset):
    byte, = struct.unpack_from(">B", data, offset)
    byte = ~byte
    value = byte & 0x7F
    while byte & 0x80:
        offset += 1
        byte, = struct.unpack_from(">B", data, offset)
        byte = ~byte
        value <<= 7
        value |= byte & 0x7F
    return (-1 - value, offset + 1)


def encode_float(stream, value):
    stream.write(b"\x23")
    value_uint64be, = struct.unpack(">Q", struct.pack(">d", value))
    if value_uint64be & 0x8000000000000000:
        value_uint64be = ~value_uint64be & 0xFFFFFFFFFFFFFFFF
    else:
        value_uint64be |= 0x8000000000000000
    stream.write(struct.pack(">Q", value_uint64be))
    return stream


def decode_float(data, offset):
    value_uint64be, = struct.unpack_from(">Q", data, offset)
    if value_uint64be & 0x8000000000000000:
        value_uint64be &= 0x7FFFFFFFFFFFFFFF
    else:
        value_uint64be = ~value_uint64be
    value, = struct.unpack(">d", struct.pack(">Q", value_uint64be))
    return (value, offset + 8)


def encode_list(stream, value):
    stream.write(b"\x21")
    for child in value:
        dump(stream, child)
    stream.write(b"\x01") 
    return stream


def decode_list(data, offset):
    result = []
    byte, = struct.unpack_from(">B", data, offset)
    while byte != 0x01:
        child, offset = decode(data, offset)
        result.append(child)
        byte, = struct.unpack_from(">B", data, offset)
    return (tuple(result), offset + 1)
        


