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

import spatial

def get_user_by_session(session):
    try:
        user_id = session[SESSION_KEY]
        backend_path = session[BACKEND_SESSION_KEY]
        backend = load_backend(backend_path)
        user = backend.get_user(user_id) or None
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

    messagehandler = []
    messagehandler.append({"match": {"command":"subscribe","channels":types.ListType}, "callback": ["m_channelsubscribe"]})
    messagehandler.append({"match": {"command":"unsubscribe","channels":types.ListType}, "callback": ["m_channelunsubscribe"]})

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
            print 'CONNECTION REUSE - DYING'
            # self.unsubscribe_all()
            self.close()
            return
        session = engine.SessionStore(channel[1:])
        self.user = get_user_by_session(session)
        print 'WHAT USER', self.user, session
        self.session_key = channel[1:]
        self.subscribe( '#' + self.session_key )
        if self.user:
            self.subscribe( '@' + self.user.username )
            if not settings.MOBILE:
                return

            self.connection_store.setdefault(self.user.username, set()).add(self)
            for connection_name in self.connection_store.keys():
                if self.user.username != connection_name: # inform me about all users
                    self.send( {'to': '@' + self.user.username, 'msg': {'command': 'hello', 'name': connection_name}} )
#            if len( self.connection_store.setdefault(self.user.username, set()) ) == 1: # hi, i'm new
#                self.sendToAllNearbyButSelf( {'command': 'hello', 'name': self.user.username } )

    def user_logout(self, channel):
        print 'DYING INTENTIONALLY'
        # self.unsubscribe_all()
        self.close()

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
        if not (self.dispatch_message(message)):                    
            print 'UNPARSED MESSAGE', message

    def sendToAllNearbyButSelf(self, msg):
        print 'SENDTOALLBUT', self.user.username, self.connection_store
        for name, conns in self.connection_store.items():
            if name != self.user.username:
                print 'SENDING', name, conns, self.user.username
                for conn in conns:
                    try:
                        conn.send( {'to': '@' + name, 'msg': msg} )
                    except:
                        pass

    def subscribe(self, channel):
        print 'subscribing', channel
        queue.master.get(channel).subscribe(self)
        self.subscribed.add(channel)

    def unsubscribe(self, channel):
        print 'unsubscribing', channel
        try:
            queue.master.get(channel).unsubscribe(self)
        except:
            pass
        try:
            self.subscribed.remove(channel)
        except:
            pass
    
    def unsubscribe_all(self):
        for channel in list(self.subscribed):
            self.unsubscribe(channel)

    def on_close(self):
        if self.user and self.user.username:
            print 'CLOSING', self.user, self.user.username
            if settings.MOBILE:
                try:
                    self.connection_store[self.user.username].remove(self)
                except:
                    pass

                if self.user and self.user.username and (not self.connection_store.get(self.user.username, None)):
                    try:
                        del self.connection_store[self.user.username]
                    except:
                        pass
                    
        for channel in self.subscribed:
            try:
                queue.master.get(channel).unsubscribe(self)
            except:
                pass
            
        self.subscribed.clear()
        if settings.MOBILE:
            if self.user and self.user.username:
                if not self.connection_store.get(self.user.username, None):
                    self.sendToAllNearbyButSelf( {'command': 'bye', 'name': self.user.username } )
        self.user = None

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
    import logging
    logging.getLogger().setLevel(logging.DEBUG)

    queue.start_queue(settings.FANOUT_HOST, settings.FANOUT_PORT)

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
