lexical-binary
==============

A lexicographic binary encoding. Encode strings, bytes, and numbers
and lists in a compact binary form preserving lexicographic sorting order.


TODO
----

 * Handle dictionaries and sets (What would a sensible ordering be for them?)


Encoding
========

All values start with a two bit major type.

  +----+----------------------+
  | 00 | Negative Not Numbers |
  | 01 | Negative Numbers     |
  | 10 | Positive Numbers     |
  | 11 | Positive Not Numbers |
  +----+----------------------+

Numbers
-------

Numbers are encoded as a continued fraction:

    a_0 + (1 / (a_1 + (1 / a_2 .....

Each integer term in the fraction is encoded as a binary exponent and
a mantissa:

    a_n = 2 ^ e_n + m_n

The number of bytes needed to encode the exponent is encoded as a unary
prefix. The exponent follows in binary. The mantissa is encoded with the
most significant bits first, and is truncated if the remaining bits are
zero.

As a special case if the integer is smaller than the remaining bits in the
first byte then then no exponent is encoded and the term itself is encoded
in the remaining bits.

For positive numbers the first term starts with the major type of 10
If the integer less than 16 then the integer and a continued fraction bit
is encoded in first byte:

     0 1 2 3 4 5 6 7
    +-+-+-+-------+-+
    |1|0|0| Value |C|
    +-+-+-+-------+-+

    Value:
        A four bit integer.
    Continued Fraction Flag: C
        Whether this is the last term of the continued fraction.

Otherwise the first byte starts encoding the exponent.

    +-----------------------------------------------------------------+
    | 1010xxxx                                                        |
    | 10110xxx xxxxxxxx                                               |
    | 101110xx xxxxxxxx xxxxxxxx                                      |
    | 1011110x xxxxxxxx xxxxxxxx xxxxxxxx                             |
    | 10111110 xxxxxxxx xxxxxxxx xxxxxxxx xxxxxxxx                    |
    | 10111111 0xxxxxxx xxxxxxxx xxxxxxxx xxxxxxxx xxxxxxxx           |
    | 10111111 10xxxxxx xxxxxxxx xxxxxxxx xxxxxxxx xxxxxxxx xxxxxxxx  |
    | ...                                                             |
    +-----------------------------------------------------------------+

This encoding can be extended to encode any size of exponent. The exponent
is followed by the mantissa bytes:


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

Practically speaking most numbers encountered in typical programs will encode
using one of the following forms:

  +----------------------------------------+-----------------+---------------+
  | 100xxxxc                               |  value < 2^4    | max 1 byte    |
  | 1010yyyy           [xxxxxx1x] xxxxxx0c |  value < 2^16   | max 4 bytes   |
  | 10110yyy  yyyyyyyy [xxxxxx1x] xxxxxx0c |  value < 2^2048 | max 293 bytes |
  +----------------------------------------+-----------------+---------------+


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



