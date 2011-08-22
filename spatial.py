import pymongo
import time

class geo_notify():
    def __init__(self,queue):
        self.queue = queue
        self.connection = pymongo.Connection('localhost', 27017)
        self.usercollection = self.connection.geodb.users

    def locationpublish(self,user,sessionid):
        # to notify user via the connection of new users nearby

        self.usercollection.remove({"username": user.username,"sessionid":sessionid})
        self.usercollection.insert({"username": user.username, "sharelocation": user.sharelocation, "time": time.time(), "sessionid": sessionid, "loc": user.loc})


        n = self.userneighbours(user)

        # inform user about neighbours
        self.message(sessionid,{ "command": "geo_neighbours", "data": n.keys()})

        # inform neighbours about user
        for nuser in n.itervalues():
            map(lambda sessionid: self.message(sessionid,{ "command": "geo_neighbour_add", "data": user.username }),nuser['sessionid'])

    def message(self,sessionid,data):
        self.queue.master.get('#' + sessionid).send(data)
            
    def logout(self,user,sessionid):
        n = self.userneighbours(user)
        for nuser in n:
            map(lambda sessionid: self.message(sessionid,{ "command": "geo_neighbour_del", "data": user.username }),n['sessionid'])
        self.usercollection.remove({"user":user,"sessionid":sessionid})

    def userneighbours(self,user):
        n = {}
        for nuser in self.neighbours(user.loc):
            print ("WORKING ON",nuser)
            if (nuser['username'] != user.username):
                if (n.has_key(nuser['username'])):
                    n[nuser['username']]['sessionid'].append(nuser['sessionid'])
                else:
                    n[nuser['username']] = {'sessionid' : [ nuser['sessionid']] }
        return n


    def neighbours(self,loc):
        data = []
        for nearuser in self.usercollection.find( { "sharelocation": True, "loc" : { "$near" :  loc } }, {"username": True, "sessionid": True} ).limit(20):
            data.append(nearuser)
        return data

