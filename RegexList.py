# ----------------------------------------------------------------
# Author: wayneferdon wayneferdon@hotmail.com
# Date: 2022-10-05 18:33:07
# LastEditors: wayneferdon wayneferdon@hotmail.com
# LastEditTime: 2022-10-05 18:33:08
# FilePath: \Wox.Plugin.SteamGames\RegexList.py
# ----------------------------------------------------------------
# Copyright (c) 2022 by Wayne Ferdon Studio. All rights reserved.
# Licensed to the .NET Foundation under one or more agreements.
# The .NET Foundation licenses this file to you under the MIT license.
# See the LICENSE file in the project root for more information.
# ----------------------------------------------------------------

# -*- coding: utf-8 -*-
import re

class RegexList:
    def __init__(self, queryString: str):
        self.queryString = queryString.replace('[', '\[') \
            .replace(']', '\]') \
            .replace('(', '\(') \
            .replace(')', '\)')
        queryStringLower = self.queryString.lower()
        queryList = queryStringLower.split()
        self.regexList = list[re.Pattern]()
        for query in queryList:
            self.regexList.append(re.compile(query))

    def match(self, item: str):
        match = True
        for regex in self.regexList:
            match = regex.search(item.lower()) and match
        return match