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
        self.write( self.open('flashpolicy.xml').read() )

class ChatConnection(tornadio.SocketConnection):
    # Class level variable

    def on_open(self, *args, **kwargs):
        self.subscribed = set()

    def on_message(self, message):
        if message['command'] == 'subscribe':
            for channel in message['channels']:
                print 'asked for', channel
                if channel.startswith('#'):
                    print 'IS SESSIONID'
                    session = engine.SessionStore(channel[1:])
                    user = get_user_by_session(session)
                    if user:
                        self.subscribe( '@' + user.username )
                self.subscribe(channel)

    def subscribe(self, channel):
        print 'subscribing', channel
        queue.master.get(channel).subscribe(self)
        self.subscribed.add(channel)

    def on_close(self):
        for channel in self.subscribed:
            try:
                queue.master.get(channel).unsubscribe(self)
            except:
                pass
        self.subscribed.clear()

    def envelope_received(self, envelope):
        self.send( envelope )

#use the routes classmethod to build the correct resource
ChatRouter = tornadio.get_router(ChatConnection)

kwargs = dict(
    enabled_protocols = settings.NOTIFY_PROTOCOLS,
    flash_policy_port = 843,
    flash_policy_file = op.join(ROOT, 'flashpolicy.xml'),
    socket_io_port = settings.NOTIFY_PORT,
    # static_path=os.path.join(os.path.dirname(__file__), "static"),
    # static_url_prefix='/',
)

if settings.NOTIFY_SECURE:
    kwargs['secure'] = True

if not settings.PRODUCTION:
    kwargs['debug'] = True

#configure the Tornado application
application = tornado.web.Application(
        [(r"/static/flashpolicy.xml", IndexHandler), ChatRouter.route()], 
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
