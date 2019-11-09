# -*- coding: utf-8 -*-
import os
import re
import webbrowser
from urllib.request import urlretrieve
import struct
from collections import namedtuple
import vdf
from wox import Wox, WoxAPI

vdfVersions = [0x07564426, 0x07564427]
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
        self.readGameHeader = self.makeCustomReader('<3IQ20sI')

        # Functions to parse different data structures.
        self.valueParsers = {
            0x00: self.parseSubsections,
            0x01: self.readString,
            0x02: self.readInt32,
            0x07: self.readInt64,
        }

    def decode(self, gameIds):
        parsed = self.wrapper()
        # These should always be present.
        headerFields = ('version', 'universe')
        header = self.wrapper((zip(headerFields, self.readVdfHeader())))
        if len(header) != len(headerFields):
            raise ValueError('Not all VDF headers are present, only found {num}: {header!r}'.format(
                num=len(header),
                header=header,
            ))

        # Currently these are the only possible values for
        # a valid appinfo.vdf
        if header['version'] not in vdfVersions:
            raise ValueError('Unknown vdfVersion: 0x{0:08x}'.format(header['version']))

        if header['universe'] != vdfUniverse:
            raise ValueError('Unknown vdfUniverse: 0x{0:08x}'.format(header['version']))

        # Parsing applications
        appFields = ('size', 'state', 'last_update', 'access_token', 'checksum', 'change_number')
        while True:
            appId = self._readInt32()
            # AppID = 0 marks the last application in the App info
            if appId == 0:
                break
            # All fields are required.
            app = self.wrapper((zip(appFields, self.readGameHeader())))
            if len(app) != len(appFields):
                raise ValueError('Not all App headers are present, only found {num}: {header!r}'.format(
                    num=len(app),
                    header=app,
                ))
            # The newest VDF format is a bit simpler to parse.
            if header['version'] == 0x07564427:
                app['sections'] = self.parseSubsections()
            else:
                app['sections'] = self.wrapper()
                while True:
                    sectionId = self.readByte()
                    if not sectionId:
                        break

                    # Skip the 0x00 byte before section name.
                    self.offset += 1

                    sectionName = self.readString()
                    app['sections'][sectionName] = self.parseSubsections(rootSection=True)

                    # New Section ID's could be added in the future, or changes could be made to
                    # existing ones, so instead of maintaining a table of section names and their
                    # corresponding IDs, we are going to store the IDs with all the data.
                    app['sections'][sectionName][b'__steamFiles_sectionId'] = sectionId
            if str(appId) in gameIds:
                parsed[appId] = app
        return parsed

    def parseSubsections(self, rootSection=False):
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
            value = self.valueParsers.get(valueType, self._unknownValueType)()

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
        raise ValueError('Cannot parse the provided data type.')


class steamLauncher(Wox):
    # set paths
    iconDatabase = 'https://steamcdn-a.akamaihd.net/steamcommunity/public/images/apps'

    sysPathList = os.environ['path'].split(';')
    steamPathList = []
    for sysPath in sysPathList:
        if os.path.isfile(sysPath + '/steam.exe') and sysPath not in steamPathList:
            steamPathList.append(sysPath)
    steamPath = steamPathList[0]

    # load libFolders' path
    libs = [steamPath + '/steamApps']
    with open(libs[0] + '/libraryFolders.vdf') as libFoldersPath:
        libFolders = vdf.load(libFoldersPath)['LibraryFolders']

    # get apps' id
    gameIdList = []
    libKeyNum = 1
    libKey = str(libKeyNum)
    while libKey in libFolders:
        lib = libFolders[libKey] + '/steamApps'
        for file in os.scandir(lib):
            if 'appManifest'.lower() in file.name and '228980' not in file.name:
                gameIdList.append(file.name.replace('appManifest_'.lower(), '').replace('.acf', ''))
        libKeyNum += 1
        libKey = str(libKeyNum)

    # get apps' title, icon
    # load app info vdf for loading client icon id
    with open(steamPath + '/appCache/appInfo.vdf', 'rb') as appinfoVdf:
        infoList = appInfoDecoder(appinfoVdf.read(), wrapper=dict).decode(gameIdList).items()
    gameList = []
    for info in infoList:
        gameId = info[0]
        detail = info[1]['sections'][b'appInfo'.lower()][b'common']
        gameIconId = detail[b'clientIcon'.lower()].decode('utf-8')
        gameIcon = steamPath + '/steam/games/' + gameIconId + '.ico'
        if not os.path.isfile(gameIcon):
            try:
                urlretrieve(url=iconDatabase + '/' + str(gameId) + '/' + gameIconId + '.ico', filename=gameIcon)
            except BaseException:
                gameIcon = 'Image/icon.png'
        gameList.append({'gameId': gameId, 'gameTitle': detail[b'name'].decode('utf-8'), 'gameIcon': gameIcon})

    def query(self, query):
        result = []
        gameList = self.gameList
        q = query.lower()
        pattern = '.*?'.join(q)
        regex = re.compile(pattern)
        for game in gameList:
            match = regex.search(game['gameTitle'].lower())
            if match:
                result.append(
                    {
                        'Title': game['gameTitle'] + ' - ({})'.format(game['gameId']),
                        'SubTitle': 'Press Enter key to launch',
                        'IcoPath': game['gameIcon'],
                        'JsonRPCAction': {
                            'method': 'launchGame',
                            'parameters': [game['gameId']],
                            "doNotHideAfterAction".replace('oNo', 'on'): False,
                        },
                    }
                )
        return result

    def launchGame(self, gameId):
        webbrowser.open('steam://runGameId/{}'.format(gameId))


if __name__ == '__main__':
    steamLauncher()
