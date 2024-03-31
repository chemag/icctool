#!/usr/bin/env python
# Copyright (c) Meta, Inc. and its affiliates.

"""icctool: An ICC Profile Parser/Generator.

This module can parse, edit, and write an ICC Profile, per
[ICC.1:2022-05](https://www.color.org/specification/ICC.1-2022-05.pdf).

Right now the only edition feature allows removing copyrightTag elements.
"""


import argparse
import json
import string
import struct
import sys

from _version import __version__


default_values = {
    "debug": 0,
    "remove_copyright": False,
    "print": False,
    "json": False,
    "short": True,
    "as_one_line": True,
    "force_version_number": None,
    "write": False,
    "infile": None,
    "outfile": None,
}

# decode a bytes string into a string containing only characters
# from the POSIX portable filename character set. For all other
# characters, use "\\x%02x".
#
# The Open Group Base Specifications Issue 7, 2018 edition
# IEEE Std 1003.1-2017 (Revision of IEEE Std 1003.1-2008)
#
# 3.282 Portable Filename Character Set
#
# The set of characters from which portable filenames are constructed.
#
# A B C D E F G H I J K L M N O P Q R S T U V W X Y Z
# a b c d e f g h i j k l m n o p q r s t u v w x y z
# 0 1 2 3 4 5 6 7 8 9 . _ -
#
# The last three characters are the <period>, <underscore>, and
# <hyphen-minus> characters, respectively. See also Pathname.
PORTABLE_FILENAME_CHARACTER_SET = list(
    string.ascii_uppercase + string.ascii_lowercase + string.digits + "._-"
)


def escape_string(str_in):
    str_out = "".join(
        c if c in PORTABLE_FILENAME_CHARACTER_SET else f"\\x{ord(c):02x}"
        for c in str_in
    )
    return str_out


def escape_bin(bin_in):
    str_out = "".join(
        chr(c) if chr(c) in PORTABLE_FILENAME_CHARACTER_SET else f"\\x{c:02x}"
        for c in bin_in
    )
    return str_out


TABSTR = "  "


"""
The structure of an ICC Profile blob is:
- icc profile header [128 bytes]
- tag table
- tagged element data
"""


class ICCHeader:
    @classmethod
    def parse_VersionNumber(cls, blob):
        profile_version_number = struct.unpack(">I", blob)[0]
        major = (profile_version_number >> 24) & 0xFF
        minor = (profile_version_number >> 20) & 0x0F
        bug_fix = (profile_version_number >> 16) & 0x0F
        rem = profile_version_number & 0xFFFF
        return (major, minor, bug_fix, rem)

    def str_VersionNumber(self):
        major, minor, bug_fix, rem = self.profile_version_number
        return f"{major}.{minor}.{bug_fix}"

    def set_VersionNumber(self, version_str):
        major, minor, bug_fix = [int(v) for v in version_str.split(".")]
        rem = 0
        self.profile_version_number = (major, minor, bug_fix, rem)

    def pack_VersionNumber(self):
        major, minor, bug_fix, rem = self.profile_version_number
        return self.dopack_VersionNumber(major, minor, bug_fix, rem)

    @classmethod
    def dopack_VersionNumber(cls, major, minor, bug_fix, rem):
        version_number_format = "!BBH"
        second_byte = (minor << 4) | bug_fix
        version_number = struct.pack(version_number_format, major, second_byte, rem)
        return version_number

    @classmethod
    def parse_dateTimeNumber(cls, blob):
        i = 0
        year = struct.unpack(">H", blob[i : i + 2])[0]
        i += 2
        month = struct.unpack(">H", blob[i : i + 2])[0]
        i += 2
        day = struct.unpack(">H", blob[i : i + 2])[0]
        i += 2
        hour = struct.unpack(">H", blob[i : i + 2])[0]
        i += 2
        minute = struct.unpack(">H", blob[i : i + 2])[0]
        i += 2
        sec = struct.unpack(">H", blob[i : i + 2])[0]
        i += 2
        return (year, month, day, hour, minute, sec)

    def str_dateTimeNumber(self):
        year, month, day, hour, minute, sec = self.date_and_time
        return f"{year}-{month:02}-{day:02}T{hour:02}:{minute:02}:{sec:02}"

    def pack_dateTimeNumber(self):
        year, month, day, hour, minute, sec = self.date_and_time
        date_and_time_format = "!HHHHHH"
        date_and_time = struct.pack(
            date_and_time_format, year, month, day, hour, minute, sec
        )
        return date_and_time

    @classmethod
    def parse(cls, blob, force_version_number):
        header = ICCHeader()
        i = 0
        header.profile_size = struct.unpack(">I", blob[i : i + 4])[0]
        i += 4
        header.preferred_cmm_type = struct.unpack(">I", blob[i : i + 4])[0]
        i += 4
        header.profile_version_number = cls.parse_VersionNumber(blob[i : i + 4])
        i += 4
        if force_version_number is not None:
            header.set_VersionNumber(force_version_number)
        header.profile_device_class = blob[i : i + 4].decode("ascii")
        i += 4
        header.color_space = blob[i : i + 4].decode("ascii")
        i += 4
        header.profile_connection_space = blob[i : i + 4].decode("ascii")
        i += 4
        header.date_and_time = cls.parse_dateTimeNumber(blob[i : i + 12])
        i += 12
        header.profile_file_signature = blob[i : i + 4].decode("ascii")
        i += 4
        assert (
            "acsp" == header.profile_file_signature
        ), f"invalid icc header: {header.profile_file_signature} != 'acsp'"
        header.primary_platform_signature = blob[i : i + 4].decode("ascii")
        i += 4
        header.profile_flags = struct.unpack(">I", blob[i : i + 4])[0]
        i += 4
        header.device_manufacturer = struct.unpack(">I", blob[i : i + 4])[0]
        i += 4
        header.device_model = struct.unpack(">I", blob[i : i + 4])[0]
        i += 4
        header.device_attributes = blob[i : i + 8]
        i += 8
        header.rendering_intent = struct.unpack(">I", blob[i : i + 4])[0]
        i += 4
        header.xyz_illuminant = ICCTag.parse_XYZNumber(blob[i : i + 12])
        i += 12
        header.profile_creator_field = struct.unpack(">I", blob[i : i + 4])[0]
        i += 4
        header.profile_id = blob[i : i + 16]
        i += 16
        header.reserved = blob[i : i + 28]
        i += 28
        # assert 0x00 == reserved, "invalid icc header"  # TODO
        return header, i

    def tostring(self, tabsize):
        prefix = " " if tabsize == -1 else ("\n" + TABSTR * tabsize)
        return (
            f"{prefix}profile_size: 0x{self.profile_size:x}"
            f"{prefix}preferred_cmm_type: {self.preferred_cmm_type}"
            f"{prefix}profile_version_number: {self.str_VersionNumber()}"
            f'{prefix}profile_device_class: "{self.profile_device_class}"'
            f'{prefix}color_space: "{self.color_space}"'
            f'{prefix}profile_connection_space: "{self.profile_connection_space}"'
            f'{prefix}date_and_time: "{self.str_dateTimeNumber()}"'
            f'{prefix}profile_file_signature: "{self.profile_file_signature}"'
            f'{prefix}primary_platform_signature: "{escape_string(self.primary_platform_signature)}"'
            f"{prefix}profile_flags: {self.profile_flags}"
            f"{prefix}device_manufacturer: 0x{self.device_manufacturer:x}"
            f"{prefix}device_model: {self.device_model}"
            f"{prefix}device_attributes: {self.device_attributes}"
            f"{prefix}rendering_intent: {self.rendering_intent}"
            f"{prefix}xyz_illuminant: {ICCTag.str_XYZNumber(self.xyz_illuminant)}"
            f"{prefix}profile_creator_field: {self.profile_creator_field}"
            f"{prefix}profile_id: {self.profile_id}"
            f"{prefix}reserved: {self.reserved}"
        )

    def todict(self):
        d = {}
        d["profile_size"] = self.profile_size
        d["preferred_cmm_type"] = self.preferred_cmm_type
        d["profile_version_number"] = self.str_VersionNumber()
        d["profile_device_class"] = self.profile_device_class
        d["color_space"] = self.color_space
        d["profile_connection_space"] = self.profile_connection_space
        d["date_and_time"] = self.str_dateTimeNumber()
        d["profile_file_signature"] = self.profile_file_signature
        d["primary_platform_signature"] = escape_string(self.primary_platform_signature)
        d["profile_flags"] = self.profile_flags
        d["device_manufacturer"] = self.device_manufacturer
        d["device_model"] = self.device_model
        d["device_attributes"] = escape_bin(self.device_attributes)
        d["rendering_intent"] = self.rendering_intent
        d["xyz_illuminant"] = ICCTag.str_XYZNumber(self.xyz_illuminant)
        d["profile_creator_field"] = self.profile_creator_field
        d["profile_id"] = escape_bin(self.profile_id)
        d["reserved"] = escape_bin(self.reserved)
        return d

    def pack(self):
        version_number_bytes = self.pack_VersionNumber()
        date_and_time_bytes = self.pack_dateTimeNumber()
        header_format = (
            "!"
            + "I"  # profile_size
            + "I"  # preferred_cmm_type
            + str(len(version_number_bytes))
            + "s"
            + str(len(self.profile_device_class))
            + "s"
            + str(len(self.color_space))
            + "s"
            + str(len(self.profile_connection_space))
            + "s"
            + str(len(date_and_time_bytes))
            + "s"
            + str(len(self.profile_file_signature))
            + "s"
            + str(len(self.primary_platform_signature))
            + "s"
            + "I"  # profile_flags
            + "I"  # device_manufacturer
            + "I"  # device_model
            + str(len(self.device_attributes))
            + "s"
            + "I"  # rendering_intent
            + "s"  # xyz_illuminant
            + "I"  # profile_creator_field
            + str(len(self.profile_id))
            + "s"
            + str(len(self.reserved))
            + "s"
        )
        header = struct.pack(
            header_format,
            self.profile_size,
            self.preferred_cmm_type,
            version_number_bytes,
            self.profile_device_class.encode("ascii"),
            self.color_space.encode("ascii"),
            self.profile_connection_space.encode("ascii"),
            date_and_time_bytes,
            self.profile_file_signature.encode("ascii"),
            self.primary_platform_signature.encode("ascii"),
            self.profile_flags,
            self.device_manufacturer,
            self.device_model,
            self.device_attributes,
            self.rendering_intent,
            ICCTag.pack_XYZNumber(self.xyz_illuminant),
            self.profile_creator_field,
            self.profile_id,
            self.reserved,
        )
        return header


