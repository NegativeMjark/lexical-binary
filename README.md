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


Numbers are encoded as an exponent and a continued fraction.

    a_0 + 2^-n_1 * (1 / a_1 + (1 / a_2 ...

For positive numbers the first byte is one of:

    +-----------+---------+----------------+----------------------------------+
    | C1000000  |         |                |                                  |
    |    to     | 1 byte  | 0 to 31        | 0x40 + a_0                       |
    | C1011111  |         |                |                                  |
    +-----------+---------+----------------+----------------------------------+
    | C1100000  |         |                |                                  |
    |    to     | 2 bytes | 32 to 2047     | 0x6000 + a_0                     |
    | C1101111  |         |                |                                  |
    +-----------+---------+----------------+----------------------------------+
    | C1110000  | 3 bytes |                | Let m = ceil(log256(a_0))        |
    |    to     |    to   | 2048 to 2^64-1 |  in ((0x70+m-2) << 8*m) + a_0    |
    | C1110110  | 9 bytes |                |                                  |
    +-----------+---------+----------------+----------------------------------+
    | C1110111  | * bytes | 2^64 or more   | 0x77 [log2(a_0)] 0x00 [a_0] 0x00 |
    +-----------+---------+----------------+----------------------------------+

        Continued Fraction Flag (C):
            This is 0 if the previous number was positive or 1 if the previous
            number was negative. This allows allows us to distinguish this byte
            from the start of a continued fraction.


The bit sequences for numbers between zero and one, numbers greater than 2^64
or continued fractions are escaped to avoid encoding 0xFF or 0x00.

    +---------------+----------------+
    | Input         | Output         |
    +---------------+----------------+
    | 0000000x y... | 00000001 xy... |
    | xxxxxxxx y... | xxxxxxxx y...  |
    | 1111111x y... | 11111110 xy... |
    +---------------+----------------+






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



