import tornadio
import sys
import gc, pprint

from django.conf import settings
from notifhelp import unhandled_exception_handler, get_user_by_session_key

class NotifConnectionFactory(object):
    def __init__(self, queue_master=None, geo_master=None):
        self.notif_master = NotifMaster(queue_master=queue_master, geo_master=geo_master)

    def __call__ (self, *args, **kwargs):
        return NotifConnection(notif_master=self.notif_master, *args, **kwargs)

class NotifMaster(object):
    def __init__(self, queue_master=None, geo_master=None):
        self.queue_master = queue_master

        self.all_connections = set()
        self.connections_by_connection_id = {}
        self.channel_subscriptions_by_connection_id = {}
        self.connection_ids_by_user_id = {}
        self.user_ids_by_connection_id = {}

        self.user_by_user_id = {}

        self.connection_ids_by_session_key = {}

        if settings.MOBILE:
            geo_master.set_notif_master(self)
            self.geo_master = geo_master

    def log(self, *args, **kwargs):
        print 'MASTER: %s' % (' '.join( str(x) for x in args ), )

    def proclaim_birth(self, conn):
        conn, connection_id = self.to_conn_and_connection_id(conn)
        self.log( connection_id, 'BORN' )
        self.all_connections.add(conn)
        assert not self.connections_by_connection_id.get( conn.get_connection_id(), None), 'Duplicate Connection Handler %s' % (conn.get_connection_id(),)

        self.connections_by_connection_id[ conn.get_connection_id() ] = conn

    def kill(self, conn):
        conn, connection_id = self.to_conn_and_connection_id(conn)

        self.log( connection_id, 'KILL' )
        self.terminate_subscriptions(conn)
        self.all_connections.remove(conn)
        conn.markDead()

        del self.connections_by_connection_id[ conn.get_connection_id() ]

    def proclaim_death(self, conn):
        conn, connection_id = self.to_conn_and_connection_id(conn)
        assert conn.dead, "Deceased but never died?"

        self.log( connection_id, 'DECEASED'  )
    
    def to_conn_and_connection_id(self, conn_or_connection_id):
        if isinstance(conn_or_connection_id, basestring):
            conn = self.connections_by_connection_id[conn_or_connection_id]
            connection_id = conn_or_connection_id
        else:
            conn = conn_or_connection_id
            connection_id = conn_or_connection_id.get_connection_id()
        return conn, connection_id
    
    def get_subscriptions_for_connection_id(self, connection_id):
        return self.channel_subscriptions_by_connection_id.setdefault( connection_id, set() )

    def get_connection_ids_for_user_id(self, user_id):
        return self.connection_ids_by_user_id.setdefault( user_id, set() )

    def get_user_ids_for_connection_id(self, connection_id):
        return self.user_ids_by_connection_id.setdefault( connection_id, set() )

    def get_connection_ids_for_session_key(self, session_key):
        return self.connection_ids_by_session_key.setdefault( session_key, set() )

    def subscribe(self, conn_or_connection_id, channel):
        conn, connection_id = self.to_conn_and_connection_id(conn_or_connection_id)
        self.log(connection_id, 'wants to subscribe to', channel)

        if channel.startswith('#'):
            connectionsession_ids = self.get_connection_ids_for_session_key( channel[1:] )
            connectionsession_ids.add( connection_id )

        if channel.startswith('@'):
            user_id = channel[1:]
            self.log('adding', connection_id, 'to', user_id )
            userconnection_ids = self.get_connection_ids_for_user_id( user_id )
            userconnection_ids.add(connection_id)

            connectionuser_ids = self.get_user_ids_for_connection_id( connection_id )
            connectionuser_ids.add(user_id)
            assert len(connectionuser_ids) == 1, 'More than one user_id in connection_id %s: %s (%s)' % (connection_id, user_id, connectionuser_ids)

            self.log('updated userconnection_ids for', user_id, ':', userconnection_ids)
        
        subscriptions = self.get_subscriptions_for_connection_id(connection_id)
        subscriptions.add(channel)
        self.queue_master.get(channel).subscribe( conn )
    
    def unsubscribe(self, conn_or_connection_id, channel):
        conn, connection_id = self.to_conn_and_connection_id(conn_or_connection_id)
        self.log(connection_id, 'wants to unsubscribe', channel)

        if channel.startswith('#'):
            connectionsession_ids = self.get_connection_ids_for_session_key( channel[1:] )
            connectionsession_ids.remove( connection_id )
            if len(connectionsession_ids) < 1:
                self.geo_publish( connection_id, loc=None)

        if channel.startswith('@'):
            user_id = channel[1:]
            self.log('removing', connection_id, 'from', user_id )
            userconnection_ids = self.get_connection_ids_for_user_id( user_id )
            userconnection_ids.remove(connection_id)

            connection_user_ids = self.get_user_ids_for_connection_id( connection_id )
            connection_user_ids.remove(user_id)
            assert len(connection_user_ids) == 0, 'More than one user_id for connection_id %s: %s (%s)' % (connection_id, user_id, connection_user_ids)

            self.log('updated userconnection_ids for', user_id, ':', userconnection_ids)

            if not userconnection_ids:
                self.user_died(user_id)

        subscriptions = self.get_subscriptions_for_connection_id(connection_id)
        subscriptions.remove(channel)
        self.queue_master.get(channel).unsubscribe( conn )

    def user_logged_in(self, conn_or_connection_id, user):
        self.user_by_user_id[user.username] = user

    def user_died(self, user_id):
        del self.user_by_user_id[user_id]
        self.log('last', user_id, 'connection died')

    def terminate_subscriptions(self, conn_or_connection_id):
        conn, connection_id = self.to_conn_and_connection_id(conn_or_connection_id)
        self.log(connection_id, 'terminating subscriptions')

        subscriptions = self.get_subscriptions_for_connection_id(connection_id)
        for channel in list(subscriptions):
            self.unsubscribe(conn, channel)

    def geo_publish(self, conn_or_connection_id, loc):
        if not settings.MOBILE:
            return

        conn, connection_id = self.to_conn_and_connection_id(conn_or_connection_id)

        connectionuser_ids = self.get_user_ids_for_connection_id( connection_id )
        if len(connectionuser_ids) == 0:
            self.log("Can't publish - No user associated with connection_id", connection_id)
            return

        assert len(connectionuser_ids) == 1, 'More than one user_id for connection_id %s: %s' % (connection_id, connectionuser_ids)
        user_id = list(connectionuser_ids)[0]

        self.log('found user_id', user_id, 'for connection_id', connection_id)

        user = self.user_by_user_id[user_id]
        nickname = user.get_profile().nickname

        self.geo_master.locationpublish(user_internal_id=user.id, nickname=nickname, loc=loc, session_key=user.session_key)

    def geo_send(self, session_key, data):
        if not settings.MOBILE:
            return

        connection_ids = self.get_connection_ids_for_session_key( session_key )
        print 'SEND TO', connection_ids

        for connection_id in connection_ids:
            conn, connection_id = self.to_conn_and_connection_id(connection_id)
            conn.send( {'to': '#' + session_key, 'msg': data} )