# list including the following elements per entry:
# (tag_name, header_signature, (list of allowed tag types))
TAG_HEADER_TABLE = (
    (
        "AToB0Tag",
        "A2B0",
        (
            "lut8Type",
            "lut16Type",
            "lutAToBType",
        ),
    ),
    (
        "AToB1Tag",
        "A2B1",
        (
            "lut8Type",
            "lut16Type",
            "lutAToBType",
        ),
    ),
    (
        "AToB2Tag",
        "A2B2",
        (
            "lut8Type",
            "lut16Type",
            "lutAToBType",
        ),
    ),
    ("blueMatrixColumnTag", "bXYZ", ("XYZType",)),
    (
        "blueTRCTag",
        "bTRC",
        (
            "curveType",
            "parametricCurveType",
        ),
    ),
    (
        "BToA0Tag",
        "B2A0",
        (
            "lut8Type",
            "lut16Type",
            "lutBToAType",
        ),
    ),
    (
        "BToA1Tag",
        "B2A1",
        (
            "lut8Type",
            "lut16Type",
            "lutBToAType",
        ),
    ),
    (
        "BToA2Tag",
        "B2A2",
        (
            "lut8Type",
            "lut16Type",
            "lutBToAType",
        ),
    ),
    ("BToD0Tag", "B2D0", ("multiProcessElementsType",)),
    ("BToD1Tag", "B2D1", ("multiProcessElementsType",)),
    ("BToD2Tag", "B2D2", ("multiProcessElementsType",)),
    ("BToD3Tag", "B2D3", ("multiProcessElementsType",)),
    ("calibrationDateTimeTacalibrationDateTimeTag", "calt", ("dateTimeType",)),
    ("charTargetTag", "targ", ("textType",)),
    ("chromaticAdaptationTag", "chad", ("s15Fixed16ArrayType",)),
    ("chromaticityTag", "chrm", ("chromaticityType",)),
    ("cicpTag", "cicp", ("cicpType",)),
    ("colorantOrderTag", "clro", ("colorantOrderType",)),
    ("colorantTableTag", "clrt", ("colorantTableType",)),
    ("colorantTableOutTag", "clot", ("colorantTableType",)),
    ("colorimetricIntentImageStateTag", "ciis", ("signatureType",)),
    ("copyrightTag", "cprt", ("multiLocalizedUnicodeType",)),
    ("deviceMfgDescTag", "dmnd", ("multiLocalizedUnicodeType",)),
    ("deviceModelDescTag", "dmdd", ("multiLocalizedUnicodeType",)),
    ("DToB0Tag", "D2B0", ("multiProcessElementsType",)),
    ("DToB1Tag", "D2B1", ("multiProcessElementsType",)),
    ("DToB2Tag", "D2B2", ("multiProcessElementsType",)),
    ("DToB3Tag", "D2B3", ("multiProcessElementsType",)),
    (
        "gamutTag",
        "gamt",
        (
            "lut8Type",
            "lut16Type",
            "lutBToAType",
        ),
    ),
    (
        "grayTRCTag",
        "kTRC",
        (
            "curveType",
            "parametricCurveType",
        ),
    ),
    ("greenMatrixColumnTag", "gXYZ", ("XYZType",)),
    (
        "greenTRCTag",
        "gTRC",
        (
            "curveType",
            "parametricCurveType",
        ),
    ),
    ("luminanceTag", "lumi", ("XYZType",)),
    ("measurementTag", "meas", ("measurementType",)),
    ("metadataTag", "meta", ("dictType",)),
    ("mediaBlackPointTag", "bkpt", ("XYZType",)),
    ("mediaWhitePointTag", "wtpt", ("XYZType",)),
    ("namedColor2Tag", "ncl2", ("namedColor2Type",)),
    ("outputResponseTag", "resp", ("responseCurveSet16Type",)),
    ("perceptualRenderingIntentGamutTag", "rig0", ("signatureType",)),
    (
        "preview0Tag",
        "pre0",
        (
            "lut8Type",
            "lut16Type",
            "lutAToBType",
            "lutBToAType",
        ),
    ),
    (
        "preview1Tag",
        "pre1",
        (
            "lut8Type",
            "lut16Type",
            "lutBToAType",
        ),
    ),
    (
        "preview2Tag",
        "pre2",
        (
            "lut8Type",
            "lut16Type",
            "lutBToAType",
        ),
    ),
    ("profileDescriptionTag", "desc", ("multiLocalizedUnicodeType",)),
    ("profileSequenceDescTag", "pseq", ("profileSequenceDescType",)),
    ("profileSequenceIdentifierTag", "psid", ("profileSequenceIdentifierType",)),
    ("redMatrixColumnTag", "rXYZ", ("XYZType",)),
    (
        "redTRCTag",
        "rTRC",
        (
            "curveType",
            "parametricCurveType",
        ),
    ),
    ("saturationRenderingIntentGamutTag", "rig2", ("signatureType",)),
    ("technologyTag", "tech", ("signatureType",)),
    ("viewingCondDescTag", "vued", ("multiLocalizedUnicodeType",)),
    ("viewingConditionsTag", "view", ("viewingConditionsType",)),
)


