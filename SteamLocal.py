# ----------------------------------------------------------------
# Author: wayneferdon wayneferdon@hotmail.com
# Date: 2022-10-05 18:41:39
# LastEditors: WayneFerdon wayneferdon@hotmail.com
# LastEditTime: 2023-02-10 17:19:06
# FilePath: \Plugins\Wox.Plugin.SteamGames\SteamLocal.py
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
from RegexList import *
import steam.utils.appcache as StaemCache

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
            header, apps = StaemCache.parse_appinfo(appInfoVdf)
            appInfoDict = dict()
            while(True):
                try:
                    app = next(apps)
                except StopIteration:
                    break
                appId = str(app['appid'])
                if appId not in libs.keys():
                    continue
                appInfo = app['data']['appinfo']
                appInfoDict[appId] = appInfo['common']
                appInfoDict[appId]['path'] = libs[appId] + appInfo['config']['installdir']
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
            if data['type'] != 'Music':
                iconId = data['clientIcon'.lower()]
                icon = self.steamPath + '/steam/games/' + iconId + '.ico'
            else:
                parentId = str(data['parent'].data)
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
                    'title': detail['name'],
                    'icon': appIcon
                }
            )
        return appList
