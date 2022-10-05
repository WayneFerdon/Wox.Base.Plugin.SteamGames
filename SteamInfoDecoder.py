# ----------------------------------------------------------------
# Author: wayneferdon wayneferdon@hotmail.com
# Date: 2022-10-05 18:32:23
# LastEditors: wayneferdon wayneferdon@hotmail.com
# LastEditTime: 2022-10-05 18:32:24
# FilePath: \Wox.Plugin.SteamGames\SteamInfo.py
# ----------------------------------------------------------------
# Copyright (c) 2022 by Wayne Ferdon Studio. All rights reserved.
# Licensed to the .NET Foundation under one or more agreements.
# The .NET Foundation licenses this file to you under the MIT license.
# See the LICENSE file in the project root for more information.
# ----------------------------------------------------------------

import struct
from collections import namedtuple

vdfVersionList = [0x07564426, 0x07564427]
vdfUniverse = 0x00000001

# VDF has variable length integers (32-bit and 64-bit).
Integer = namedtuple('Integer', ('size', 'data'))

class SteamInfoDecoder:
    def __init__(self, data, wrapper=dict):
        self.wrapper = wrapper  # Wrapping container
        self.data = memoryview(data)  # Incoming data (bytes)
        self.offset = 0  # Parsing offset

        # Commonly used structs
        self._readInt32_ = self.makeCustomReader('<I', singleValue=True)
        self._readInt64_ = self.makeCustomReader('<Q', singleValue=True)
        self.readVdfHeader = self.makeCustomReader('<2I')
        self.readAppHeader = self.makeCustomReader('<3IQ20sI')

        # Functions to parse different data structures.
        self.valueParserDic = {
            0x00: self.parseSubsectionList,
            0x01: self.readString,
            0x02: self.readInt32,
            0x07: self.readInt64,
        }

    def decode(self, appIdList):
        parsed = self.wrapper()
        # These should always be present.
        headerFieldList = ('version', 'universe')
        header = self.wrapper(
            zip(headerFieldList, self.readVdfHeader())
        )
        if len(header) != len(headerFieldList):
            raise ValueError(
                'Not all VDF headers are present, only found {num}: {header!r}'.format(
                    num=len(header), header=header)
            )

        # Currently these are the only possible values for
        # a valid appinfo.vdf
        if header['version'] not in vdfVersionList:
            raise ValueError(
                'Unknown vdfVersion: 0x{0:08x}'.format(header['version'])
            )

        if header['universe'] != vdfUniverse:
            raise ValueError(
                'Unknown vdfUniverse: 0x{0:08x}'.format(header['version'])
            )

        # Parsing applications
        appFieldList = ('size', 'state', 'last_update',
                        'access_token', 'checksum', 'change_number')
        while True:
            appId = self._readInt32_()
            # AppID = 0 marks the last application in the App info
            if appId == 0:
                break
            # All fields are required.
            app = self.wrapper((zip(appFieldList, self.readAppHeader())))
            if len(app) != len(appFieldList):
                raise ValueError(
                    'Not all App headers are present, only found {num}: {header!r}'.format(
                        num=len(app), header=app)
                )
            # The newest VDF format is a bit simpler to parse.
            if header['version'] == 0x07564427:
                app['sections'] = self.parseSubsectionList()
            else:
                app['sections'] = self.wrapper()
                while True:
                    sectionId = self.readByte()
                    if not sectionId:
                        break

                    # Skip the 0x00 byte before section name.
                    self.offset += 1

                    sectionName = self.readString()
                    app['sections'][sectionName] = self.parseSubsectionList(
                        rootSection=True)

                    # New Section ID could be added in the future, or changes could be made to
                    # existing ones, so instead of maintaining a table of section names and their
                    # corresponding IdList, we are going to store the IdList with all the data.
                    app['sections'][sectionName][b'__steamFiles_sectionId'] = sectionId
            if str(appId) in appIdList:
                parsed[appId] = app
        return parsed

    def parseSubsectionList(self, rootSection=False):
        subsection = self.wrapper()

        while True:
            valueType = self.readByte()
            if valueType == 0x08:
                if rootSection:
                    # There's one additional 0x08 byte at the end of
                    # the root subsection.
                    self.offset += 1
                break

            key = self.readString()
            value = self.valueParserDic.get(
                valueType, self._unknownValueType_)()

            subsection[key] = value

        return subsection

    def makeCustomReader(self, fmt, singleValue=False):
        customStruct = struct.Struct(fmt)

        def returnMany():
            result = customStruct.unpack_from(self.data, self.offset)
            self.offset += customStruct.size
            return result

        def returnOne():
            result = customStruct.unpack_from(self.data, self.offset)
            self.offset += customStruct.size
            return result[0]

        if singleValue:
            return returnOne
        else:
            return returnMany

    def readInt32(self):
        number = self._readInt32_()
        return Integer(data=number, size=32)

    def readInt64(self):
        number = self._readInt64_()
        return Integer(data=number, size=64)

    def readByte(self):
        byte = self.data[self.offset]
        self.offset += 1
        return byte

    def readString(self):
        # This method is pretty fast, provided we iterate over a memory view.
        # It's also easier to read then the most per-formant ones, which is more important.
        for index, value in enumerate(self.data[self.offset:]):
            # NUL-byte – a string's end
            if value != 0:
                continue

            string = slice(self.offset, self.offset + index)
            self.offset += index + 1
            return self.data[string].tobytes()

    @staticmethod
    def _unknownValueType_():
        raise ValueError(
            'Cannot parse the provided data type.'
        )
