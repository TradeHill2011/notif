import socket
# import cjson
import traceback

import imp
imp.find_module('settings')
import settings
from django.core.management import setup_environ
setup_environ(settings)

from django.conf import settings

import json
from datetime import datetime
from decimal import *

class CustomEncoder(json.JSONEncoder):
  def default(self, o, markers=None):
    if isinstance(o, Decimal):
      return str(o);
    elif isinstance(o, datetime):
      return str(o);
    return json.JSONEncoder.default(self, o)

class FanoutConnection(object):
    def __init__(self, HOST=settings.FANOUT_HOST, PORT=settings.FANOUT_PORT):
        self._socket = None

        s = None
        hostinfo = []
        try:
            hostinfo = socket.getaddrinfo(HOST, PORT, socket.AF_UNSPEC, socket.SOCK_STREAM)
        except:
            import traceback
            traceback.print_exc()
            print "can't resolve", HOST, PORT
        for res in hostinfo:
            af, socktype, proto, canonname, sa = res
            try:
                s = socket.socket(af, socktype, proto)
            except socket.error, msg:
                s = None
                continue
            try:
                s.connect(sa)
            except socket.error, msg:
                s.close()
                s = None
                continue
            break
        
        if s:
            self._socket = s
            self._socket.setblocking(1)
            self._socket.settimeout(0.1)
        else:
            print "Can't connect to fanout server."

    def yell(self, who, data=None, json_data=None):
        if not json_data:
            json_data = json.dumps( {'to': who, 'msg': data}, cls=CustomEncoder )
        if self._socket:
            msg = (unicode(len(json_data)) + u'\n' + json_data).encode('utf-8')
            try:
                self._socket.send(msg)
            except:
                traceback.print_exc()
                self._socket = None

    def close(self):
        try:
            self._socket.send('BYE\n')
        except:
            pass
        self._socket = None

def main():
    conn = FanoutConnection()
    conn.yell( 'EVERYONE', 'frob' )
    conn.yell( '@enki@bbq.io', 'secret' )
    conn.yell( 'LOST', 'lost' )
    conn.close()

if __name__ == '__main__':
    main()
