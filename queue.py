from fanout.client import FanoutClient
from tornado import ioloop
import cjson
jsondumps = cjson.encode
jsonloads = cjson.decode

master = None
import traceback

class QueueMaster:
    def __init__(self, queue_host, queue_port):
        self.queues = {}
        self._client = FanoutClient(self.envelope_received)
        self._client.connect( queue_host, queue_port )

    def get(self, name):
        return self.queues.setdefault(name, Queue(master=self, name=name))
    
    def envelope_received(self, envelope_data):
        try:
            envelope = jsonloads(envelope_data)
            self.get( envelope['to'] ).envelope_received(envelope)
        except:
            traceback.print_exc()
    
    def _send_envelope(self, msg):
        self._client.yell( jsondumps(msg) )
    
    def kill_queue(self, name):
        try:
            del self.queues[name]
        except:
            pass

class Queue:
    def __init__(self, master, name):
        self.master = master
        self.name = name
        self.listeners = set()
    
    def subscribe(self, listener):
        self.listeners.add(listener)

    def unsubscribe(self, listener):
        self.listeners.remove(listener)
    
    def envelope_received(self, envelope):
        print 'REC', self.name, envelope
        for l in self.listeners:
            if callable(l):
                l(envelope)
            else:
                l.envelope_received(envelope)

    def send(self, msg, envelope_extra=None):
        envelope = {'to': self.name, 'msg': msg}
        if envelope_extra:
            envelope.update(envelope_extra)
        self.master._send_envelope(envelope)
    
    def kill(self):
        self.master.kill_queue(self.name)

def start_queue(host, port):
    # print 'Starting Queue'
    global master
    master = QueueMaster(host, port)
