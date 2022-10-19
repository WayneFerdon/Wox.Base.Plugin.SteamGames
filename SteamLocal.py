# ----------------------------------------------------------------
# Author: wayneferdon wayneferdon@hotmail.com
# Date: 2022-10-05 18:41:39
# LastEditors: wayneferdon wayneferdon@hotmail.com
# LastEditTime: 2022-10-20 01:07:17
# FilePath: \Wox.Plugin.SteamGames\SteamLocal.py
# ----------------------------------------------------------------
# Copyright (c) 2022 by Wayne Ferdon Studio. All rights reserved.
# Licensed to the .NET Foundation under one or more agreements.
# The .NET Foundation licenses this file to you under the MIT license.
# See the LICENSE file in the project root for more information.
# ----------------------------------------------------------------

import os
from urllib.request import urlretrieve
from numpy import integer
import vdf
import winreg
from WoxQuery import *
from SteamInfoDecoder import *
from RegexList import *

ICON_DATABASE = 'https://steamcdn-a.akamaihd.net/steamcommunity/public/images/apps'


class SteamLocal:
    def __init__(self):
        regPath = r"steam\\Shell\\Open\\Command"
        key = winreg.OpenKeyEx(winreg.HKEY_CLASSES_ROOT,regPath)
        data = winreg.QueryValueEx(key,None)
        self.steamPath =  str(data[0]).split("\"")[1].replace("\steam.exe","")

    def __localAppInfo__(self) -> dict:
        localAppID, libs = self.__localAppId__()
        with open(self.steamPath + '/appcache/appinfo.vdf', 'rb') as appInfoVdf:
            appInfoList = SteamInfoDecoder(appInfoVdf.read(), wrapper=dict).decode(localAppID).items()
        appInfoDict = dict()
        for appInfo in appInfoList:
            appId = appInfo[0]
            appInfoDict[str(appId)] = appInfo[1]['sections'][b'appInfo'.lower()][b'common']
            appInfoDict[str(appId)]['path'] = libs[str(appId)] + str(appInfo[1]['sections'][b'appInfo'.lower()][b'config'][b'installdir'], "utf-8")
        return appInfoDict

    def __localLib__(self) -> dict:
        with open(self.steamPath + '/steamapps/libraryFolders.vdf') as libFoldersVdf:
            libList = vdf.load(libFoldersVdf)
            libList = libList['libraryfolders']
        return libList

    def __localAppId__(self):
        def scanApp(path):
            for child in os.scandir(path):
                if (
                        'appManifest'.lower() in child.name
                        and '228980' not in child.name
                ):
                    id = child.name.replace('appManifest_'.lower(), '').replace('.acf', '')
                    appIdList.append(id)
                    libInfos[id] = path + 'common\\'

        libList = self.__localLib__()
        libInfos = dict()
        appIdList = list()
        scanApp(self.steamPath)
        libNum = 1
        libDirKey = str(libNum)
        while libDirKey in libList.keys():
            libDir = libList[libDirKey]['path'] + '\\steamapps\\'
            scanApp(libDir)
            libNum += 1
            libDirKey = str(libNum)
        return appIdList, libInfos

    def appInfoList(self):
        def getIcon(data:dict[str, bytes|integer]):
            if data[b'type'] != b'Music':
                iconId = data[b'clientIcon'.lower()].decode('utf-8')
                icon = self.steamPath + '/steam/games/' + iconId + '.ico'
            else:
                parentId = str(data[b'parent'].data)
                parent = localAppInfo[parentId]
                icon = getIcon(parent)
            if not os.path.isfile(icon):
                try:
                    urlretrieve(
                        url=ICON_DATABASE + '/' + str(appId) + '/' + icon + '.ico',
                        filename=icon
                    )
                except Exception:
                    icon = './Image/steamIcon.png'
            return icon

        appList = list()
        localAppInfo = self.__localAppInfo__()
        for appId in localAppInfo:
            detail = localAppInfo[appId]
            appIcon = getIcon(detail)
            appList.append(
                {
                    'path': detail['path'],
                    'id': appId,
                    'title': bytes(detail[b'name']).decode('utf-8'),
                    'icon': appIcon
                }
            )
        return appList
