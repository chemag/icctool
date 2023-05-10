#!/usr/bin/env python
# Copyright (c) Meta, Inc. and its affiliates.

"""icctool: An ICC Profile Parser/Generator.

This module can parse, edit, and write an ICC Profile, per
[ICC.1:2022-05](https://www.color.org/specification/ICC.1-2022-05.pdf).

Right now the only edition feature allows removing copyrightTag elements.
"""


import argparse
import struct
import sys


default_values = {
    "debug": 0,
    "remove_copyright": False,
    "print": False,
    "as_one_line": True,
    "force_version_number": None,
    "write": False,
    "infile": None,
    "outfile": None,
}

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
        header.xyz_illuminant = blob[i : i + 12]
        i += 12
        header.profile_creator_field = struct.unpack(">I", blob[i : i + 4])[0]
        i += 4
        header.profile_id = blob[i : i + 16]
        i += 16
        header.reserved = blob[i : i + 28]
        i += 28
        # assert 0x00 == reserved, "invalid icc header"  # TODO
        return header, i

    def tostring(self, as_one_line):
        prefix = " " if as_one_line else "\n"
        return (
            f"{prefix}profile_size: 0x{self.profile_size:x}"
            f"{prefix}preferred_cmm_type: {self.preferred_cmm_type}"
            f"{prefix}profile_version_number: {self.str_VersionNumber()}"
            f"{prefix}profile_device_class: '{self.profile_device_class}'"
            f"{prefix}color_space: '{self.color_space}'"
            f"{prefix}profile_connection_space: '{self.profile_connection_space}'"
            f"{prefix}date_and_time: {self.str_dateTimeNumber()}"
            f"{prefix}profile_file_signature: '{self.profile_file_signature}'"
            f"{prefix}primary_platform_signature: '{self.primary_platform_signature}'"
            f"{prefix}profile_flags: {self.profile_flags}"
            f"{prefix}device_manufacturer: 0x{self.device_manufacturer:x}"
            f"{prefix}device_model: {self.device_model}"
            f"{prefix}device_attributes: {self.device_attributes}"
            f"{prefix}rendering_intent: {self.rendering_intent}"
            f"{prefix}xyz_illuminant: {self.xyz_illuminant}"
            f"{prefix}profile_creator_field: {self.profile_creator_field}"
            f"{prefix}profile_id: {self.profile_id}"
            f"{prefix}reserved: {self.reserved}"
        )

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
            + str(len(self.xyz_illuminant))
            + "s"
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
            self.xyz_illuminant,
            self.profile_creator_field,
            self.profile_id,
            self.reserved,
        )
        return header


# TODO(chema): refactor this
TAG_TYPE = [
    "textType",
    "textDescriptionType",
    "multiLocalizedUnicodeType",
    "XYZType",
    "s15Fixed16ArrayType",
    "curveType",
    "parametricCurveType",
]

