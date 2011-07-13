from os import path as op
import os
import sys
import queue

import tornado.web
import tornadio
import tornadio.router
import tornadio.server

ROOT = op.normpath(op.dirname(__file__))

class IndexHandler(tornado.web.RequestHandler):
    """Regular HTTP handler to serve the chatroom page"""
    def get(self):
        self.render("index.html")

class ChatConnection(tornadio.SocketConnection):
    # Class level variable

    def on_open(self, *args, **kwargs):
        self.subscribed = set()

    def on_message(self, message):
        if message['command'] == 'subscribe':
            for channel in message['channels']:
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

#configure the Tornado application
application = tornado.web.Application(
    [(r"/", IndexHandler), ChatRouter.route()],
    enabled_protocols = [
                         'websocket',
                         # 'flashsocket',
#                         'htmlfile',
#                         'xhr-polling',
                         'jsonp-polling',
                         ],
    # flash_policy_port = 843,
    # flash_policy_file = op.join(ROOT, 'flashpolicy.xml'),
    socket_io_port = sys.argv[1],
    static_path=os.path.join(os.path.dirname(__file__), "static"),
    secure=True,
)

if __name__ == "__main__":
    import logging
    logging.getLogger().setLevel(logging.DEBUG)

    queue.start_queue()

    tornadio.server.SocketServer(application, xheaders=True, ssl_options={
           "certfile": "/root/notify.tradehill.com.crt",
           "keyfile": "/root/dec.key",
       })
