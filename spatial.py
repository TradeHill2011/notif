import pymongo
import time

class geo_notify():
    def __init__(self,queue):
        self.queue = queue
        self.connection = pymongo.Connection('localhost', 27017)
        self.usercollection = self.connection.geodb.users
        self.usercollection.remove()

    def locationpublish(self,user,loc,sessionid):
        profile  = user.get_profile()
        user = User(self, {"id": user.id, "nickname": profile.nickname, "time": time.time(), "sessionid": sessionid, "loc": loc } )

        # save to db
        user.save()
        
        # send message to neighbours and inform user about neighbours
        user.announce()
            
    def logout(self,sessionid):
        userdata = self.usercollection.find_one({"sessionid":sessionid})
        if not userdata:
            return

        User(self,userdata).logout()
        
class User():
    def __init__(self,master,data):
        self.master = master
        for key in data.keys():
            setattr(self,key,data[key])
        self.summary = { "nickname": self.nickname, "id": self.id, "count": 1 }
        print ("SPAWNING USER OBJECT",self.summary)

    def logout(self):
        self.master.usercollection.remove({"sessionid": self.sessionid})    
        map(lambda nuser: nuser.message({ "command": "geo_del", "data": self.summary }), self.neighbours())

    def announce(self):
        nlist = {}
        # inform neighbours about user        
        for nuser in self.neighbours():
            nuser.message({ "command": "geo_add", "data": self.summary })
            
            if not nlist.has_key(nuser.id):
                nlist[nuser.id] = nuser.summary
            else:
                nlist[nuser.id]['count'] += 1
                
        # inform user about neighbours
        self.message({ "command": "geo_list", "data": nlist.values() })


    def save(self):
        self.master.usercollection.remove({"sessionid": self.sessionid})
        self.master.usercollection.insert({"sessionid": self.sessionid, "id": self.id, "nickname": self.nickname, "loc": self.loc })
        
    def neighbours(self):
        for nearuserdata in self.master.usercollection.find( { "loc" : { "$near" : self.loc } } ).limit(20):
            if nearuserdata['id'] != self.id:
                yield User(self.master,nearuserdata)


    def message(self,data):
        self.master.queue.master.get('#' + self.sessionid).send(data)
