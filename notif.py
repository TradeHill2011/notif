from os import path as op
import os
import sys
import queue

import tornado.web
import tornadio
import tornadio.router
import tornadio.server

import imp
imp.find_module('settings')
import settings
from django.core.management import setup_environ
setup_environ(settings)

from django.conf import settings

from django.utils.importlib import import_module
engine = import_module(settings.SESSION_ENGINE)

from django.contrib.auth import *

from TradeHill.models import *
import spatial
import types

def get_user_by_session(session):
    try:
        user_id = session[SESSION_KEY]
        
        backend_path = session[BACKEND_SESSION_KEY]
        backend = load_backend(backend_path)
        user = backend.get_user(user_id) or None
        print ("GOT USER",user,user.id)
        user.sharelocation = True # temporary, put this in a db
        
    except KeyError:
        user = None
    return user

ROOT = op.normpath(op.dirname(__file__))

class IndexHandler(tornado.web.RequestHandler):
    """Regular HTTP handler to serve the chatroom page"""
    def get(self):
        self.write( open( os.path.join(ROOT, 'flashpolicy.xml') ).read() )

class NotifConnection(tornadio.SocketConnection):
    # Class level variable
    connection_store = {}
    name = None
    user = None
    session_table = {}

    messagehandler = []
    messagehandler.append({"match": {"command":"subscribe","channels":types.ListType}, "callback": ["m_channelsubscribe"]})
    messagehandler.append({"match": {"command":"unsubscribe","channels":types.ListType}, "callback": ["m_channelunsubscribe"]})
    messagehandler.append({"match": {"command":"locationpublish","lat":types.FloatType,"lng": types.FloatType}, "callback": ["m_location_publish"]})
    messagehandler.append({"match": {"command":"locationpublish","lat":types.IntType,"lng": types.IntType}, "callback": ["m_location_publish"]})

    def m_location_publish(self,message):
        if (hasattr(self,"session")):
            geo_notify.locationpublish(self.user, [message['lat'],message['lng']], self.session.session_key)

    def m_channelsubscribe(self,message):
        for channel in message['channels']:
                print 'asked for', channel
                if channel.startswith('#'):
                    self.user_login(channel)
                elif channel.startswith('@'):
                    print 'SECURITY PROBLEM @ in channel', channel
                else:
                    self.subscribe(channel)
        
    def m_channelunsubscribe(self,message):
        for channel in message['channels']:
            if channel.startswith('#'):
                self.user_logout(channel)
            elif channel.startswith('@'):
                print 'SECURITY PROBLEM @ in channel', channel
            else:
                self.unsubscribe(channel)
        
        
    def on_open(self, *args, **kwargs):
        self.subscribed = set()
        
    def user_login(self, channel):
        if self.user:
            print 'CONNECTION REUSE - DYING', self.user, channel
            self.unsubscribe_all(channel)
            # self.close()
            return
        self.session = engine.SessionStore(channel[1:])
        self.user = get_user_by_session(self.session)
        
        print 'WHAT USER', self.user, self.session
        self.session_key = channel[1:]
        self.subscribe( '#' + self.session_key )
        if self.user:
            self.subscribe( '@' + self.user.username, session_key=self.session_key )
            if not settings.MOBILE:
                return
        
            self.connection_store.setdefault(self.user.username, set()).add(self)
