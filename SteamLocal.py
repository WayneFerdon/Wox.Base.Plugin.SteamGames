# ----------------------------------------------------------------
# Author: wayneferdon wayneferdon@hotmail.com
# Date: 2022-10-05 18:41:39
# LastEditors: wayneferdon wayneferdon@hotmail.com
# LastEditTime: 2022-10-05 18:43:01
# FilePath: \Wox.Plugin.SteamGames\SteamLocal.py
# ----------------------------------------------------------------
# Copyright (c) 2022 by Wayne Ferdon Studio. All rights reserved.
# Licensed to the .NET Foundation under one or more agreements.
# The .NET Foundation licenses this file to you under the MIT license.
# See the LICENSE file in the project root for more information.
# ----------------------------------------------------------------

import os
from urllib.request import urlretrieve
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

    def __localAppInfo__(self):
        with open(self.steamPath + '/appcache/appinfo.vdf', 'rb') as appInfoVdf:
            appInfoList = SteamInfoDecoder(appInfoVdf.read(), wrapper=dict).decode(
                self.__localAppId__()).items()
        appInfoDict = dict()
        for appInfo in appInfoList:
            appId = appInfo[0]
            appInfoDict[str(
                appId)] = appInfo[1]['sections'][b'appInfo'.lower()][b'common']
        return appInfoDict

    def __localLib__(self):
        with open(self.steamPath + '/steamApps/libraryFolders.vdf') as libFoldersVdf:
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
                    appIdList.append(
                        child.name.replace(
                            'appManifest_'.lower(), '').replace('.acf', '')
                    )

        libList = self.__localLib__()
        appIdList = list()
        scanApp(self.steamPath)
        libNum = 1
        libDirKey = str(libNum)
        while libDirKey in libList.keys():
            libDir = libList[libDirKey]['path'] + '/steamApps'
            scanApp(libDir)
            libNum += 1
            libDirKey = str(libNum)
        return appIdList

    def appInfoList(self):
        def getIcon(data):
            if data[b'type'] != b'Music':
                iconId = data[b'clientIcon'.lower()].decode('utf-8')
                icon = self.steamPath + '/steam/games/' + iconId + '.ico'
            else:
                parentId = str(data[b'parent'].data)
                parent = localAppInfo[parentId]
                icon = getIcon(parent)
            if not os.path.isfile(icon):
                try:
                    urlretrieve(url=ICON_DATABASE + '/' + str(appId) +
                                '/' + icon + '.ico', filename=icon)
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
                    'appId': appId,
                    'appTitle': detail[b'name'].decode('utf-8'),
                    'appIcon': appIcon
                }
            )
        return appList
