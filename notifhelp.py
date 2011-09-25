from django.conf import settings

from django.utils.importlib import import_module
engine = import_module(settings.SESSION_ENGINE)

from django.contrib.auth import *

import traceback, sys, time

def unhandled_exception_handler(reraise=False):
    tb = sys.exc_info()[2]
    stack = []

    while tb:
        # stack.append(tb.tb_frame) # too verbose!
        stack = [tb.tb_frame]
        tb = tb.tb_next

    traceback.print_exc()

    for frame in stack:
            print
            print "Frame %s in %s at line %s" % (frame.f_code.co_name,
                                                 frame.f_code.co_filename,
                                                 frame.f_lineno)
            for key, value in frame.f_locals.items():
                print "\t%20s = " % key,
                try:
                    print value
                except:
                    print "<ERROR WHILE PRINTING VALUE>"

    if reraise:
        raise

def get_user_by_session(session):
    try:
        user_id = session[SESSION_KEY]
        
        backend_path = session[BACKEND_SESSION_KEY]
        backend = load_backend(backend_path)
        user = backend.get_user(user_id) or None
        # print "GOT USER",user,user.id
        user.sharelocation = True # temporary, put this in a db
        
    except KeyError:
        user = None
    return user

def get_user_by_session_key(session_key):
    session_store = engine.SessionStore(session_key)
    user = get_user_by_session(session_store)
    if user:
        user.session_key = session_key
    
    return user

