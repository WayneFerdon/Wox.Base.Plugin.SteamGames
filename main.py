# ----------------------------------------------------------------
# Author: wayneferdon wayneferdon@hotmail.com
# Date: 2022-02-12 06:25:55
# LastEditors: wayneferdon wayneferdon@hotmail.com
# LastEditTime: 2022-10-20 01:09:27
# FilePath: \Wox.Plugin.SteamGames\main.py
# ----------------------------------------------------------------
# Copyright (c) 2022 by Wayne Ferdon Studio. All rights reserved.
# Licensed to the .NET Foundation under one or more agreements.
# The .NET Foundation licenses this file to you under the MIT license.
# See the LICENSE file in the project root for more information.
# ----------------------------------------------------------------

# -*- coding: utf-8 -*-
import webbrowser
from WoxQuery import *
from SteamInfoDecoder import *
from RegexList import *
from SteamLocal import *
from subprocess import run

# class steamLauncher:
class SteamLauncher(WoxQuery):
    def query(self, queryString):
        appList = SteamLocal().appInfoList()
        results = list()
        regex = RegexList(queryString)
        subTitle = 'Press Enter key to launch'
        for app in appList:
            appTitle = app['title']
            appId = app['id']
            if not regex.match(appTitle + str(appId)):
                continue
            appIcon = app['icon']
            title = appTitle + ' - ({})'.format(appId)
            contextData = appId
            results.append(WoxResult(title, subTitle, appIcon, contextData, self.launchApp.__name__, True, appId).toDict())
        return results
    
    def context_menu(self, appId):
        appList = SteamLocal().appInfoList()
        for app in appList:
            if appId != app['id']:
                continue
            path = app["path"]
            subtitle = "Press Enter to Open App Dir"
            method = self.openDir.__name__
            icon = app['icon']
            return [WoxResult(path, subtitle, icon, None, method, True, path).toDict()]

    def openDir(self, dir:str):
        dir = dir.replace("\\\\","\\")
        run(f'explorer {dir}', shell=True)
    
    @classmethod
    def launchApp(cls, appId):
        webbrowser.open('steam://runGameId/{}'.format(appId))


if __name__ == '__main__':
    SteamLauncher()
    # print(SteamLauncher().query(""))