# list including the following elements per entry:
# (tag_name, element_signature)
TAG_ELEMENT_TABLE = (
    ("textType", "text"),
    ("textDescriptionType", "desc"),
    ("multiLocalizedUnicodeType", "mluc"),
    ("XYZType", "XYZ "),
    ("s15Fixed16ArrayType", "sf32"),
    ("curveType", "curv"),
    ("parametricCurveType", "para"),
    ("chromaticityType", "chrm"),
)


# produces a dictionary with tag signatures as keys, and names as values
def read_tag_header_table(table=TAG_HEADER_TABLE):
    return {signature: name for (name, signature, _) in table}


# produces a dictionary with tag signatures as keys, and names as values
def read_tag_element_table(table=TAG_ELEMENT_TABLE):
    return {signature: name for (name, signature) in table}


class ICCTag:
    header_table = read_tag_header_table()
    element_table = read_tag_element_table()

    @classmethod
    def parse(cls, header_signature, header_offset, header_size, blob, header):
        # check whether the tag signature is known
        if header_signature not in cls.header_table:
            print(f'warning: invalid tag signature: "{header_signature}"')
        # get the element signature
        element_signature = blob[0:4].decode("ascii")
        element_name = cls.element_table.get(element_signature, None)
        parser_name = f"parse_{element_name}"
        if parser_name in dir(cls):
            # run the element parser
            tag = getattr(cls, parser_name)(blob)
        else:
            if parser_name != "parse_None":
                print(
                    f'warning: no parser "{parser_name}()" for header_signature: "{header_signature}" element_signature: "{element_signature}" element_name: "{element_name}"'
                )
            tag = cls.parse_UnimplementedType(blob)
        # add the header info
        tag.header_signature = header_signature
        tag.header_offset = header_offset
        tag.header_size = header_size
        return tag

    def tostring(self, tabsize):
        prefix = " " if tabsize == -1 else ("\n" + TABSTR * tabsize)
        out = f"{prefix}tag {{"
        tabsize += 0 if tabsize == -1 else 1
        prefix = " " if tabsize == -1 else ("\n" + TABSTR * tabsize)
        out += f'{prefix}header_signature: "{self.header_signature}"'
        out += f"{prefix}header_offset: 0x{self.header_offset:x}"
        out += f"{prefix}header_size: {self.header_size}"
        # check whether there is a valid print function
        element_name = self.element_table.get(self.element_signature, None)
        printer_name = f"tostring_{element_name}"
        if printer_name in dir(self):
            # run the element printer
            out += prefix + getattr(self, printer_name)(tabsize).strip()
        else:
            if printer_name != "tostring_None":
                print(f'warning: no printer for tag element: "{element_name}"')
            out += prefix + self.tostring_UnimplementedType(tabsize).strip()
        tabsize -= 0 if tabsize == -1 else 1
        prefix = " " if tabsize == -1 else ("\n" + TABSTR * tabsize)
        out += f"{prefix}}}"
        return out

    def todict(self):
        d = {}
        d["header_signature"] = self.header_signature
        d["header_offset"] = self.header_offset
        d["header_size"] = self.header_size
        # check whether there is a valid print function
        element_name = self.element_table.get(self.element_signature, None)
        printer_name = f"todict_{element_name}"
        if printer_name in dir(self):
            # run the element printer
            d.update(getattr(self, printer_name)())
        else:
            if printer_name != "todict_None":
                print(f'warning: no printer for tag element: "{element_name}"')
            d.update(self.todict_UnimplementedType())
        return d

    def pack(self):
        # check whether there is a valid pack function
        element_name = self.element_table.get(self.element_signature, None)
        pack_name = f"pack_{element_name}"
        if pack_name in dir(self):
            # run the element packer
            return getattr(self, pack_name)()
        else:
            if pack_name != "pack_None":
                print(f'warning: no packer for tag element: "{element_name}"')
            return self.pack_UnimplementedType()

    # element parsers
    @classmethod
    def parse_UnimplementedType(cls, blob):
        tag = ICCTag()
        tag.element_size = len(blob)
        i = 0
        tag.element_signature = blob[i : i + 4].decode("ascii")
        tag.remaining = blob[i:]
        return tag

    @classmethod
    def parse_textType(cls, blob):
        tag = ICCTag()
        tag.element_size = len(blob)
        i = 0
        tag.element_signature = blob[i : i + 4].decode("ascii")
        i += 4
        tag.reserved = struct.unpack(">I", blob[i : i + 4])[0]
        i += 4
        tag.text = blob[i:].decode("ascii")
        return tag

    @classmethod
    def parse_chromaticityType(cls, blob):
        tag = ICCTag()
        tag.element_size = len(blob)
        i = 0
        tag.element_signature = blob[i : i + 4].decode("ascii")
        i += 4
        tag.reserved = struct.unpack(">I", blob[i : i + 4])[0]
        i += 4
        tag.num_device_channels = struct.unpack(">H", blob[i : i + 2])[0]
        i += 2
        tag.phosphor_colorant_type = struct.unpack(">H", blob[i : i + 2])[0]
        i += 2
        tag.cie_xy_coordinates = []
        for _ in range(tag.num_device_channels):
            cie_xy_coordinate_x = cls.parse_u16Fixed16Number(blob[i : i + 4])
            i += 4
            cie_xy_coordinate_y = cls.parse_u16Fixed16Number(blob[i : i + 4])
            i += 4
            tag.cie_xy_coordinates.append((cie_xy_coordinate_x, cie_xy_coordinate_y))
        return tag

    @classmethod
    def parse_curveType(cls, blob):
        tag = ICCTag()
        tag.element_size = len(blob)
        i = 0
        tag.element_signature = blob[i : i + 4].decode("ascii")
        i += 4
        tag.reserved = struct.unpack(">I", blob[i : i + 4])[0]
        i += 4
        tag.curve_count = struct.unpack(">I", blob[i : i + 4])[0]
        i += 4
        tag.curve_value = []
        for _ in range(tag.curve_count):
            tag.curve_value.append(struct.unpack(">H", blob[i : i + 2])[0])
            i += 2
        return tag

    @classmethod
    def parse_textDescriptionType(cls, blob):
        tag = ICCTag()
        tag.element_size = len(blob)
        i = 0
        tag.element_signature = blob[i : i + 4].decode("ascii")
        i += 4
        tag.reserved = struct.unpack(">I", blob[i : i + 4])[0]
        i += 4
        tag.ascii_length = struct.unpack(">I", blob[i : i + 4])[0]
        i += 4
        tag.ascii_invariant_description = (
            struct.unpack(f">{tag.ascii_length}s", blob[i : i + tag.ascii_length])[0]
            .decode("ascii")
            .strip("\x00")
        )
        i += tag.ascii_length
        tag.unicode_language_code = struct.unpack(">I", blob[i : i + 4])[0]
        i += 4
        tag.unicode_length = struct.unpack(">I", blob[i : i + 4])[0]
        i += 4
        tag.unicode_localizable_description = blob[i : i + tag.unicode_length]
        i += tag.unicode_length
        tag.scriptcode_code = struct.unpack(">H", blob[i : i + 2])[0]
        i += 2
        tag.macintosh_length = struct.unpack(">B", blob[i : i + 1])[0]
        i += 1
        tag.macintosh_description = blob[i : i + 67]
        i += 67
        # keep the remaining buffer
        tag.rem = blob[i:]
        return tag

    @classmethod
    def parse_s15Fixed16Number(cls, blob):
        # get the s15Fixed part
        s15Fixed = struct.unpack(">h", blob[0:2])[0]
        # get the u16Frac part
        u16Frac = struct.unpack(">H", blob[2:4])[0]
        return (s15Fixed, u16Frac)

    @classmethod
    def parse_u16Fixed16Number(cls, blob):
        # get the u16Fixed part
        u16Fixed = struct.unpack(">H", blob[0:2])[0]
        # get the u16Frac part
        u16Frac = struct.unpack(">H", blob[2:4])[0]
        return (u16Fixed, u16Frac)

    @classmethod
    def parse_XYZType(cls, blob):
        tag = ICCTag()
        tag.element_size = len(blob)
        i = 0
        tag.element_signature = blob[i : i + 4].decode("ascii")
        assert (
            "XYZ " == tag.element_signature
        ), f"invalid XYZType signature ({tag.element_signature})"
        i += 4
        tag.reserved = struct.unpack(">I", blob[i : i + 4])[0]
        i += 4
        # read the XYZ numbers
        tag.numbers = []
        while i < len(blob):
            tag.numbers.append((cls.parse_XYZNumber(blob[i:])))
            i += 12
        return tag

    @classmethod
    def parse_XYZNumber(cls, blob):
        # s15Fixed16Number
        i = 0
        cie_x = cls.parse_s15Fixed16Number(blob[i : i + 4])
        i += 4
        cie_y = cls.parse_s15Fixed16Number(blob[i : i + 4])
        i += 4
        cie_z = cls.parse_s15Fixed16Number(blob[i : i + 4])
        i += 4
        return cie_x, cie_y, cie_z

    @classmethod
    def parse_multiLocalizedUnicodeType(cls, blob):
        tag = ICCTag()
        tag.element_size = len(blob)
        i = 0
        tag.element_signature = blob[i : i + 4].decode("ascii")
        i += 4
        tag.reserved = struct.unpack(">I", blob[i : i + 4])[0]
        i += 4
        tag.number_of_names = struct.unpack(">I", blob[i : i + 4])[0]
        i += 4
        # read the tag names
        tag.names = []
        for name_index in range(tag.number_of_names):
            name_record_size = struct.unpack(">I", blob[i : i + 4])[0]
            i += 4
            language_code = blob[i : i + 2].decode("ascii")
            i += 2
            country_code = blob[i : i + 2].decode("ascii")
            i += 2
            length = struct.unpack(">I", blob[i : i + 4])[0]
            i += 4
            offset = struct.unpack(">I", blob[i : i + 4])[0]
            i += 4
            content = blob[offset : offset + length].decode("utf-16be")
            i += length
            tag.names.append(
                (name_record_size, language_code, country_code, length, offset, content)
            )
        # keep the remaining buffer
        tag.rem = blob[i:]
        return tag

    @classmethod
    def parse_s15Fixed16ArrayType(cls, blob):
        tag = ICCTag()
        tag.element_size = len(blob)
        i = 0
        tag.element_signature = blob[i : i + 4].decode("ascii")
        i += 4
        tag.reserved = struct.unpack(">I", blob[i : i + 4])[0]
        i += 4
        # read the XYZ numbers
        tag.numbers = []
        while i < len(blob):
            # s15Fixed16Number
            number = cls.parse_s15Fixed16Number(blob[i : i + 4])
            i += 4
            tag.numbers.append(number)
        return tag

    @classmethod
    def parse_parametricCurveType(cls, blob):
        tag = ICCTag()
        tag.element_size = len(blob)
        i = 0
        tag.element_signature = blob[i : i + 4].decode("ascii")
        i += 4
        tag.reserved = struct.unpack(">I", blob[i : i + 4])[0]
        i += 4
        tag.encoded_value = struct.unpack(">H", blob[i : i + 2])[0]
        i += 2
        tag.reserved2 = struct.unpack(">H", blob[i : i + 2])[0]
        i += 2
        NUM_PARAMETERS = {
            0: 1,
            1: 3,
            2: 4,
            3: 5,
            4: 7,
        }
        num_parameters = NUM_PARAMETERS[tag.encoded_value]
        tag.parameters = []
        for par_index in range(num_parameters):
            number = cls.parse_s15Fixed16Number(blob[i : i + 4])
            i += 4
            tag.parameters.append(number)
        return tag

    # element printers
    def tostring_UnimplementedType(self, tabsize):
        prefix = " " if tabsize == -1 else ("\n" + TABSTR * tabsize)
        out = ""
        out += f"{prefix}element_size: {self.element_size}"
        out += f'{prefix}element_signature: "{self.element_signature}"'
        out += f'{prefix}remaining: "{self.remaining}"'
        return out

    def todict_UnimplementedType(self):
        d = {}
        d["element_size"] = self.element_size
        d["element_signature"] = self.element_signature
        d["remaining"] = self.remaining
        return d

    def tostring_textType(self, tabsize):
        prefix = " " if tabsize == -1 else ("\n" + TABSTR * tabsize)
        out = ""
        out += f'{prefix}element_signature: "{self.element_signature}"'
        out += f"{prefix}reserved: {self.reserved}"
        out += f'{prefix}text: "{escape_string(self.text)}"'
        return out

    def todict_textType(self):
        d = {}
        d["element_signature"] = self.element_signature
        d["reserved"] = self.reserved
        d["text"] = escape_string(self.text)
        return d

    def tostring_chromaticityType(self, tabsize):
        prefix = " " if tabsize == -1 else ("\n" + TABSTR * tabsize)
        out = ""
        out += f'{prefix}element_signature: "{self.element_signature}"'
        out += f"{prefix}reserved: {self.reserved}"
        out += f"{prefix}num_device_channels: {self.num_device_channels}"
        out += f"{prefix}phosphor_colorant_type: {self.phosphor_colorant_type}"
        for i, (cie_xy_coordinate_x, cie_xy_coordinate_y) in enumerate(
            self.cie_xy_coordinates
        ):
            out += f"{prefix}cie_cy_coordinates_channel_{i}: ({self.tofloat_u16Fixed16Number(cie_xy_coordinate_x)}, {self.tofloat_u16Fixed16Number(cie_xy_coordinate_y)})"
        return out

    def todict_chromaticityType(self):
        d = {}
        d["element_signature"] = self.element_signature
        d["reserved"] = self.reserved
        d["num_device_channels"] = self.num_device_channels
        d["phosphor_colorant_type"] = self.phosphor_colorant_type
        d["cie_xy_coordinates"] = self.cie_xy_coordinates
        return d

    def tostring_curveType(self, tabsize):
        prefix = " " if tabsize == -1 else ("\n" + TABSTR * tabsize)
        out = ""
        out += f'{prefix}element_signature: "{self.element_signature}"'
        out += f"{prefix}reserved: {self.reserved}"
        out += f"{prefix}curve_count: {self.curve_count}"
        out += f"{prefix}curve_value: {self.curve_value}"
        return out

    def todict_curveType(self):
        d = {}
        d["element_signature"] = self.element_signature
        d["reserved"] = self.reserved
        d["curve_count"] = self.curve_count
        d["curve_value"] = self.curve_value
        return d

    def tostring_textDescriptionType(self, tabsize):
        prefix = " " if tabsize == -1 else ("\n" + TABSTR * tabsize)
        out = ""
        out += f'{prefix}element_signature: "{self.element_signature}"'
        out += f"{prefix}reserved: {self.reserved}"
        out += (
            f'{prefix}ascii_invariant_description: "{self.ascii_invariant_description}"'
        )
        out += f"{prefix}unicode_language_code: {self.unicode_language_code}"
        out += f"{prefix}unicode_localizable_description: {self.unicode_localizable_description}"
        return out

    def todict_textDescriptionType(self):
        d = {}
        d["element_signature"] = self.element_signature
        d["reserved"] = self.reserved
        d["ascii_invariant_description"] = self.ascii_invariant_description
        d["unicode_language_code"] = self.unicode_language_code
        d["unicode_localizable_description"] = self.unicode_localizable_description
        return d

    def tostring_multiLocalizedUnicodeType(self, tabsize):
        prefix = " " if tabsize == -1 else ("\n" + TABSTR * tabsize)
        out = ""
        out += f"{prefix}element_size: {self.element_size}"
        out += f'{prefix}element_signature: "{self.element_signature}"'
        out += f"{prefix}reserved: {self.reserved}"
        out += f"{prefix}number_of_names: {self.number_of_names}"
        out += f"{prefix}names ["
        tabsize += 0 if tabsize == -1 else 1
        prefix = " " if tabsize == -1 else ("\n" + TABSTR * tabsize)
        for (
            name_record_size,
            language_code,
            country_code,
            length,
            offset,
            content,
        ) in self.names:
            out += f"{prefix}("
            tabsize += 0 if tabsize == -1 else 1
            prefix = " " if tabsize == -1 else ("\n" + TABSTR * tabsize)
            out += f"{prefix}name_record_size: {name_record_size}"
            out += f'{prefix}language_code: "{language_code}"'
            out += f'{prefix}country_code: "{country_code}"'
            out += f"{prefix}length: {length}"
            out += f"{prefix}offset: {offset}"
            out += f'{prefix}content: "{content}"'
            tabsize -= 0 if tabsize == -1 else 1
            prefix = " " if tabsize == -1 else ("\n" + TABSTR * tabsize)
            out += f"{prefix}),"
        tabsize -= 0 if tabsize == -1 else 1
        prefix = " " if tabsize == -1 else ("\n" + TABSTR * tabsize)
        out += f"{prefix}]"
        return out

    def todict_multiLocalizedUnicodeType(self):
        d = {}
        d["element_size"] = self.element_size
        d["element_signature"] = self.element_signature
        d["reserved"] = self.reserved
        d["number_of_names"] = self.number_of_names
        d["names"] = []
        for (
            name_record_size,
            language_code,
            country_code,
            length,
            offset,
            content,
        ) in self.names:
            di = {}
            di["name_record_size"] = name_record_size
            di["language_code"] = language_code
            di["country_code"] = country_code
            di["length"] = length
            di["offset"] = offset
            di["content"] = content
            d["names"].append(di)
        return d

    @classmethod
    def tofloat_s15Fixed16Number(cls, s15Fixed16Number):
        s15Fixed = s15Fixed16Number[0]
        u16Frac = s15Fixed16Number[1]
        return s15Fixed + (u16Frac / 65536.0)

    @classmethod
    def tofloat_u16Fixed16Number(cls, u16Fixed16Number):
        u16Fixed = u16Fixed16Number[0]
        u16Frac = u16Fixed16Number[1]
        return u16Fixed + (u16Frac / 65536.0)

    def tostring_XYZType(self, tabsize):
        prefix = " " if tabsize == -1 else ("\n" + TABSTR * tabsize)
        out = ""
        out += f'{prefix}element_signature: "{self.element_signature}"'
        out += f"{prefix}reserved: {self.reserved}"
        out += f"{prefix}numbers {{"
        tabsize += 0 if tabsize == -1 else 1
        prefix = " " if tabsize == -1 else ("\n" + TABSTR * tabsize)
        for xyz_number in self.numbers:
            out += f"{prefix}({self.str_XYZNumber(xyz_number)}),"
        return out

    @classmethod
    def str_XYZNumber(cls, xyz_number):
        cie_x, cie_y, cie_z = xyz_number
        return f"{cls.tofloat_s15Fixed16Number(cie_x)} {cls.tofloat_s15Fixed16Number(cie_y)} {cls.tofloat_s15Fixed16Number(cie_z)}"

    def todict_XYZType(self):
        d = {}
        d["element_signature"] = self.element_signature
        d["reserved"] = self.reserved
        d["numbers"] = []
        for xyz_number in self.numbers:
            d["numbers"].append((self.todict_XYZNumber(xyz_number)))
        return d

    @classmethod
    def todict_XYZNumber(cls, xyz_number):
        cie_x, cie_y, cie_z = xyz_number
        return (
            cls.tofloat_s15Fixed16Number(cie_x),
            cls.tofloat_s15Fixed16Number(cie_y),
            cls.tofloat_s15Fixed16Number(cie_z),
        )

    def tostring_s15Fixed16ArrayType(self, tabsize):
        prefix = " " if tabsize == -1 else ("\n" + TABSTR * tabsize)
        out = ""
        out += f'{prefix}element_signature: "{self.element_signature}"'
        out += f"{prefix}reserved: {self.reserved}"
        out += f"{prefix}numbers {{"
        tabsize += 0 if tabsize == -1 else 1
        prefix = " " if tabsize == -1 else ("\n" + TABSTR * tabsize)
        for number in self.numbers:
            out += f"{prefix}{self.tofloat_s15Fixed16Number(number)},"
        tabsize -= 0 if tabsize == -1 else 1
        prefix = " " if tabsize == -1 else ("\n" + TABSTR * tabsize)
        out += f"{prefix}}}"
        return out

    def todict_s15Fixed16ArrayType(self):
        d = {}
        d["element_signature"] = self.element_signature
        d["reserved"] = self.reserved
        d["numbers"] = []
        for number in self.numbers:
            d["numbers"].append(self.tofloat_s15Fixed16Number(number))
        return d

    def tostring_parametricCurveType(self, tabsize):
        prefix = " " if tabsize == -1 else ("\n" + TABSTR * tabsize)
        out = ""
        out += f'{prefix}element_signature: "{self.element_signature}"'
        out += f"{prefix}reserved: {self.reserved}"
        out += f"{prefix}encoded_value: {self.encoded_value}"
        out += f"{prefix}reserved2: {self.reserved2}"
        out += f"{prefix}parameters {{"
        tabsize += 0 if tabsize == -1 else 1
        prefix = " " if tabsize == -1 else ("\n" + TABSTR * tabsize)
        for number in self.parameters:
            out += f"{prefix}{self.tofloat_s15Fixed16Number(number)},"
        tabsize -= 0 if tabsize == -1 else 1
        prefix = " " if tabsize == -1 else ("\n" + TABSTR * tabsize)
        out += f"{prefix}}}"
        return out

    def todict_parametricCurveType(self):
        d = {}
        d["element_signature"] = self.element_signature
        d["reserved"] = self.reserved
        d["encoded_value"] = self.encoded_value
        d["reserved2"] = self.reserved2
        d["parameters"] = []
        for number in self.parameters:
            d["parameters"].append(self.tofloat_s15Fixed16Number(number))
        return d

    # element packers
    def pack_UnimplementedType(self):
        # remaining contains the full blob (unparsed)
        tag = self.remaining
        return tag

    def pack_textType(self):
        # element_signature
        tag_format = "!" + str(len(self.element_signature)) + "s"
        # reserved
        tag_format += "I"
        # text
        tag_format += str(len(self.text)) + "s"
        tag = struct.pack(
            tag_format,
            self.element_signature.encode("ascii"),
            self.reserved,
            self.text.encode("ascii"),
        )
        return tag

    def pack_chromaticityType(self):
        # element_signature
        tag_format = "!" + str(len(self.element_signature)) + "s"
        # reserved
        tag_format += "I"
        # num_device_channels
        tag_format += "H"
        # phosphor_colorant_type
        tag_format += "H"
        tag = struct.pack(
            tag_format,
            self.element_signature.encode("ascii"),
            self.reserved,
            self.num_device_channels,
            self.phosphor_colorant_type,
        )
        for cie_xy_coordinate in self.cie_xy_coordinates:
            tag += self.pack_u16Fixed16Number(number)
        return tag

    def pack_u16Fixed16Number(cls, u16Fixed16Number):
        tag_format += "H" * self.num_device_channels
        tag = struct.pack(
            tag_format,
            self.element_signature.encode("ascii"),
            self.reserved,
            self.num_device_channels,
            self.phosphor_colorant_type,
            *self.cie_xy_coordinates,
        )
        return tag

    def pack_curveType(self):
        # element_signature
        tag_format = "!" + str(len(self.element_signature)) + "s"
        # reserved
        tag_format += "I"
        # curve_count
        tag_format += "I"
        # curve_value(s)
        tag_format += "H" * self.curve_count
        tag = struct.pack(
            tag_format,
            self.element_signature.encode("ascii"),
            self.reserved,
            self.curve_count,
            *self.curve_value,
        )
        return tag

    def pack_textDescriptionType(self):
        # element_signature
        tag_format = "!" + str(len(self.element_signature)) + "s"
        # reserved
        tag_format += "I"
        # ascii_length
        tag_format += "I"
        tag = struct.pack(
            tag_format,
            self.element_signature.encode("ascii"),
            self.reserved,
            self.ascii_length,
        )
        # element_signature
        tag_format = "!" + str(self.ascii_length) + "s"
        tag += struct.pack(
            tag_format,
            self.ascii_invariant_description.encode("ascii"),
        )
        # unicode_language_code
        tag_format = "!" + "I"
        # unicode_length
        tag_format += "I"
        # unicode_localizable_description
        tag_format += str(self.unicode_length) + "s"
        tag += struct.pack(
            tag_format,
            self.unicode_language_code,
            self.unicode_length,
            self.unicode_localizable_description,
        )
        # scriptcode_code
        tag_format = "!" + "H"
        tag_format += "B"
        tag_format += str(len(self.macintosh_description)) + "s"
        tag_format += str(len(self.rem)) + "s"
        tag += struct.pack(
            tag_format,
            self.scriptcode_code,
            self.macintosh_length,
            self.macintosh_description,
            self.rem,
        )
        return tag

    def pack_XYZType(self):
        tag_format = "!" + str(len(self.element_signature)) + "s" + "I"  # reserved
        tag = struct.pack(
            tag_format,
            self.element_signature.encode("ascii"),
            self.reserved,
        )
        for xyz_number in self.numbers:
            tag += self.pack_XYZNumber(xyz_number)
        return tag

    @classmethod
    def pack_XYZNumber(cls, xyz_number):
        numbers_format = "!hH"
        cie_x, cie_y, cie_z = xyz_number
        tag = struct.pack(numbers_format, *cie_x)
        tag += struct.pack(numbers_format, *cie_y)
        tag += struct.pack(numbers_format, *cie_z)
        return tag

    def pack_multiLocalizedUnicodeType(self):
        tag_format = (
            "!"
            + str(len(self.element_signature))
            + "s"
            + "I"  # reserved
            + "I"  # number_of_names
        )
        tag = struct.pack(
            tag_format,
            self.element_signature.encode("ascii"),
            self.reserved,
            self.number_of_names,
        )
        for (
            name_record_size,
            language_code,
            country_code,
            length,
            offset,
            content,
        ) in self.names:
            content_bytes = content.encode("utf-16be")
            name_format = (
                "!"
                + "I"  # name_record_size
                + str(len(language_code))
                + "s"
                + str(len(country_code))
                + "s"
                + "I"  # length
                + "I"  # offset
                + str(len(content_bytes))
                + "s"
            )
            tag += struct.pack(
                name_format,
                name_record_size,
                language_code.encode("ascii"),
                country_code.encode("ascii"),
                length,
                offset,
                content_bytes,
            )
        # keep the remaining buffer
        tag += self.rem
        return tag

    @classmethod
    def pack_s15Fixed16Number(cls, s15Fixed16Number):
        s15Fixed = s15Fixed16Number[0]
        u16Frac = s15Fixed16Number[1]
        numbers_format = "!hH"
        tag = struct.pack(numbers_format, s15Fixed, u16Frac)
        return tag

    @classmethod
    def pack_u16Fixed16Number(cls, u16Fixed16Number):
        u16Fixed = u16Fixed16Number[0]
        u16Frac = u16Fixed16Number[1]
        numbers_format = "!HH"
        tag = struct.pack(numbers_format, s15Fixed, u16Frac)
        return tag

    def pack_s15Fixed16ArrayType(self):
        tag_format = "!" + str(len(self.element_signature)) + "s" + "I"  # reserved
        tag = struct.pack(
            tag_format,
            self.element_signature.encode("ascii"),
            self.reserved,
        )
        numbers_format = "!hH"
        for number in self.numbers:
            tag += struct.pack(numbers_format, *number)
        return tag

    def pack_parametricCurveType(self):
        tag_format = (
            "!"
            + str(len(self.element_signature))
            + "s"
            + "I"  # reserved
            + "H"  # encoded_value
            + "H"  # reserved2
        )
        tag = struct.pack(
            tag_format,
            self.element_signature.encode("ascii"),
            self.reserved,
            self.encoded_value,
            self.reserved2,
        )
        parameters_format = "!hH"
        for parameter in self.parameters:
            tag += struct.pack(parameters_format, *parameter)
        return tag


