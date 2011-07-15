import socket
import cjson
import traceback

import imp
imp.find_module('settings')
import settings
from django.core.management import setup_environ
setup_environ(settings)

from django.conf import settings


class FanoutConnection(object):
    def __init__(self, HOST=settings.FANOUT_HOST, PORT=settings.FANOUT_PORT):
        self._socket = None

        s = None
        for res in socket.getaddrinfo(HOST, PORT, socket.AF_UNSPEC, socket.SOCK_STREAM):
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

    def yell(self, who, what):
        data = cjson.encode( {'to': who, 'msg': what} )
        if self._socket:
            msg = (unicode(len(data)) + u'\n' + data).encode('utf-8')
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
