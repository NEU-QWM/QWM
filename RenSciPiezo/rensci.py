"""
Script Name: rensci.py
Author: Sasha Zibrov
Date: 2026-05-13
Description: Driver to operate the Renaissance Scientific Piezo Stage
"""

import socket
import json
import threading
import atexit
from contextlib import contextmanager

from functools import wraps

import time

DEFAULT_AMPLITUDE = 100  # V
DEFAULT_FREQUENCY = 1000 # Hz


DEFAULT_CHANNEL = {'x':1, 'y':2, 'z':3}
DEFAULT_HOME = {'x': 0, 'y':0, 'z': 7.5}

def wait_for_motion(func):
    
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        result = func(self, *args, **kwargs)

        self.wait_motion_done()
        return result
    return wrapper

class RenSciDriver:
    def __init__(self, host='localhost', port=6002, timeout=2.0, auto_reconnect=True):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.auto_reconnect = auto_reconnect    
        self._sock = None
        self._lock = threading.RLock()
        self._rpc_id = 0
        atexit.register(self.disconnect)

    def connect(self):
        with self._lock:
            if self._sock is not None:
                # print('Already connected')
                return
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((self.host, self.port))
            self._sock = sock
            print(f'Connected to {self.host}:{self.port}')
    
    def disconnect(self):
        with self._lock:
            if self._sock:
                print('Disconnecting from server')
                try:
                    self._sock.shutdown(socket.SHUT_RDWR)
                except Exception as OSError:
                    pass  # Ignore errors during shutdown

                try:
                    self._sock.close()
                finally:
                    self._sock = None
            else:
                print('Not connected')
    
    def reconnect(self):
        print('Reconnecting to server')
        self.disconnect()
        self.connect()
    
    @property
    def is_connected(self):
        return self._sock is not None
    
    def _next_id(self):
        self._rpc_id += 1
        return self._rpc_id
    
    def rpc(self, method, params=None):
        # if params is None:
            # params = {}
        message = {
            'jsonrpc': '2.0',
            'method': method,
            # 'params': params,
            'id': self._next_id()
        }
        if params:
            message['params'] = params

        payload = json.dumps(message).encode('utf-8')

        with self._lock:
            self.connect()

            try:
                self._sock.sendall(payload)
                raw = self._sock.recv(128)
            except (BrokenPipeError, ConnectionResetError, socket.timeout, OSError):
                if not self.auto_reconnect:
                    raise
                self.reconnect()
                # retry the request after reconnecting
                self._sock.sendall(payload)
                raw = self._sock.recv(128)

        response = json.loads(raw)
        if "error" in response:
            err = response["error"]
            code = err.get("code", "unknown")
            message = err.get("message", str(err))
            raise RuntimeError( f"JSON-RPC error {code}: {message}")
        
        return response
    
    @contextmanager
    def session(self):
        self.connect()
        try:
            yield self
        finally:
            self.disconnect()



    @wait_for_motion 
    def goStepsForward(self, channel=1, steps=100, amplitude = DEFAULT_AMPLITUDE , frequency = DEFAULT_FREQUENCY):
        return self.rpc('goStepsForward',[channel, steps, amplitude, frequency])
    
    @wait_for_motion 
    def goStepsReverse(self, channel=1, steps=100, amplitude = DEFAULT_AMPLITUDE , frequency = DEFAULT_FREQUENCY):
        return self.rpc('goStepsReverse',[channel, steps, amplitude, frequency])

    @wait_for_motion 
    def goPosition(self, channel=1, target=0.0, amplitude = DEFAULT_AMPLITUDE , frequency = DEFAULT_FREQUENCY):
        t0 = time.time()
        return self.rpc('goPosition', [channel, target*1e-3, amplitude, frequency])

    @wait_for_motion     
    def goInterval(self, channel=1, delta=0.1, amplitude = DEFAULT_AMPLITUDE , frequency = DEFAULT_FREQUENCY):
        return self.rpc('goInterval', [channel, delta*1e-3, amplitude, frequency])
    
    def getStatusPositioning(self):
        return self.rpc('getStatusPositioning').get('result')
    
    def stopPositioning(self):
        return self.rpc('stopPositioning')
    
    def getPosition(self, channel):
        return self.rpc('getPosition', [channel]).get('result')*1e3
    
    def home(self):
        for ax in [1,2]:
            self.goPosition(ax, target=0.0, amplitude = DEFAULT_AMPLITUDE , frequency =1000)
        self.goPosition(3, target=7.5, amplitude = DEFAULT_AMPLITUDE , frequency =1000)

    def wait_motion_done(self, poll=0.02, timeout=60, start_timeout=1.0):
        t0 = time.monotonic()

        started = False
        while (time.monotonic() - t0 < start_timeout):
            moving = self.getStatusPositioning()
            if moving:
                started = True
                break

            time.sleep(poll)
        if not started:
            return
        
        while True:
            moving = self.getStatusPositioning()
            if not moving:
                return
            if (time.monotonic() - t0 > timeout):
                raise TimeoutError()
            time.sleep(poll)
    


    