class ICCProfile:
    # Table 11
    DEVICE_CLASS = {
        "scnr": "Input Device Profile",
        "mntr": "Display Device Profile",
        "prtr": "Output Device Profile",
        "link": "DeviceLink profile",
        "spac": "ColorSpace Conversion profile",
        "abst": "Abstract profile",
        "nmcl": "Named colour profile",
    }
    # Table 36
    PHOSPHOR_OR_COLORANT_TYPE = {
        0: "unknown",
        1: "ITU-R BT.709",
        2: "SMPTE RP145-1994",
        3: "EBU Tech.3213-E",
        4: "P22",
    }

    @classmethod
    def parse(cls, blob, force_version_number):
        # parse header
        profile = ICCProfile()
        profile.header, i = ICCHeader.parse(blob, force_version_number)
        # parse tag table
        profile.tag_count = struct.unpack(">I", blob[i : i + 4])[0]
        i += 4
        profile.tag_table = []
        profile.elements = {}
        for tag_index in range(profile.tag_count):
            header_signature = blob[i : i + 4].decode("ascii")
            i += 4
            header_offset = struct.unpack(">I", blob[i : i + 4])[0]
            i += 4
            header_size = struct.unpack(">I", blob[i : i + 4])[0]
            i += 4
            # parse tagged element data
            element_blob = blob[header_offset : header_offset + header_size]
            profile.tag_table.append((header_signature, header_offset))
            tag = ICCTag.parse(
                header_signature,
                header_offset,
                header_size,
                element_blob,
                profile.header,
            )
            if header_offset in profile.elements:
                if isinstance(profile.elements[header_offset], list):
                    profile.elements[header_offset].append(tag)
                else:
                    profile.elements[header_offset] = [
                        profile.elements[header_offset],
                        tag,
                    ]
            else:
                profile.elements[header_offset] = tag
        return profile

    def size(self):
        size = 0
        # header
        size += 128
        # tag table
        size += 4 + 12 * self.tag_count
        # tagged element data
        for tag in self.elements.values():
            size += tag.element_size
        return size

    def tostring(self, as_one_line=False):
        tabsize = -1 if as_one_line else 0
        prefix = " " if tabsize == -1 else ("\n" + TABSTR * tabsize)
        out = ""
        out += self.header.tostring(tabsize)
        out += f"{prefix}tag_count: {self.tag_count}"
        for _, element in self.elements.items():
            if isinstance(element, list):
                for subelement in element:
                    out += f"{prefix}{subelement.tostring(tabsize).strip()}"
            else:
                out += f"{prefix}{element.tostring(tabsize).strip()}"
        return out.strip()

    def todict(self, short=False):
        d = {}
        d.update(self.header.todict())
        d["tag"] = []
        for _, element in self.elements.items():
            if isinstance(element, list):
                for subelement in element:
                    d["tag"].append(subelement.todict())
            else:
                d["tag"].append(element.todict())
        if short:
            d = self.reduce_info(d)
        return d

    def reduce_info(self, din):
        # select header fields
        dout = {
            "profile_version": din["profile_version_number"],
            "profile_class": self.DEVICE_CLASS[din["profile_device_class"]],
            "color_space": din["color_space"],
            "profile_connection_space": din["profile_connection_space"],
            "xyz_illuminant": din["xyz_illuminant"],
        }
        # add tag summaries
        for tag in din["tag"]:
            if tag["header_signature"] == "desc":
                if tag["element_signature"] == "mluc":
                    dout["profile_description"] = tag["names"][0]["content"]
                elif tag["element_signature"] == "desc":
                    dout["profile_description"] = tag["ascii_invariant_description"]
            elif tag["header_signature"] == "cprt":
                if tag["element_signature"] == "mluc":
                    dout["profile_copyright"] = tag["names"][0]["content"]
                elif tag["element_signature"] == "text":
                    dout["profile_copyright"] = tag["text"]
            elif tag["header_signature"] == "wtpt":
                dout["media_white_point"] = " ".join(str(n) for n in tag["numbers"][0])
            elif tag["header_signature"] == "chad":
                dout["chromatic_adaptation"] = " ".join(str(n) for n in tag["numbers"])
            elif tag["header_signature"] == "rXYZ":
                dout["red_matrix_column"] = " ".join(str(n) for n in tag["numbers"][0])
            elif tag["header_signature"] == "gXYZ":
                dout["green_matrix_column"] = " ".join(
                    str(n) for n in tag["numbers"][0]
                )
            elif tag["header_signature"] == "bXYZ":
                dout["blue_matrix_column"] = " ".join(str(n) for n in tag["numbers"][0])
            elif tag["header_signature"] == "rTRC":
                if tag["element_signature"] == "para":
                    dout["red_trc"] = " ".join(str(n) for n in tag["parameters"])
                elif tag["element_signature"] == "curv":
                    dout["red_trc"] = " ".join(str(n) for n in tag["curve_value"])
            elif tag["header_signature"] == "gTRC":
                if tag["element_signature"] == "para":
                    dout["green_trc"] = " ".join(str(n) for n in tag["parameters"])
                elif tag["element_signature"] == "curv":
                    dout["green_trc"] = " ".join(str(n) for n in tag["curve_value"])
            elif tag["header_signature"] == "bTRC":
                if tag["element_signature"] == "para":
                    dout["blue_trc"] = " ".join(str(n) for n in tag["parameters"])
                elif tag["element_signature"] == "curv":
                    dout["blue_trc"] = " ".join(str(n) for n in tag["curve_value"])
            elif tag["header_signature"] == "chrm":
                dout["chromaticity_channels"] = tag["num_device_channels"]
                dout["chromaticity_phosphor_colorant_type"] = PHOSPHOR_OR_COLORANT_TYPE[
                    tag["phosphor_colorant_type"]
                ]
                for i, (cie_xy_coordinate_x, cie_xy_coordinate_y) in enumerate(
                    tag["cie_xy_coordinates"]
                ):
                    x = (ICCTag.tofloat_u16Fixed16Number(cie_xy_coordinate_x),)
                    y = (ICCTag.tofloat_u16Fixed16Number(cie_xy_coordinate_y),)
                    dout[f"chromaticity_channels_{i}"] = " ".join(
                        (
                            str(ICCTag.tofloat_u16Fixed16Number(cie_xy_coordinate_x)),
                            str(ICCTag.tofloat_u16Fixed16Number(cie_xy_coordinate_y)),
                        )
                    )
                dout["chromaticity_channels"] = tag["num_device_channels"]
            elif tag["header_signature"] == "dmdd":
                dout["device_model_desc"] = tag["ascii_invariant_description"]
            elif tag["header_signature"] == "dmnd":
                dout["device_mfg_desc"] = tag["ascii_invariant_description"]
            else:
                print(f"warning: need to support {header_signature}")
        return dout


