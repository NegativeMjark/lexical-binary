lexical-binary
==============

A lexicographic binary encoding. Encode strings, bytearrays, integers, lists in 
a compact binary form preserving lexicographic sorting order.

Encoding
========

Each value starts with a byte in the range %x00-%x7F indicating the type.

| Code | Type             |
| ---- | -----------------|
| 0x01 | End of List      |
| 0x10 | None             |
| 0x11 | False            |
| 0x12 | True             |
| 0x20 | Bytes            |
| 0x21 | Start of List    |
| 0x22 | String           |
| 0x23 | Float            |
| 0x24 | Negative Integer |
| 0x25 | Positive Integer |

Strings
-------

Unicode strings are null terminated encoded using a form of [][UTF-8] modified 
to avoid embedded %x00 null bytes.

Strings begin with a single %x22 byte and end with a single %x00 null byte.

The string is encoded as UTF-8 then one is added to each byte. Since %xFF cannot
appear in a UTF-8 encoded string this operation is safe.

Bytes
-----

Byte arrays are encoded so as to avoid bytes in the range %x00-7F.

Byte arrays begin with a single %x20 byte and end with a single %x00 null byte.

Bytes are encoded using a base128 encoding:

Encoding

   xxxxxxxx yyyyyyyy zzzzzzzz aaaaaaaa bbbbbbbb cccccccc dddddddd
   1xxxxxxx 1xyyyyyy 1yyzzzzz 1zzzaaaa 1aaaabbb 1bbbbbcc 1ccccccd 1ddddddd

Decoding

   1wwwwwww 1xxxxxxx 1yyyyyyy 1zzzzzzz 1aaaaaaa 1bbbbbbb 1ccccccc 1ddddddd
            wwwwwwwx xxxxxxyy yyyyyzzz zzzzaaaa aaabbbbb bbcccccc cddddddd


Integers
--------

Positive integers are encoded using a self delminating encoding using a high 
continuation bit. Each integer is encoded as a sequence of bytes with the
continuation bit set followed by a single byte with the continuation bit unset.
Integers must be encoded using the shortest possible encoding.

    +-------------------------+------------------------------+
    | 0x00000000 - 0x0000007F | 0xxxxxxx                     |
    | 0x00000080 - 0x00003FFF | 1xxxxxxx 0xxxxxxx            |
    | 0x00004000 - 0x001FFFFF | 1xxxxxxx 1xxxxxxx 0xxxxxxxx  |
    | ...                     | ...                          |
    +-------------------------+------------------------------+

Positive integers begin with a single %x25 byte followed by the above encoding
ending with a byte with the high bit unset.

Negative integers begin with a single %x24 byte followed by the bitwise 
complement of the encoding of 0 - (value + 1) ending with a byte with the high 
bit set.
 

Lists
-----

Lists are encoded with a %x21 byte followed by one or more values followed by a
single %x01 byte.


Floats
------

Floats are encoded in a modified big endian IEEE 754 double-precision binary 64 
bit floating-point format. If the float is positive then the number is stored 
with the sign bit set on. If the float is negative then the bitwise complement
of the float is stored.

Floats begin with a single %x23 byte which is followed by 8 bytes.

Lexicographic comparison of this encoding will be slightly different to IEEE 
floats: -0 will sort before 0, NAN will sort after INF, and -NAN will sort 
before -INF.


[UTF-8]: http://tools.ietf.org/html/rfc3629 (
    UTF-8, a transformation format of ISO 10646
)


