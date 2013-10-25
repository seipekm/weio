### 
#
# WEIO Web Of Things Platform
# Copyright (C) 2013 Nodesign.net, Uros PETREVSKI, Drasko DRASKOVIC
# All rights reserved
#
#               ##      ## ######## ####  #######  
#               ##  ##  ## ##        ##  ##     ## 
#               ##  ##  ## ##        ##  ##     ## 
#               ##  ##  ## ######    ##  ##     ## 
#               ##  ##  ## ##        ##  ##     ## 
#               ##  ##  ## ##        ##  ##     ## 
#                ###  ###  ######## ####  #######
#
#                    Web Of Things Platform 
#
# This file is part of WEIO
# WEIO is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# WEIO is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Authors : 
# Uros PETREVSKI <uros@nodesign.net>
# Drasko DRASKOVIC <drasko.draskovic@gmail.com>
#
###

import os, signal, sys, platform, subprocess, datetime

from tornado import web, ioloop, iostream, gen
sys.path.append(r'./');
from sockjs.tornado import SockJSRouter, SockJSConnection

from weioPlayer import player

import functools
import json
from weioLib import weioIpAddress
from weioLib import weioFiles

from shutil import copyfile

# For shared objects between handlers
# Handlers need to communicate between each other to avoid too complex client interaction
# Editor handler send funtction is exported to global shared object shared.editor,
# it will be used in dashboardHandler for transactions
from weioLib.weioUserApi import *

# IMPORT BASIC CONFIGURATION FILE 
from weioLib import weio_config


