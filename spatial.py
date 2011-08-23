import pymongo
import time

class geo_notify():
    def __init__(self,queue):
        self.queue = queue
        self.connection = pymongo.Connection('localhost', 27017)
        self.usercollection = self.connection.geodb.users
        self.usercollection.remove()
    def locationpublish(self,user,loc,sessionid):
        # to notify user via the connection of new users nearby
        user = {"username": user.username, "sharelocation": user.sharelocation, "time": time.time(), "sessionid": sessionid, "loc": loc}

        self.usercollection.remove({"username": user['username'],"sessionid":user['sessionid']})
        self.usercollection.insert(user)
        
        n = self.userneighbours(user)

        # inform user about neighbours
        self.message(sessionid,{ "command": "geo_list", "data": n.keys()})

        # inform neighbours about user
        for nuser in n.itervalues():
            map(lambda sessionid: self.message(sessionid,{ "command": "geo_add", "data": user['username'] }),nuser['sessionid'])

    def message(self,sessionid,data):
        self.queue.master.get('#' + sessionid).send(data)
            
    def logout(self,sessionid):
        user = self.usercollection.find_one({"sessionid":sessionid})
        print ("found user",user)
        n = self.userneighbours(user)
        print ("found n",n)
        for nuser in n.itervalues():
            map(lambda sessionid: self.message(sessionid,{ "command": "geo_del", "data": user['username'] }),nuser['sessionid'])

    def userneighbours(self,user):
        n = {}
        for nuser in self.neighbours(user['loc']):
            print ("WORKING ON",nuser)
            if (nuser['username'] != user['username']):
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

