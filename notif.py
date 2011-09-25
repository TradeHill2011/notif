import os, sys, queue
from os import path as op

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

from notifprotocol import NotifConnectionFactory

from spatial import GeoMaster

kwargs = dict(
    enabled_protocols = settings.NOTIFY_TRANSPORTS,
    # flash_policy_port = 843,
    # flash_policy_file = op.join(ROOT, 'flashpolicy.xml'),
    socket_io_port = settings.NOTIFY_LISTEN_PORT,
    #static_path=os.path.join(os.path.dirname(__file__), "static"),
    #static_url_prefix='/static/',
    session_expiry = 8,
    session_check_interval = 4,
)

if settings.NOTIFY_SECURE:
    kwargs['secure'] = True

if not settings.PRODUCTION:
    kwargs['debug'] = True

ssl_options = None
if settings.NOTIFY_SECURE:
    ssl_options={
           "certfile": "/root/notify.tradehill.com.crt",
           "keyfile": "/root/dec.key",
       }

xheaders = False
if not settings.NOTIFY_SECURE:
    xheaders = True

def main():
    queue.start_queue(settings.FANOUT_HOST, settings.FANOUT_PORT)

    NotifRouter = tornadio.get_router(NotifConnectionFactory(queue_master=queue.master, geo_master=GeoMaster()), settings=kwargs)

    #configure the Tornado application
    application = tornado.web.Application(
            [NotifRouter.route()], 
            **kwargs
    )

    tornadio.server.SocketServer(application, 
        xheaders=xheaders, 
        ssl_options=ssl_options
    )


if __name__ == "__main__":
    main()