# tag: (signature, permited_tag_types)
# AToB0Tag: ("A2B0", (lut8Type, lut16Type, lutAToBType,))
# AToB1Tag: ("A2B1", (lut8Type, lut16Type, lutAToBType,))
# AToB2Tag: ("A2B2", (lut8Type, lut16Type, lutAToBType,))
# blueMatrixColumnTag: ("bXYZ", (XYZType,))
# blueTRCTag: ("bTRC", (curveType, parametricCurveType,))
# BToA0Tag: ("B2A0", (lut8Type, lut16Type, lutBToAType,))
# BToA1Tag: ("B2A1", (lut8Type, lut16Type, lutBToAType,))
# BToA2Tag: ("B2A2", (lut8Type, lut16Type, lutBToAType,))
# BToD0Tag: ("B2D0", (multiProcessElementsType,))
# BToD1Tag: ("B2D1", (multiProcessElementsType,))
# BToD2Tag: ("B2D2", (multiProcessElementsType,))
# BToD3Tag: ("B2D3", (multiProcessElementsType,))
# calibrationDateTimeTacalibrationDateTimeTag: ("calt", (dateTimeType,))
# charTargetTag: ("targ", (textType,))
# chromaticAdaptationTag: ("chad", (s15Fixed16ArrayType,))
# chromaticityTag: ("chrm", (chromaticityType,))
# cicpTag: ("cicp", (cicpType,))
# colorantOrderTag: ("clro", (colorantOrderType,))
# colorantTableTag: ("clrt", (colorantTableType,))
# colorantTableOutTag: ("clot", (colorantTableType,))
# colorimetricIntentImageStateTag: ("ciis", (signatureType,))
# copyrightTag: ("cprt", (multiLocalizedUnicodeType,))
# deviceMfgDescTag: ("dmnd", (multiLocalizedUnicodeType,))
# deviceModelDescTag: ("dmdd", (multiLocalizedUnicodeType,))
# DToB0Tag: ("D2B0", (multiProcessElementsType,))
# DToB1Tag: ("D2B1", (multiProcessElementsType,))
# DToB2Tag: ("D2B2", (multiProcessElementsType,))
# DToB3Tag: ("D2B3", (multiProcessElementsType,))
# gamutTag: ("gamt", (lut8Type, lut16Type, lutBToAType,))
# grayTRCTag: ("kTRC", (curveType, parametricCurveType,))
# greenMatrixColumnTag: ("gXYZ", (XYZType,))
# greenTRCTag: ("gTRC", (curveType, parametricCurveType,))
# luminanceTag: ("lumi", (XYZType,))
# measurementTag: ("meas", (measurementType,))
# metadataTag: ("meta", (dictType,))
# mediaWhitePointTag: ("wtpt", (XYZType,))
# namedColor2Tag: ("ncl2", (namedColor2Type,))
# outputResponseTag: ("resp", (responseCurveSet16Type,))
# perceptualRenderingIntentGamutTag: ("rig0", (signatureType,))
# preview0Tag: ("pre0", (lut8Type, lut16Type, lutAToBType, lutBToAType,))
# preview1Tag: ("pre1", (lut8Type, lut16Type, lutBToAType,))
# preview2Tag: ("pre2", (lut8Type, lut16Type, lutBToAType,))
# profileDescriptionTag: ("desc", (multiLocalizedUnicodeType,))
# profileSequenceDescTag: ("pseq", (profileSequenceDescType,))
# profileSequenceIdentifierTag: ("psid", (profileSequenceIdentifierType,))
# redMatrixColumnTag: ("rXYZ", (XYZType,))
# redTRCTag: ("rTRC", (curveType, parametricCurveType,))
# saturationRenderingIntentGamutTag: ("rig2", (signatureType,))
# technologyTag: ("tech", (signatureType,))
# viewingCondDescTag: ("vued", (multiLocalizedUnicodeType,))
# viewingConditionsTag: ("view", (viewingConditionsType,))