def parse_icc_profile(infile, force_version_number, debug):
    marker_list = []
    # open infile
    if debug > 0:
        print("\nfile: %s" % infile)
    with open(infile, "rb") as fin:
        blob = fin.read()
        profile = ICCProfile.parse(blob, force_version_number)
    return profile


def remove_copyright(profile, debug):
    # 1. look for copyrightTag elements ("cprt") in the tag table
    new_tag_table = []
    offset_removal_list = []
    for signature, offset in profile.tag_table:
        if signature == "cprt":
            offset_removal_list.append(offset)
        else:
            new_tag_table.append((signature, offset))
    profile.tag_table = new_tag_table
    profile.tag_count -= len(offset_removal_list)
    tag_table_savings = 4 * len(offset_removal_list)
    # 2. ensure the elements in the offset removal list are not used anymore
    final_offset_removal_list = []
    for offset_candidate in offset_removal_list:
        if offset_candidate in (offset for (offset, _) in profile.tag_table):
            # offset is still used
            continue
        final_offset_removal_list.append(offset_candidate)
    # 3. remove unused elements
    elements_savings = 0
    for offset in final_offset_removal_list:
        elements_savings += len(profile.elements[offset].pack())
        del profile.elements[offset]
    return profile


def write_icc_profile(profile, outfile, debug):
    # 1. pack the header
    header_bytes = profile.header.pack()
    header_size = len(header_bytes)
    # 2. pack the tag elements
    offset_dict = {}
    elements_bytes = b""
    for offset, tag in profile.elements.items():
        tag_bytes = tag.pack()
        offset_dict[offset] = (len(elements_bytes), len(tag_bytes))
        elements_bytes += tag_bytes
    # 3. pack the tag table
    assert profile.tag_count == len(
        profile.tag_table
    ), "error: invalid tag count ({profile.tag_count} != {len(profile.tag_table)})"
    tag_table_bytes = struct.pack("!I", profile.tag_count)
    tag_table_size = 4 + 12 * profile.tag_count
    for signature, in_offset in profile.tag_table:
        offset_out, size = offset_dict[in_offset]
        offset = header_size + tag_table_size + offset_out
        tag_entry_format = "!" + str(len(signature)) + "s" + "I" + "I"  # offset  # size
        tag_table_bytes += struct.pack(
            tag_entry_format,
            signature.encode("ascii"),
            offset,
            size,
        )
    # 4. re-pack the header
    total_bytes = header_bytes + tag_table_bytes + elements_bytes
    profile.header.profile_size = len(total_bytes)
    header_bytes = profile.header.pack()
    total_bytes = header_bytes + tag_table_bytes + elements_bytes

    # 5. write back the full profile
    with open(outfile, "wb+") as fout:
        fout.write(total_bytes)


