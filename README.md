# icctool

A simple ICC Profile parser/generator in python.

icctool can parse, edit, and write an ICC Profile, per
[ICC.1:2022-05](https://www.color.org/specification/ICC.1-2022-05.pdf).
ICC profiles must be in binary format (starting with the header).

Right now the only edition feature allows removing copyrightTag elements.


# Operation

(1) parse ICC profile.
```
$ ./icctool.py samsung.bin
```

(2) print ICC profile in text format.
```
$ ./icctool.py --print samsung.bin
profile_size: 0x278 preferred_cmm_type: 0 profile_version_number: 4.3.0 profile_device_class: 'mntr' color_space: 'RGB ' profile_connection_space: 'XYZ ' date_and_time: 2022-07-01T00:00:00 profile_file_signature: 'acsp' primary_platform_signature: 'SEC' profile_flags: 0 device_manufacturer: 0x53454300 device_model: 0 device_attributes: b'\x00\x00\x00\x00\x00\x00\x00\x00' rendering_intent: 0 xyz_illuminant: b'\x00\x00\xf6\xd6\x00\x01\x00\x00\x00\x00\xd3-' profile_creator_field: 1397048064 profile_id: b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' reserved: b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' tag_count: 10 tag_table [ ( signature: 'desc' offset: 0xfc ) ( signature: 'cprt' offset: 0x160 ) ( signature: 'wtpt' offset: 0x1dc ) ( signature: 'chad' offset: 0x1f0 ) ( signature: 'rXYZ' offset: 0x21c ) ( signature: 'gXYZ' offset: 0x230 ) ( signature: 'bXYZ' offset: 0x244 ) ( signature: 'rTRC' offset: 0x258 ) ( signature: 'gTRC' offset: 0x258 ) ( signature: 'bTRC' offset: 0x258 ) ] elements { 252: tag { size: 100 signature: 'mluc' reserved: 0 number_of_names: 1 names [ ( name_record_size: '12' language_code: en country_code: US length: 70 offset: 28 content: 'DCI-P3 D65 Gamut with sRGB Transfer' ) ] } 352: tag { size: 124 signature: 'mluc' reserved: 0 number_of_names: 1 names [ ( name_record_size: '12' language_code: en country_code: US length: 96 offset: 28 content: 'Copyright (c) 2022 Samsung Electronics Co., Ltd.' ) ] } 476: tag { size: 20 signature: 'XYZ ' reserved: 0 numbers { (0.964202880859375, 1.0, 0.8249053955078125) } } 496: tag { size: 44 signature: 'sf32' reserved: 0 numbers { (1, 3133) (0, 1500) (-1, 62251) (0, 1936) (0, 64912) (-1, 64419) (-1, 64931) (0, 986) (0, 49292) } } 540: tag { size: 20 signature: 'XYZ ' reserved: 0 numbers { (0.51507568359375, 0.2411651611328125, -0.0010528564453125) } } 560: tag { size: 20 signature: 'XYZ ' reserved: 0 numbers { (0.2919464111328125, 0.692230224609375, 0.0418853759765625) } } 580: tag { size: 20 signature: 'XYZ ' reserved: 0 numbers { (0.1571807861328125, 0.06658935546875, 0.7845458984375) } } 600: tag { size: 32 signature: 'para' reserved: 0 encoded_value: 3 reserved2: 0 parameters { (2, 26214) (0, 62119) (0, 3417) (0, 5072) (0, 2651) } } }
```

(3) write ICC profile in binary format.
```
$ ./icctool.py --write samsung.bin /tmp/out.bin
$ diff samsung.bin /tmp/out.bin
$
```


(4) remove the copyrightTag element, and write the output in binary format
```
$ ./icctool.py --write --remove-copyright samsung.bin /tmp/out.bin
$ diff samsung.bin /tmp/out.bin
Binary files samsung.bin and /tmp/out.bin differ
$ diff <(xxd samsung.bin) <(xxd /tmp/out.bin)
1c1
< 00000000: 0000 0278 0000 0000 0430 0000 6d6e 7472  ...x.....0..mntr
---
> 00000000: 0000 01f8 0000 0000 0430 0000 6d6e 7472  .........0..mntr
9,40c9,31
< 00000080: 0000 000a 6465 7363 0000 00fc 0000 0064  ....desc.......d
< 00000090: 6370 7274 0000 0160 0000 007c 7774 7074  cprt...`...|wtpt
< 000000a0: 0000 01dc 0000 0014 6368 6164 0000 01f0  ........chad....
< 000000b0: 0000 002c 7258 595a 0000 021c 0000 0014  ...,rXYZ........
< 000000c0: 6758 595a 0000 0230 0000 0014 6258 595a  gXYZ...0....bXYZ
< 000000d0: 0000 0244 0000 0014 7254 5243 0000 0258  ...D....rTRC...X
< 000000e0: 0000 0020 6754 5243 0000 0258 0000 0020  ... gTRC...X... 
< 000000f0: 6254 5243 0000 0258 0000 0020 6d6c 7563  bTRC...X... mluc
< 00000100: 0000 0000 0000 0001 0000 000c 656e 5553  ............enUS
< 00000110: 0000 0046 0000 001c 0044 0043 0049 002d  ...F.....D.C.I.-
< 00000120: 0050 0033 0020 0044 0036 0035 0020 0047  .P.3. .D.6.5. .G
< 00000130: 0061 006d 0075 0074 0020 0077 0069 0074  .a.m.u.t. .w.i.t
< 00000140: 0068 0020 0073 0052 0047 0042 0020 0054  .h. .s.R.G.B. .T
< 00000150: 0072 0061 006e 0073 0066 0065 0072 0000  .r.a.n.s.f.e.r..
< 00000160: 6d6c 7563 0000 0000 0000 0001 0000 000c  mluc............
< 00000170: 656e 5553 0000 0060 0000 001c 0043 006f  enUS...`.....C.o
< 00000180: 0070 0079 0072 0069 0067 0068 0074 0020  .p.y.r.i.g.h.t. 
< 00000190: 0028 0063 0029 0020 0032 0030 0032 0032  .(.c.). .2.0.2.2
< 000001a0: 0020 0053 0061 006d 0073 0075 006e 0067  . .S.a.m.s.u.n.g
< 000001b0: 0020 0045 006c 0065 0063 0074 0072 006f  . .E.l.e.c.t.r.o
< 000001c0: 006e 0069 0063 0073 0020 0043 006f 002e  .n.i.c.s. .C.o..
< 000001d0: 002c 0020 004c 0074 0064 002e 5859 5a20  .,. .L.t.d..XYZ 
< 000001e0: 0000 0000 0000 f6d6 0001 0000 0000 d32d  ...............-
< 000001f0: 7366 3332 0000 0000 0001 0c3d 0000 05dc  sf32.......=....
< 00000200: ffff f32b 0000 0790 0000 fd90 ffff fba3  ...+............
< 00000210: ffff fda3 0000 03da 0000 c08c 5859 5a20  ............XYZ 
< 00000220: 0000 0000 0000 83dc 0000 3dbd ffff ffbb  ..........=.....
< 00000230: 5859 5a20 0000 0000 0000 4abd 0000 b136  XYZ ......J....6
< 00000240: 0000 0ab9 5859 5a20 0000 0000 0000 283d  ....XYZ ......(=
< 00000250: 0000 110c 0000 c8d8 7061 7261 0000 0000  ........para....
< 00000260: 0003 0000 0002 6666 0000 f2a7 0000 0d59  ......ff.......Y
< 00000270: 0000 13d0 0000 0a5b                      .......[
---
> 00000080: 0000 0009 6465 7363 0000 00f0 0000 0064  ....desc.......d
> 00000090: 7774 7074 0000 0154 0000 0014 6368 6164  wtpt...T....chad
> 000000a0: 0000 0168 0000 002c 7258 595a 0000 0194  ...h...,rXYZ....
> 000000b0: 0000 0014 6758 595a 0000 01a8 0000 0014  ....gXYZ........
> 000000c0: 6258 595a 0000 01bc 0000 0014 7254 5243  bXYZ........rTRC
> 000000d0: 0000 01d0 0000 0020 6754 5243 0000 01d0  ....... gTRC....
> 000000e0: 0000 0020 6254 5243 0000 01d0 0000 0020  ... bTRC....... 
> 000000f0: 6d6c 7563 0000 0000 0000 0001 0000 000c  mluc............
> 00000100: 656e 5553 0000 0046 0000 001c 0044 0043  enUS...F.....D.C
> 00000110: 0049 002d 0050 0033 0020 0044 0036 0035  .I.-.P.3. .D.6.5
> 00000120: 0020 0047 0061 006d 0075 0074 0020 0077  . .G.a.m.u.t. .w
> 00000130: 0069 0074 0068 0020 0073 0052 0047 0042  .i.t.h. .s.R.G.B
> 00000140: 0020 0054 0072 0061 006e 0073 0066 0065  . .T.r.a.n.s.f.e
> 00000150: 0072 0000 5859 5a20 0000 0000 0000 f6d6  .r..XYZ ........
> 00000160: 0001 0000 0000 d32d 7366 3332 0000 0000  .......-sf32....
> 00000170: 0001 0c3d 0000 05dc ffff f32b 0000 0790  ...=.......+....
> 00000180: 0000 fd90 ffff fba3 ffff fda3 0000 03da  ................
> 00000190: 0000 c08c 5859 5a20 0000 0000 0000 83dc  ....XYZ ........
> 000001a0: 0000 3dbd ffff ffbb 5859 5a20 0000 0000  ..=.....XYZ ....
> 000001b0: 0000 4abd 0000 b136 0000 0ab9 5859 5a20  ..J....6....XYZ 
> 000001c0: 0000 0000 0000 283d 0000 110c 0000 c8d8  ......(=........
> 000001d0: 7061 7261 0000 0000 0003 0000 0002 6666  para..........ff
> 000001e0: 0000 f2a7 0000 0d59 0000 13d0 0000 0a5b  .......Y.......[
```