class ICCTag:
    def __init__(self, tag_type):
        assert tag_type in TAG_TYPE, f"error: invalid tag type: {tag_type}"
        self.tag_type = tag_type

    @classmethod
    def parse(cls, signature, blob, header):
        if header.profile_version_number[0:2] == (2, 4):
            # version 2.4.0
            if signature in ("desc", "dmnd", "dmdd", "scrd", "vued"):
                return cls.parse_textDescriptionType(blob)
            elif signature in ("cprt", "targ"):
                return cls.parse_textType(blob)
        if signature in ("cprt", "dmnd", "dmdd", "desc", "vued"):
            return cls.parse_multiLocalizedUnicodeType(blob)
        elif signature in ("bXYZ", "gXYZ", "lumi", "bkpt", "wtpt", "rXYZ"):
            return cls.parse_XYZType(blob)
        elif signature in ("chad", "gXYZ", "lumi", "bkpt", "wtpt", "rXYZ"):
            return cls.parse_s15Fixed16ArrayType(blob)
        elif signature in ("bTRC", "kTRC", "gTRC", "rTRC"):
            signature = blob[0:4].decode("ascii")
            if signature == "curv":
                return cls.parse_curveType(blob)
            elif signature == "para":
                return cls.parse_parametricCurveType(blob)
        raise f"INVALID SIGNATURE: {signature}"

    def tostring(self):
        out = "tag {"
        out += f" type: {self.tag_type}"
        out += f" size: {self.size}"
        if self.tag_type == "multiLocalizedUnicodeType":
            out += self.str_multiLocalizedUnicodeType()
        elif self.tag_type == "XYZType":
            out += self.str_XYZType()
        elif self.tag_type == "s15Fixed16ArrayType":
            out += self.str_s15Fixed16ArrayType()
        elif self.tag_type == "curveType":
            out += self.str_curveType()
        elif self.tag_type == "parametricCurveType":
            out += self.str_parametricCurveType()
        elif self.tag_type == "textDescriptionType":
            out += self.str_textDescriptionType()
        elif self.tag_type == "textType":
            out += self.str_textType()
        out += " }"
        return out

    def pack(self):
        if self.tag_type == "multiLocalizedUnicodeType":
            return self.pack_multiLocalizedUnicodeType()
        elif self.tag_type == "XYZType":
            return self.pack_XYZType()
        elif self.tag_type == "s15Fixed16ArrayType":
            return self.pack_s15Fixed16ArrayType()
        elif self.tag_type == "curveType":
            return self.pack_curveType()
        elif self.tag_type == "parametricCurveType":
            return self.pack_parametricCurveType()
        elif self.tag_type == "textDescriptionType":
            return self.pack_textDescriptionType()
        elif self.tag_type == "textType":
            return self.pack_textType()

    @classmethod
    def parse_textType(cls, blob):
        tag = ICCTag("textType")
        tag.size = len(blob)
        i = 0
        tag.signature = blob[i : i + 4].decode("ascii")
        assert "text" == tag.signature, f"invalid textType signature ({tag.signature})"
        i += 4
        tag.reserved = struct.unpack(">I", blob[i : i + 4])[0]
        i += 4
        tag.text = blob[i:].decode("ascii")
        return tag

    def pack_textType(self):
        # TODO: implement this
        pass

    def str_textType(self):
        out = ""
        out += f" signature: '{self.signature}'"
        out += f" reserved: {self.reserved}"
        out += f" text: {self.text}"
        return out

    @classmethod
    def parse_textDescriptionType(cls, blob):
        tag = ICCTag("textDescriptionType")
        tag.size = len(blob)
        i = 0
        tag.signature = blob[i : i + 4].decode("ascii")
        assert (
            "desc" == tag.signature
        ), f"invalid textDescriptionType signature ({tag.signature})"
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

    def pack_textDescriptionType(self):
        # TODO: implement this
        pass

    def str_textDescriptionType(self):
        out = ""
        out += f" signature: '{self.signature}'"
        out += f" reserved: {self.reserved}"
        out += f' ascii_invariant_description: "{self.ascii_invariant_description}"'
        out += f" unicode_language_code: {self.unicode_language_code}"
        out += (
            f" unicode_localizable_description: {self.unicode_localizable_description}"
        )
        return out

    @classmethod
    def parse_multiLocalizedUnicodeType(cls, blob):
        tag = ICCTag("multiLocalizedUnicodeType")
        tag.size = len(blob)
        i = 0
        tag.signature = blob[i : i + 4].decode("ascii")
        assert (
            "mluc" == tag.signature
        ), f"invalid multiLocalizedUnicodeType signature ({tag.signature})"
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

    def pack_multiLocalizedUnicodeType(self):
        tag_format = (
            "!"
            + str(len(self.signature))
            + "s"
            + "I"  # reserved
            + "I"  # number_of_names
        )
        tag = struct.pack(
            tag_format,
            self.signature.encode("ascii"),
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

    def str_multiLocalizedUnicodeType(self):
        out = ""
        out += f" signature: '{self.signature}'"
        out += f" reserved: {self.reserved}"
        out += f" number_of_names: {self.number_of_names}"
        out += " names ["
        for (
            name_record_size,
            language_code,
            country_code,
            length,
            offset,
            content,
        ) in self.names:
            out += " ("
            out += f" name_record_size: '{name_record_size}'"
            out += f" language_code: {language_code}"
            out += f" country_code: {country_code}"
            out += f" length: {length}"
            out += f" offset: {offset}"
            out += f" content: '{content}'"
            out += " )"
        out += " ]"
        return out

    @classmethod
    def parse_s15Fixed16Number(cls, blob):
        # get the s15Fixed part
        s15Fixed = struct.unpack(">h", blob[0:2])[0]
        # get the s16Frac part
        s16Frac = struct.unpack(">H", blob[2:4])[0]
        return (s15Fixed, s16Frac)

    @classmethod
    def parse_XYZType(cls, blob):
        tag = ICCTag("XYZType")
        tag.size = len(blob)
        i = 0
        tag.signature = blob[i : i + 4].decode("ascii")
        assert "XYZ " == tag.signature, f"invalid XYZType signature ({tag.signature})"
        i += 4
        tag.reserved = struct.unpack(">I", blob[i : i + 4])[0]
        i += 4
        # read the XYZ numbers
        tag.numbers = []
        while i < len(blob):
            # s15Fixed16Number
            cie_x = cls.parse_s15Fixed16Number(blob[i : i + 4])
            i += 4
            cie_y = cls.parse_s15Fixed16Number(blob[i : i + 4])
            i += 4
            cie_z = cls.parse_s15Fixed16Number(blob[i : i + 4])
            i += 4
            tag.numbers.append((cie_x, cie_y, cie_z))
        return tag

    def pack_XYZType(self):
        tag_format = "!" + str(len(self.signature)) + "s" + "I"  # reserved
        tag = struct.pack(
            tag_format,
            self.signature.encode("ascii"),
            self.reserved,
        )
        numbers_format = "!hH"
        for (cie_x, cie_y, cie_z) in self.numbers:
            tag += struct.pack(numbers_format, *cie_x)
            tag += struct.pack(numbers_format, *cie_y)
            tag += struct.pack(numbers_format, *cie_z)
        return tag

    @classmethod
    def str_s15Fixed16Number(cls, s15Fixed16Number):
        s15Fixed = s15Fixed16Number[0]
        s16Frac = s15Fixed16Number[1]
        return s15Fixed + (s16Frac / 65536.0)

    def str_XYZType(self):
        out = ""
        out += f" signature: '{self.signature}'"
        out += f" reserved: {self.reserved}"
        out += " numbers {"
        for (cie_x, cie_y, cie_z) in self.numbers:
            out += f" ({self.str_s15Fixed16Number(cie_x)}, {self.str_s15Fixed16Number(cie_y)}, {self.str_s15Fixed16Number(cie_z)})"
        out += " }"
        return out

    @classmethod
    def parse_s15Fixed16ArrayType(cls, blob):
        tag = ICCTag("s15Fixed16ArrayType")
        tag.size = len(blob)
        i = 0
        tag.signature = blob[i : i + 4].decode("ascii")
        assert (
            "sf32" == tag.signature
        ), f"invalid s15Fixed16ArrayType signature ({tag.signature})"
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

    def pack_s15Fixed16ArrayType(self):
        tag_format = "!" + str(len(self.signature)) + "s" + "I"  # reserved
        tag = struct.pack(
            tag_format,
            self.signature.encode("ascii"),
            self.reserved,
        )
        numbers_format = "!hH"
        for number in self.numbers:
            tag += struct.pack(numbers_format, *number)
        return tag

    def str_s15Fixed16ArrayType(self):
        out = ""
        out += f" signature: '{self.signature}'"
        out += f" reserved: {self.reserved}"
        out += " numbers {"
        for number in self.numbers:
            out += f" {number}"
        out += " }"
        return out

    @classmethod
    def parse_parametricCurveType(cls, blob):
        tag = ICCTag("parametricCurveType")
        tag.size = len(blob)
        i = 0
        tag.signature = blob[i : i + 4].decode("ascii")
        assert (
            "para" == tag.signature
        ), f"invalid parametricCurveType signature ({tag.signature})"
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

    def pack_parametricCurveType(self):
        tag_format = (
            "!"
            + str(len(self.signature))
            + "s"
            + "I"  # reserved
            + "H"  # encoded_value
            + "H"  # reserved2
        )
        tag = struct.pack(
            tag_format,
            self.signature.encode("ascii"),
            self.reserved,
            self.encoded_value,
            self.reserved2,
        )
        parameters_format = "!hH"
        for parameter in self.parameters:
            tag += struct.pack(parameters_format, *parameter)
        return tag

    def str_parametricCurveType(self):
        out = ""
        out += f" signature: '{self.signature}'"
        out += f" reserved: {self.reserved}"
        out += f" encoded_value: {self.encoded_value}"
        out += f" reserved2: {self.reserved2}"
        out += " parameters {"
        for number in self.parameters:
            out += f" {number}"
        out += " }"
        return out


class ICCProfile:
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
            signature = blob[i : i + 4].decode("ascii")
            i += 4
            offset = struct.unpack(">I", blob[i : i + 4])[0]
            i += 4
            size = struct.unpack(">I", blob[i : i + 4])[0]
            i += 4
            # parse tagged element data
            profile.tag_table.append((signature, offset))
            tag = ICCTag.parse(signature, blob[offset : offset + size], profile.header)
            profile.elements[offset] = tag
        return profile

    def size(self):
        size = 0
        # header
        size += 128
        # tag table
        size += 4 + 12 * self.tag_count
        # tagged element data
        for tag in self.elements.values():
            size += tag.size
        return size

    def tostring(self, as_one_line=False):
        prefix = " " if as_one_line else "\n"
        out = ""
        out += self.header.tostring(as_one_line)
        out += f"{prefix}tag_count: {self.tag_count}"
        out += f"{prefix}tag_table ["
        for tag_index in range(self.tag_count):
            signature, offset = self.tag_table[tag_index]
            out += f"{prefix}("
            out += f" signature: '{signature}'"
            out += f" offset: 0x{offset:x}"
            out += " )"
        out += f"{prefix}]"
        out += f"{prefix}elements {{"
        for offset, tag in self.elements.items():
            out += f"{prefix}0x{offset:04x}: {tag.tostring()}"
        out += f"{prefix}}}"
        return out


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
    for (signature, offset) in profile.tag_table:
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
    for (signature, in_offset) in profile.tag_table:
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
        "--write",
        dest="write",
        action="store_true",
        default=default_values["write"],
        help="Write ICC profile in binary format",
    )
    parser.add_argument(
        "infile",
        type=str,
        nargs="?",
        default=default_values["infile"],
        metavar="input-file",
        help="input file",
    )
    parser.add_argument(
        "outfile",
        type=str,
        nargs="?",
        default=default_values["outfile"],
        metavar="output-file",
        help="output file",
    )
    # do the parsing
    options = parser.parse_args(argv[1:])
    return options


def main(argv):
    # parse options
    options = get_options(argv)
    # get infile/outfile
    if options.infile == "-":
        options.infile = "/dev/fd/0"
    # print results
    if options.debug > 0:
        print(options)
    # parse input profile
    profile = parse_icc_profile(
        options.infile, options.force_version_number, options.debug
    )
    if options.print:
        # dump contents
        print(profile.tostring(options.as_one_line))
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
