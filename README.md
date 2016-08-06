lexical-binary
==============

A lexicographic binary encoding. Encode strings, bytes, and numbers
and lists in a compact binary form preserving lexicographic sorting order.


TODO
----

 * Handle dictionaries and sets (What would a sensible ordering be for them?)


Encoding
========

Numbers
-------

Numbers greater than one are encoded as an exponent and a mantissa followed by
a continued fraction:

    2^n + m + (1 / (a_1 + (1 / a_2 ...

Numbers less than one are encoded as a exponent and a continued fraction.

    2^-n * (1 / a_1 + (1 / a_2 ...

For positive numbers the first byte is one of:

    +----------+---------+-----------------+
    | 10000000 | 1 Byte  | Zero            |
    +----------+---------+-----------------+
    | 10000001 | N bytes | 2^-1 or less    |
    +----------+---------+-----------------+
    | 1000001C |         |                 |
    |    to    | 1 byte  | 1 to 47         |
    | 110xxxxC |         |                 |
    +----------+---------+-----------------+
    | 1110xxxx | 2 bytes | 48 to 2047      |
    | 1111000x | 3 bytes | 2048 to 2^16-1  |
    | 1111001x | 4 bytes | 2^16 to 2^32-1  |
    | 1111010x | 9 bytes | 2^32 to 2^64-1  |
    +----------+---------+-----------------+
    | 11110110 | 2 bytes | 2^64 to 2^191   |
    | 11110111 | N bytes | 2^192 or more   |
    +----------+---------+-----------------+


For numbers less than 2^-256 the exponent is encoded as unary count of the
number of bytes needed to encode the exponent, followed by the exponent
itself followed a single bit to encode whether a continued fraction follows.

    +-------------------------------------+
    | 10000001 1yyyyyyC                   |
    | 10000001 01yyyyyy yyyyyyyC          |
    | 10000001 001yyyyy yyyyyyyy yyyyyyyC |
    | ...                                 |
    +-------------------------------------+


For numbers greater than 2^64 the exponent is encoded as a unary count of the
number of bytes needed to encode the exponent, followed by the exponent.

    +-------------------------------------+
    | 11110110 yyyyyyyy                   |
    | 11110111 0yyyyyyy yyyyyyyy          |
    | 11110111 10yyyyyy yyyyyyyy yyyyyyyy |
    | ...                                 |
    +-------------------------------------+


For numbers greater than 2^64 the exponent is followed by a mantissa. The
mantissa can be truncated if all the low bits are 0.

     0 1 2 3 4 5 6 7
    +-----------+-+-+
    | Mantissa  |Z|C|
    +-----------+-+-+

        Mantissa:
            The high bits of the mantissa.
        Zero Flag: Z
            This is 0 if all the lower bits of the mantissa are zero.
            If this is set then this is the last byte of the mantissa.
        Continued Fraction Flag: C
            If the Zero Flag is 0 then this flag is 0 if this is the
            last term of the continued fraction and this flag is 1 if
            another term of the continued fraction follows this one.
            Otherwise if the Zero Flag is 1 then this is the next
            highest bit of the mantissa.

The first term may be followed by a continued fraction if the C bit is set.
The continued fraction is encoded using a modified exp-golomb encoding.

    +--------------+-------+
    | 0            | 1     |
    | 10x          | 2-3   |
    | 110xx        | 4-7   |
    | 1110xxx      | 8-15  |
    | 111100xxxx   | 16-31 |
    | 1111010xxxxx | 31-64 |
    | ......       |       |
    | 11111        | stop  |
    +--------------+-------+

Strings
-------

Unicode strings are null terminated encoded using a form of UTF8
http://tools.ietf.org/html/rfc3629 modified to avoid embedded %x00 null bytes.

The string is encoded as UTF-8 then %x01 is added to each byte. Since %xFF
cannot appear in a UTF-8 encoded string this operation is safe.

The string is terminated with a null byte.

Bytes
-----

Byte arrays are encoded so as to avoid bytes in the range %x00-7F.

Bytes are encoded using a base128 encoding:

Encoding

    xxxxxxxx yyyyyyyy zzzzzzzz aaaaaaaa bbbbbbbb cccccccc dddddddd
    1xxxxxxx 1xyyyyyy 1yyzzzzz 1zzzaaaa 1aaaabbb 1bbbbbcc 1ccccccd 1ddddddd

Decoding

    1wwwwwww 1xxxxxxx 1yyyyyyy 1zzzzzzz 1aaaaaaa 1bbbbbbb 1ccccccc 1ddddddd
             wwwwwwwx xxxxxxyy yyyyyzzz zzzzaaaa aaabbbbb bbcccccc cddddddd



Lists
-----



