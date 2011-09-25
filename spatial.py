import pymongo
import time

class GeoMaster(object):
    def __init__(self):
        pass
    
    def set_notif_master(self, notif_master):
        self.notif_master = notif_master
        self.connection = pymongo.Connection('localhost', 27017)
        self.usercollection = self.connection.geodb.users
        self.usercollection.remove()

    def log(self, *args, **kwargs):
        print 'GEOMASTER: %s' % (' '.join( str(x) for x in args ), )

    def locationpublish(self, user_internal_id, nickname, loc, session_key):
        geouser = GeoUser(self, {"id": user_internal_id, "nickname": nickname, "time": time.time(), "session_key": session_key, "loc": loc } )
        geouser.login()
            
    def logout(self, session_key):
        userdata = self.usercollection.find_one({"session_key":session_key})
        if not userdata:
            return

        GeoUser(self, userdata).logout()

    def send(self, session_key, data):
        self.log( session_key, 'SEND', data )
        self.notif_master.geo_send(session_key=session_key, data=data)
        
class GeoUser(object):
    def __init__(self, geo_master, data):
        self.geo_master = geo_master
        self.data = data

        self.log("SPAWNING GEOUSER OBJECT")

    @property
    def summary(self):
        return dict( (x,y) for (x,y) in self.data.iteritems() if x in ('id', 'loc', 'nickname') )

    def log(self, *args, **kwargs):
        print 'GEOUSER %s: %s' % (self.summary, ' '.join( str(x) for x in args ), )

    def login(self):
        self.save()        
        self.announce()

    def announce(self):
        nlist = {}
        self.log('ANNOUNCING')

        for nuser in self.get_neighbors():
            nuser.message({ "command": "geo_add", "data": self.summary })
            
            if not nlist.has_key(nuser.data['id']):
                nlist[nuser.data['id']] = nuser.summary
            
        # inform user about neighbors
        self.message({ "command": "geo_list", "data": nlist.values() })

    def logout(self):
        self.geo_master.usercollection.remove({"session_key": self.data['session_key']})    
        
        # XXX: not good enough - need to keep track of who we announced to
        # reason: my neighbors are not neccessarily your neighbors.
        if not self.geo_master.usercollection.find({"id": self.data['id']}):
            for nuser in self.get_neighbors():
                nuser.message({ "command": "geo_del", "data": self.summary })

    def save(self):
        self.geo_master.usercollection.remove({
                                            "session_key": self.data['session_key']
                                         })
        
        self.geo_master.usercollection.insert(self.data)
        
    def get_neighbors(self):
        for nearuserdata in self.geo_master.usercollection.find( { "loc" : { "$near" : self.data['loc'] } } ).limit(20):
            if nearuserdata['id'] != self.data['id']:
                yield GeoUser(self.geo_master,nearuserdata)


    def message(self, data):
        self.geo_master.send(self.data['session_key'], data)

geo_notify = GeoMaster

