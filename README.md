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

The first bit of every value is a flag to indicate if the previous value was
a continued fraction. The second bit indicates whether this value is positive
or negative. Negative values are encoded in the same way as postive values but
with the meaning of the bits inverted. This means that negative numbers with
bigger magnitudes sort before negative numbers with smaller magnitudes.

Postive numbers are encoded as an integer, an exponent and a continued fraction.

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
    | C1110111  | * bytes | 2^64 or more   | 0x77 [a_0] 0x00                  |
    +-----------+---------+----------------+----------------------------------+

        Continued Fraction Flag (C):
            This is 0 if the previous number was positive or 1 if the previous
            number was negative. This allows allows us to distinguish this byte
            from the start of a continued fraction.


###Lexicograhic Bit Stream Encoding

Numbers greater than 2^64 and continued fractions are encoded using variable
length sequences of bits. Theses bit streams are encoded as a sequence of bytes
which do not include 0xFF or 0x00 followed by a terminating 0xFF or 0x00.
Whether a sequnce is terminated by 0xFF or 0x00 depends on context, sometimes
shorter sequences should sort before longer sequences, sometimes the converse.

Encode a sequence of bits a bigendian number by setting the high bit of the
first byte to the first bit, the lower bits to the subsequent bits. If this
would write a 0x00, 0x01, 0xFE or 0xFF then write a 0x01 or 0xFE byte and write
the eigth bit as the high bit of the next byte and shift the rest of the input
by one.

    +---------------+----------------+
    | Input         | Output         |
    +---------------+----------------+
    | 0000000x y... | 00000001 xy... |
    | xxxxxxxx y... | xxxxxxxx y...  |
    | 1111111x y... | 11111110 xy... |
    +---------------+----------------+

Sequences are truncated if all the remaing bits match the terminating
character.

At the end of the input pad out the bits to the nearest byte by adding ones if
the terminator is 0xFF, or zeros if the terminator is 0x00. If the resulting
final byte is 0xFF or 0x00 then stop otherwise add a 0x00 or 0xFF byte.

### Encoding Integers Less than 2^64

Small integers are encoded either directly in the initial bytes, or as a N-byte
bigendian unsigned integer following the first byte.

Numbers less than 32 are encoded directly into the first byte. Numbers less
than 2048 are encoded directly in the first two bytes.

Otherwise the intial byte indicates the number of subsequent bytes and the
number is encoded as a N-byte bigendian integer.

### Encoding Integers Greater than 2^64

Bigger integers are encoded as a stream of bits using a doubled exp-golomb
encoding. The number is converted to the form:

        2 ^ (2 ^ a + b - 1) + c

where ``b < 2 ^ a`` and ``c < 2 ^ (2 ^ a + b)``. Then a is encoded in unary,
then b and c are encoded in binary as bigendian a-bit and ``(2^a+b)``-bit
integers. Then the trailing zero bits are discarded.

    +------------------+--------------------------+---------------------------+
    |  1  ->  0        |   64  ->  11011          | 2 ^   63  ->  111111      |
    |  2  ->  1        |  100  ->  110111001      | 2 ^  127  ->  1111111     |
    |  3  ->  1001     |  256  ->  1110001        | 2 ^  255  ->  11111111    |
    |  5  ->  10101    | 1000  ->  1110010111101  | 2 ^ 1023  ->  1111111111  |
    |  8  ->  11       | 1024  ->  1110011        |                           |
    | 10  ->  1100001  | 4000  ->  1110100111101  |                           |
    | 16  ->  11001    | 4096  ->  1110101        |                           |
    +------------------+--------------------------+---------------------------+

This encodes numbers of the form ``(2 ^ n) * m`` efficiently when m is small.
For example the largest 64 bit floating point ``(2 ^ 971) * (2 ^ 53 - 1)``
takes only 73 bits to encode.

When the sequence is encoded as bytes it is terminated with 0x00.

## Encoding Continued Fractions

If the number is an integer then no continued fraction is present. The high bit
of the first byte of the next value will be 0.

Continued fractions are encoded as a stream of bits using a sequence of single
exp-golomb encodings. First a 1 bit is writen to indicate the presence of a
continued fraction. Then the terms of the sequence are converted to the form:

    2 ^ a + b

where ``b < 2 ^ a``. Then a is written in unary, then b is written in binary as
a bigendian a-bit integer.

The first term of the contined fraction is a exponent. If the first term is
bigger then the actual value of fraction needs to be smaller. Therefore the
encoding of the first term is encoded as the bitwise complement of the
exp-golomb encoding. If the first term is the last term of the sequence then
when the sequence is encoded as bytes it is terminated with 0x00.

Then the terms of the fraction:

    1 / a_1 + (1 / (a_2 + (1 / (a_3 + (1 /...

are encoded. The odd terms, ``a_(2*n+1)``, are encoded as the bitwise
complement of their exp-golomb encoding. If the last term of the fraction is an
odd term then when the sequence is encoded as bytes it is terminated with 0xFF.
The even terms, ``a_(2*n)`` are encoded directly as their exp-golomb encoding.
If the last term of the fraction is an even term then when the sequence is
encoded as bytes it is terminated with 0x00.

    1/2   ->  2^-1                     ->  0xC000
    1/3   ->  2^-2*(1+1/3)             ->  0xA5FF
    1/5   ->  2^-3*(1+1/(1+1/(1+1/2))) ->  0xA9FF
    5/7  ->   2^-1*(1+1/(2+1/3))       ->  0xDD00

This encodes numbers of the form ``(2 ^ -n) * (a / b)`` efficiently when a and
b are small.

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



