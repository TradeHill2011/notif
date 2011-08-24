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
        print (dir(user))
        
        user = {"userid": user.id, "username": user.username, "sharelocation": user.sharelocation, "time": time.time(), "sessionid": sessionid, "loc": loc}

        self.usercollection.remove({"sessionid":user['sessionid']})
        self.usercollection.insert(user)
        
        n = self.userneighbours(user)

        # inform user about neighbours

        
        self.message(sessionid,{ "command": "geo_list", "data": })

        # inform neighbours about user
        for nuser in n.itervalues():
            map(lambda sessionid: self.message(sessionid,{ "command": "geo_add", "data": { 'username': user['username'], 'userid': user['userid']} }),nuser['sessionid'])

    def message(self,sessionid,data):
        self.queue.master.get('#' + sessionid).send(data)
            
    def logout(self,sessionid):
        user = self.usercollection.find_one({"sessionid":sessionid})
        if not user:
            return
        print ("found user",user)
        self.usercollection.remove({"sessionid":sessionid})
        n = self.userneighbours(user)
        for nuser in n.itervalues():
            map(lambda sessionid: self.message(sessionid,{ "command": "geo_del", "data": user['userid'] }),nuser['sessionid'])
            

    def userneighbours(self,user):
        n = {}
        for nuser in self.neighbours(user['loc']):
            if (nuser['userid'] == user['userid']):
                continue
                
            if (n.has_key(nuser['userid'])):
                n[nuser['userid']]['sessionid'].append(nuser['sessionid'])
            else:
                n[nuser['userid']] = {'username': nuser['username'], 'sessionid' : [ nuser['sessionid']] }
        print (n)
        return n


    def neighbours(self,loc):
        data = []
        for nearuser in self.usercollection.find( { "loc" : { "$near" :  loc } } ).limit(20):
            data.append(nearuser)
        return data