def get_options(argv):
    """Generic option parser.

    Args:
        argv: list containing arguments

    Returns:
        Namespace - An argparse.ArgumentParser-generated option object
    """
    # init parser
    # usage = 'usage: %prog [options] arg1 arg2'
    # parser = argparse.OptionParser(usage=usage)
    # parser.print_help() to get argparse.usage (large help)
    # parser.print_usage() to get argparse.usage (just usage line)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-v",
        "--version",
        action="store_true",
        dest="version",
        default=False,
        help="Print version",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="count",
        dest="debug",
        default=default_values["debug"],
        help="Increase verbosity (use multiple times for more)",
    )
    parser.add_argument(
        "--quiet",
        action="store_const",
        dest="debug",
        const=-1,
        help="Zero verbosity",
    )
    parser.add_argument(
        "--remove-copyright",
        dest="remove_copyright",
        action="store_true",
        default=default_values["remove_copyright"],
        help="Remove copyright",
    )
    parser.add_argument(
        "--print",
        dest="print",
        action="store_true",
        default=default_values["print"],
        help="Print input ICC profile in text format",
    )
    parser.add_argument(
        "--force-version-number",
        action="store",
        dest="force_version_number",
        default=default_values["force_version_number"],
        metavar="FORCED-VERSION-NUMBER",
        help="force version number",
    )
    parser.add_argument(
        "--as-one-line",
        dest="as_one_line",
        action="store_true",
        default=default_values["as_one_line"],
        help="Print output as one line%s"
        % (" [default]" if default_values["as_one_line"] else ""),
    )
    parser.add_argument(
        "--noas-one-line",
        dest="as_one_line",
        action="store_false",
        help="Print output as one line%s"
        % (" [default]" if not default_values["as_one_line"] else ""),
    )
    parser.add_argument(
        "--json",
        dest="json",
        action="store_true",
        default=default_values["json"],
        help="Diff output in scriptable mode (1 JSON line)%s"
        % (" [default]" if default_values["json"] else ""),
    )
    parser.add_argument(
        "--no-json",
        dest="json",
        action="store_false",
        help="Diff output in non-scriptable mode%s"
        % (" [default]" if not default_values["json"] else ""),
    )
    parser.add_argument(
        "--short",
        dest="short",
        action="store_true",
        default=default_values["short"],
        help="Short JSON Version%s" % (" [default]" if default_values["short"] else ""),
    )
    parser.add_argument(
        "--no-short",
        dest="short",
        action="store_false",
        help="Long JSON Version%s"
        % (" [default]" if not default_values["short"] else ""),
    )
    parser.add_argument(
        "--write",
        dest="write",
        action="store_true",
        default=default_values["write"],
        help="Write ICC profile in binary format",
    )
    parser.add_argument(
        "-i",
        "--infile",
        dest="infile",
        type=str,
        default=default_values["infile"],
        metavar="input-file",
        help="input file",
    )
    parser.add_argument(
        "-o",
        "--outfile",
        dest="outfile",
        type=str,
        default=default_values["outfile"],
        metavar="output-file",
        help="output file",
    )
    # do the parsing
    options = parser.parse_args(argv[1:])
    # implement version
    if options.version:
        print(f"version: {__version__}")
        sys.exit(0)
    return options