# Wifi detection route handler  
class WeioDashBoardHandler(SockJSConnection):
    global callbacks

    # Handler sanity, True alive, False dead
    global stdoutHandlerIsLive
    global stderrHandlerIsLive
    
    stdoutHandlerIsLive = None
    stderrHandlerIsLive = None
    
    def __init(self):
        self.errObject = []
        self.errReason = ""
    
    def delegateToEditorHandler(self,rq):
        shared.editor(rq)
    
    # DEFINE CALLBACKS HERE
    # First, define callback that will be called from websocket
    def sendIp(self,rq):
        
        # get configuration from file
        config = weio_config.getConfiguration()
        
        data = {}
        ip = weioIpAddress.getLocalIpAddress()
        #publicIp = weioIpAddress.getPublicIpAddress()
        data['requested'] = rq['request']
        data['status'] = config["dns_name"] + " on " + ip
        # Send connection information to the client
        self.send(json.dumps(data))
    
    def sendLastProjectName(self,rq):
        
        # get configuration from file
        config = weio_config.getConfiguration()
        
        data = {}
        data['requested'] = rq['request']
        lp = config["last_opened_project"].split("/")

        if (weioFiles.checkIfDirectoryExists(config["user_projects_path"]+config["last_opened_project"])):
            data['data'] = lp[0]
        else :
            data['data'] = "Select project here"
        # Send connection information to the client
        self.send(json.dumps(data))
        
    def play(self, rq):
        player.play(rq)

    def stop(self, rq):
        """Stop running application"""
        player.stop(rq)
       
    def sendPlatformDetails(self, rq):
        
        # get configuration from file
        config = weio_config.getConfiguration()
        
        data = {}
        
        platformS = ""
        
        platformS += "WeIO version " + config["weio_version"] + " with Python " + platform.python_version() + " on " + platform.system() + "<br>"
        platformS += "GPL 3, Nodesign.net 2013 Uros Petrevski & Drasko Draskovic <br>"
        
        data['serverPush'] = 'sysConsole'
        data['data'] = platformS
        self.delegateToEditorHandler(data)
        #CONSOLE.send(json.dumps(data))
    
    def getUserProjectsList(self, rq):
        
        # get configuration from file
        config = weio_config.getConfiguration()
        
        data = {}
        data['requested'] = rq['request']
        data['data'] = weioFiles.listOnlyFolders(config["user_projects_path"])
        self.send(json.dumps(data))
    
    def changeProject(self,rq):
        
        # get configuration from file
        config = weio_config.getConfiguration()
        
        config["last_opened_project"] = rq['data']+"/"
        weio_config.saveConfiguration(config);
        
        data = {}
        data['requested'] = rq['request']
        self.send(json.dumps(data))
        
        rqlist = ["stop", "getLastProjectName", "getUserProjetsFolderList"]
        
        for i in range(0,len(rqlist)):
            rq['request'] = rqlist[i]
            callbacks[rq['request']](self, rq)
        
    
    def sendUserData(self,rq):
        data = {}
        # get configuration from file
        config = weio_config.getConfiguration()
        data['requested'] = rq['request']
        
        data['name'] = config["user"]
        self.send(json.dumps(data))

    def newProject(self, rq):
        
        config = weio_config.getConfiguration()
        
        data = {}
        data['requested'] = rq['request']
        path = rq['path']

        weioFiles.createDirectory(config["user_projects_path"] + path)
        # ADD HERE SOME DEFAULT FILES
        # adding __init__.py
        weioFiles.saveRawContentToFile(config["user_projects_path"] + path + "/__init__.py", "")
        
        copyfile("www/libs/weio/boilerPlate/index.html", config["user_projects_path"] + path +"/index.html")
        copyfile("www/libs/weio/boilerPlate/main.py", config["user_projects_path"] + path + "/main.py")
        
        data['status'] = "New project created"
        data['path'] = path
        self.send(json.dumps(data))

    def deleteCurrentProject(self, rq):
        
        data = {}
        data['requested'] = rq['request']

        config = weio_config.getConfiguration()
        projectToKill = config["last_opened_project"]
        
        weioFiles.removeDirectory(config["user_projects_path"]+projectToKill)
        
        folders = weioFiles.listOnlyFolders(config["user_projects_path"])
        
        if len(folders) > 0 :
            config["last_opened_project"] = folders[0]
            weio_config.saveConfiguration(config)
        
            data['data'] = "reload page"
        else :
            data['data'] = "ask to create new project"
        
        self.send(json.dumps(data))

    def iteratePacketRequests(self, rq) :
        
        requests = rq["packets"]

        for uniqueRq in requests:
            request = uniqueRq['request']
            if request in callbacks:
                callbacks[request](self, uniqueRq)
            else :
                print "unrecognised request ", uniqueRq['request']

    def sendPlayerStatus(self, rq):
        data = {}
        data['requested'] = rq['request']
        data['status'] = player.playing
        
        self.send(json.dumps(data))
                
    
##############################################################################################################################
    # DEFINE CALLBACKS IN DICTIONARY
    # Second, associate key with right function to be called
    # key is comming from socket and call associated function
    callbacks = {
        'getIp' : sendIp,
        'getLastProjectName' : sendLastProjectName,
        #'getFileTreeHtml' : getTreeInHTML,
        #'getFile': sendFileContent,
        'play' : play,
        'stop' : stop,
        'getUserProjetsFolderList': getUserProjectsList,
        'changeProject': changeProject,
        #'saveFile': saveFile,
        #'createNewFile': createNewFile,
        #'deleteFile': deleteFile,
        'getUser': sendUserData,
        'createNewProject': newProject,
        'deleteProject' : deleteCurrentProject,
        'packetRequests': iteratePacketRequests,
        'getPlayerStatus': sendPlayerStatus
        
    }
    
    def on_open(self, info) :
        
        global CONSOLE
        # Store instance of the ConsoleConnection class
        # in the global variable that will be used
        # by the MainProgram thread
        CONSOLE = self
        # connect interfaces to player object
        player.setConnectionObject(self)
   

    def on_message(self, data):
        """Parsing JSON data that is comming from browser into python object"""
        req = json.loads(data)
        self.serve(req)
        
    def serve(self, rq):
        """Parsed input from browser ready to be served"""
        # Call callback by key directly from socket
        global callbacks
        request = rq['request']
        
        if request in callbacks :
            callbacks[request](self, rq)
        else :
            print "unrecognised request ", rq['request']