class NotifConnectionBase(tornadio.SocketConnection):
    def __init__(self, *args, **kwargs):
        self.notif_master = kwargs.pop('notif_master')
        self.dead = False

        super(NotifConnectionBase, self).__init__(*args, **kwargs)

        self.notif_master.proclaim_birth(self)

    def get_connection_id(self):
        return self._protocol.session_id

    def __repr__(self):
        return '<NotifConnection %s>' % (self.get_connection_id(),)

    def __del__(self):
        self.notif_master.proclaim_death(self)

    def markDead(self):
        assert not self.dead, 'Already dead'
        self.dead = True

    def log(self, *args, **kwargs):
        print '%s: %s' % ( self.get_connection_id(), 
                    ' '.join( str(x) for x in args ),
            )

    def on_open(self, *args, **kwargs):
        self.log('OPEN')
    
    def on_close(self, *args, **kwargs):
        self.log('CLOSE')
        self.notif_master.kill(self)
    
    def on_message(self, message):
        if not self.dispatch_message(message):
            self.log('UNPARSED MESSAGE', message)
    
    def dispatch_message(self, message):
        try:
            command_handler = getattr(self, 'handle_' + message['command'])
            command_handler(message)
            return True
        except:
            unhandled_exception_handler()

    def envelope_received(self, envelope):
        self.send( envelope )

class NotifConnection(NotifConnectionBase):
    def subscribe(self, channel):
        self.notif_master.subscribe(self, channel)

    def unsubscribe(self, channel):
        self.notif_master.unsubscribe(self, channel)

    def user_login(self, channel):
        self.log('USER_LOGIN', channel)
        user = get_user_by_session_key( channel[1:] )

        if user:
            self.notif_master.user_logged_in(self, user)
            self.subscribe( '@' + user.username )
            self.subscribe( channel )

    def user_logout(self, channel):
        self.log('USER_LOGOUT', channel)
        user = get_user_by_session_key( channel[1:] )

        if user:
            self.unsubscribe( '@' + user.username )
            self.unsubscribe( channel )

    def handle_locationpublish(self, message):
        if not settings.MOBILE:
            return
        self.log('LOCATIONPUBLISH' , message)
        self.notif_master.geo_publish( self, [message['lat'],message['lng']] )

    def handle_subscribe(self, message):
        self.log( 'SUBSCRIBE', message )

        for channel in message['channels']:
            if channel.startswith('#'):
                self.user_login(channel)
            elif channel.startswith('@'):
                self.log( 'SECURITY PROBLEM @ in channel', channel )
            else:
                self.subscribe(channel)

    def handle_unsubscribe(self, message):
        self.log( 'UNSUBSCRIBE', message )
        for channel in message['channels']:
            if channel.startswith('#'):
                self.user_logout(channel)
            elif channel.startswith('@'):
                print 'SECURITY PROBLEM @ in channel', channel
            else:
                self.unsubscribe(channel)
