#!/usr/bin/python
import os, sys
import re, os, sys
import logging

from tornado import ioloop
import tornado.options
from tornado.options import define, options
from fanout.server import Server

import imp
imp.find_module('settings')
import settings
from django.core.management import setup_environ
setup_environ(settings)

from django.conf import settings


define('host', default=settings.FANOUT_LISTEN_HOST, help="listen host")
define('port', default=settings.FANOUT_PORT, type=int, help='listen port')

def cb(data):
    print 'received:', data

def main():
    tornado.options.parse_command_line()

    server = Server()
    server.start(options.host, options.port)
    ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    main()