def main(argv):
    # parse options
    options = get_options(argv)
    # get infile/outfile
    if options.infile == "-" or options.infile is None:
        options.infile = "/dev/fd/0"
    if options.outfile == "-" or options.outfile is None:
        options.outfile = "/dev/fd/1"
    # print results
    if options.debug > 0:
        print(options)
    # parse input profile
    profile = parse_icc_profile(
        options.infile, options.force_version_number, options.debug
    )
    if options.print:
        # dump contents
        # print(profile.tostring(options.as_one_line))
        with open(options.outfile, "a") as fout:
            fout.write(profile.tostring(options.as_one_line))
        sys.exit(0)
    elif options.json:
        # dump contents
        profile_dict = profile.todict(options.short)
        profile_json = json.dumps(profile_dict, indent=4)
        with open(options.outfile, "a") as fout:
            fout.write(profile_json)
        sys.exit(0)
    if options.remove_copyright:
        # remove copyrights
        profile = remove_copyright(profile, options.debug)
    if options.write:
        # ensure there is a valid outfile
        assert options.outfile is not None, "error: need a valid outfile"
        # write profile
        write_icc_profile(profile, options.outfile, options.debug)


if __name__ == "__main__":
    # at least the CLI program name: (CLI) execution
    main(sys.argv)