#            for connection_name in self.connection_store.keys():
#                if self.user.username != connection_name: # inform me about all users
#                    self.send( {'to': '@' + self.user.username, 'msg': {'command': 'hello', 'name': connection_name}} )
#            if len( self.connection_store.setdefault(self.user.username, set()) ) == 1: # hi, i'm new
#                self.sendToAllNearbyButSelf( {'command': 'hello', 'name': self.user.username } )

    def user_logout(self, channel):
        print 'DYING INTENTIONALLY', self.user, channel
        self.unsubscribe_all(channel)
        # self.close()

    def dispatch_message(self,message):
        
        def matchmessage(match,message):    
            def matchkey(key,match,message):
                if (key in message):
                    if ((type(match[key]) == types.StringType) and (match[key] == message[key])):
                        return True
                    if ((type(match[key])) == type) and (match[key] == type(message[key])):
                        return True
                    if ((type(match[key])) == types.FunctionType):
                        return bool(match[key](message[key]))

                    
            for key in match:
                if not matchkey(key,match,message):
                    return False

            return True
            

        matched = False
        for messagehandler in self.messagehandler:
            if (matchmessage(messagehandler['match'],message)):
                matched = True
                map(lambda handler: getattr(self,handler)(message), messagehandler['callback'])
                
        return matched


    def on_message(self, message):
        print("MSGIN",message)
        if not (self.dispatch_message(message)):                    
            print 'UNPARSED MESSAGE', message

    def sendToAllNearbyButSelf(self, msg, username=None):
        if not username:
            username = self.user.username
        print 'SENDTOALLBUT', username, self.connection_store
        for name, conns in self.connection_store.items():
            if name != username:
                print 'SENDING', name, conns, username
                for conn in conns:
                    try:
                        conn.send( {'to': '@' + name, 'msg': msg} )
                    except:
                        pass

    def subscribe(self, channel, session_key = None):
        if session_key:
            self.session_table[session_key] = channel
        print 'subscribing', channel, session_key
        queue.master.get(channel).subscribe(self)
        self.subscribed.add(channel)

    def unsubscribe(self, channel):
        print 'unsubscribing', channel, self.session_table.get(channel)
        try:
            queue.master.get(channel).unsubscribe(self)
        except:
            pass
        try:
            self.subscribed.remove(channel)
        except:
            pass
    
    def unsubscribe_all(self, channel=None):
        username = None
        if channel:
            username = self.session_table.get(channel[1:], None)
            if username:
                username = username[1:]
                del self.session_table[channel[1:]]
        
        if not username:
            username = (self.user and self.user.username)

        print 'UNSUB ALL', self.user, username, self.connection_store

        for channel in list(self.subscribed):
            self.unsubscribe(channel)
        self.subscribed.clear()

        

        if settings.MOBILE:
            try:
                for x in list(self.connection_store[username]):
                    if x.session_key == channel[1:]:
                        self.connection_store[username].remove(x)
            except Exception, e:
                print 'UNSUB ERROR', e
                pass
            if username and (not self.connection_store.get(username, None)):
                try:
                    del self.connection_store[username]
                except:
                    pass

        if (hasattr(self,"session")):
            geo_notify.logout(self.session.session_key)
    
#            if username:
#                if not self.connection_store.get(username, None):
#                    self.sendToAllNearbyButSelf( {'command': 'bye', 'name': username }, username=username )

        print 'ENDUNSUB ALL: ', self.connection_store, self


        self.user = None

    def on_close(self):
        self.unsubscribe_all()

    def envelope_received(self, envelope):
        self.send( envelope )

kwargs = dict(
    enabled_protocols = settings.NOTIFY_TRANSPORTS,
    # flash_policy_port = 843,
    # flash_policy_file = op.join(ROOT, 'flashpolicy.xml'),
    socket_io_port = settings.NOTIFY_LISTEN_PORT,
    #static_path=os.path.join(os.path.dirname(__file__), "static"),
    #static_url_prefix='/static/',
    session_expiry = 15,
    session_check_interval = 5,
)

if settings.NOTIFY_SECURE:
    kwargs['secure'] = True

if not settings.PRODUCTION:
    kwargs['debug'] = True

#use the routes classmethod to build the correct resource
NotifRouter = tornadio.get_router(NotifConnection, settings=kwargs)

#configure the Tornado application
application = tornado.web.Application(
        [NotifRouter.route()], 
        **kwargs
    )

if __name__ == "__main__":
#    import logging
#    logging.getLogger().setLevel(logging.INFO)

    queue.start_queue(settings.FANOUT_HOST, settings.FANOUT_PORT)
    geo_notify = spatial.geo_notify(queue)

    ssl_options = None
    if settings.NOTIFY_SECURE:
        ssl_options={
               "certfile": "/root/notify.tradehill.com.crt",
               "keyfile": "/root/dec.key",
           }
    
    xheaders = False

    if not settings.NOTIFY_SECURE:
        xheaders = True

    tornadio.server.SocketServer(application, 
        xheaders=xheaders, 
        ssl_options=ssl_options
    )
