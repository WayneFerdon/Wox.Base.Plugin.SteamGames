# -*- coding: utf-8 -*-
import os
import re
import webbrowser
from urllib.request import urlretrieve
import struct
from collections import namedtuple
import vdf
from wox import Wox, WoxAPI

vdfVersionList = [0x07564426, 0x07564427]
vdfUniverse = 0x00000001

# VDF has variable length integers (32-bit and 64-bit).
Integer = namedtuple('Integer', ('size', 'data'))


class appInfoDecoder:

    def __init__(self, data, wrapper=dict):
        self.wrapper = wrapper  # Wrapping container
        self.data = memoryview(data)  # Incoming data (bytes)
        self.offset = 0  # Parsing offset

        # Commonly used structs
        self._readInt32 = self.makeCustomReader('<I', singleValue=True)
        self._readInt64 = self.makeCustomReader('<Q', singleValue=True)
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
                'Not all VDF headers are present, only found {num}: {header!r}'.format(num=len(header), header=header)
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
        appFieldList = ('size', 'state', 'last_update', 'access_token', 'checksum', 'change_number')
        while True:
            appId = self._readInt32()
            # AppID = 0 marks the last application in the App info
            if appId == 0:
                break
            # All fields are required.
            app = self.wrapper((zip(appFieldList, self.readAppHeader())))
            if len(app) != len(appFieldList):
                raise ValueError(
                    'Not all App headers are present, only found {num}: {header!r}'.format(num=len(app), header=app)
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
                    app['sections'][sectionName] = self.parseSubsectionList(rootSection=True)

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
            value = self.valueParserDic.get(valueType, self._unknownValueType)()

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
        number = self._readInt32()
        return Integer(data=number, size=32)

    def readInt64(self):
        number = self._readInt64()
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
    def _unknownValueType():
        raise ValueError(
            'Cannot parse the provided data type.'
        )


class steamLauncher(Wox):
    # set icon database paths
    iconDatabase = 'https://steamcdn-a.akamaihd.net/steamcommunity/public/images/apps'

    # find the first steam path from system environment
    sysPathList = os.environ['path'].split(';')
    for sysPath in sysPathList:
        if os.path.isfile(sysPath + '/steam.exe'):
            steamPath = sysPath
            break

    # load libList from steam installation path
    with open(steamPath + '/steamApps/libraryFolders.vdf') as libFoldersVdf:
        libList = vdf.load(libFoldersVdf)['LibraryFolders']

    # load apps' id from steam library
    appIdList = []
    libNum = 1
    libDirKey = str(libNum)
    while libDirKey in libList:
        libDir = libList[libDirKey] + '/steamApps'
        for file in os.scandir(libDir):
            if 'appManifest'.lower() in file.name and '228980' not in file.name:
                appIdList.append(
                    file.name.replace('appManifest_'.lower(), '').replace('.acf', '')
                )
        libNum += 1
        libDirKey = str(libNum)

    # get apps' title, icon
    # load app info vdf for loading client icon id
    with open(steamPath + '/appCache/appInfo.vdf', 'rb') as appInfoVdf:
        appInfoList = appInfoDecoder(appInfoVdf.read(), wrapper=dict).decode(appIdList).items()
    appList = []
    for appInfo in appInfoList:
        appId = appInfo[0]
        detail = appInfo[1]['sections'][b'appInfo'.lower()][b'common']
        appIconId = detail[b'clientIcon'.lower()].decode('utf-8')
        appIcon = steamPath + '/steam/games/' + appIconId + '.ico'
        if not os.path.isfile(appIcon):
            try:
                urlretrieve(url=iconDatabase + '/' + str(appId) + '/' + appIconId + '.ico', filename=appIcon)
            except Exception:
                appIcon = './Image/steamIcon.png'
        appList.append(
            {
                'appId': appId,
                'appTitle': detail[b'name'].decode('utf-8'),
                'appIcon': appIcon
            }
        )

    def query(self, queryString):
        result = []
        appList = self.appList

        queryStringLower = queryString.lower()
        queryList = queryStringLower.split()
        regexList = []
        for query in queryList:
            # pattern = '.*?'.join(query)
            # regexList.append(re.compile(pattern))
            regexList.append(re.compile(query))

        for app in appList:
            appTitle = app['appTitle']
            appId = app['appId']
            match = True
            for regex in regexList:
                match = regex.search(appTitle.lower() + str(appId)) and match
            if match:
                appIcon = app['appIcon']
                result.append(
                    {
                        'Title': appTitle + ' - ({})'.format(appId),
                        'SubTitle': 'Press Enter key to launch',
                        'IcoPath': appIcon,
                        'JsonRPCAction': {
                            'method': 'launchApp',
                            'parameters': [appId],
                            "dontHideAfterAction": False
                        }
                    }
                )
        return result

    @classmethod
    def launchApp(cls, appId):
        webbrowser.open(
            'steam://runGameId/{}'.format(appId)
        )


if __name__ == '__main__':
    steamLauncher()
