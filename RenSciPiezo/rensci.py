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
from typing import Callable, Generator, Optional


from functools import wraps

import time

DEFAULT_AMPLITUDE = 100  # V
DEFAULT_FREQUENCY = 1000 # Hz


DEFAULT_CHANNEL = {'x':1, 'y':2, 'z':3}
DEFAULT_HOME = {'x': 0, 'y':0, 'z': 7.5}

# def wait_for_motion(func):
    
#     @wraps(func)
#     def wrapper(self, *args, **kwargs):
#         result = func(self, *args, **kwargs)

#         self.wait_motion_done()
#         return result
#     return wrapper

def wait_open_loop(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        result = func(self, *args, **kwargs)
        self.wait_open_loop_done()
        return result
    return wrapper

def wait_closed_loop(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        result = func(self, *args, **kwargs)
        self.wait_closed_loop_done()
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

    @wait_open_loop
    def goStepsForward(
        self,
        channel:   int   = 1,
        steps:     int   = 100,
        amplitude: float = DEFAULT_AMPLITUDE,
        frequency: int   = DEFAULT_FREQUENCY,
    ) -> bool:
        """Move *steps* steps forward on *channel*.  Returns True if accepted."""
        return bool(self.rpc("goStepsForward", [channel, steps, amplitude, frequency]).get("result"))
    
    @wait_open_loop
    def goStepsReverse(
        self,
        channel:   int   = 1,
        steps:     int   = 100,
        amplitude: float = DEFAULT_AMPLITUDE,
        frequency: int   = DEFAULT_FREQUENCY,
    ) -> bool:
        return bool(self.rpc("goStepsReverse", [channel, steps, amplitude, frequency]).get("result"))

    def goContinuousForward(
        self,
        channel:   int   = 1,
        amplitude: float = DEFAULT_AMPLITUDE,
        frequency: int   = DEFAULT_FREQUENCY,
    ) -> bool:
        return bool(self.rpc("goContinuousForward", [channel, amplitude, frequency]).get("result"))

    def goContinuousReverse(
        self,
        channel:   int   = 1,
        amplitude: float = DEFAULT_AMPLITUDE,
        frequency: int   = DEFAULT_FREQUENCY,
    ) -> bool:
        return bool(self.rpc("goContinuousReverse", [channel, amplitude, frequency]).get("result"))

    # ── Closed-loop motion  ────────────────────────────
    def getPosition(self, channel: int) -> float:
        """Returns position in **metres** (wire protocol)."""
        return float(self.rpc("getPosition", [channel]).get("result")*1e3)
    
    @wait_closed_loop
    def goPosition(
        self,
        channel:   int,
        target:    float,           # mm
        amplitude: float = DEFAULT_AMPLITUDE,
        frequency: int   = DEFAULT_FREQUENCY,
    ) -> bool:
        return bool(self.rpc("goPosition", [channel, target*1e-3, amplitude, frequency]).get("result"))

    @wait_closed_loop
    def goInterval(
        self,
        channel:   int,
        delta:     float,           # mm
        amplitude: float = DEFAULT_AMPLITUDE,
        frequency: int   = DEFAULT_FREQUENCY,
    ) -> bool:
        return bool(self.rpc("goInterval", [channel, delta*1e-3, amplitude, frequency]).get("result"))

    def holdPosition(
        self,
        channel:   int,
        target:    float,           # mm    
        amplitude: float = DEFAULT_AMPLITUDE,
        timeout:   int   = 30,
    ) -> bool:
        return bool(self.rpc("holdPosition", [channel, target*1e-3, amplitude, timeout]).get("result"))

    def setStopLimit(self, channel: int, threshold: float) -> bool:
        """threshold in metres."""
        return bool(self.rpc("setStopLimit", [channel, threshold]).get("result"))

    def getStopLimit(self, channel: int) -> float:
        return float(self.rpc("getStopLimit", [channel]).get("result"))

    def stopPositioning(self) -> bool:
        return bool(self.rpc("stopPositioning").get("result"))

    def getStatusPositioning(self) -> bool:
        """True while a closed-loop command (goPosition/goInterval/holdPosition) is running."""
        return bool(self.rpc("getStatusPositioning").get("result"))

    def setSensorsOff(self) -> bool:
        return bool(self.rpc("setSensorsOff").get("result"))

    # ── General commands ──────────────────────────────────────────

    def stopMotion(self) -> bool:
        """Stop any open-loop motion."""
        return bool(self.rpc("stopMotion").get("result"))

    def setDriveChannel(self, channel: int) -> bool:
        return bool(self.rpc("setDriveChannel", [channel]).get("result"))

    def setDriveChannelsOff(self) -> bool:
        return bool(self.rpc("setDriveChannelsOff").get("result"))

    def getDriveChannel(self) -> int:
        return int(self.rpc("getDriveChannel").get("result"))

    def getStatusDriveBusy(self) -> bool:
        """True while an open-loop command (goSteps*) is running."""
        return bool(self.rpc("getStatusDriveBusy").get("result"))

    def getStatusDriveOverload(self) -> bool:
        return bool(self.rpc("getStatusDriveOverload").get("result"))

    # ── Wait helpers ───────────────────────────────────────────────────────

    def wait_open_loop_done(
        self,
        poll:          float = 0.05,
        timeout:       float = 60.0,
        start_timeout: float = 2.0,
        settle_count:  int   = 3,
    ):
        """
        Block until an open-loop move (goSteps*) is complete.

        Uses getStatusDriveBusy() — the correct call for open-loop moves per
        the manual (§9.2.3).  Requires *settle_count* consecutive False readings
        to avoid false exit on transient relay-switching gaps.
        """
        self._wait_flag(
            flag_fn       = self.getStatusDriveBusy,
            label         = "open-loop",
            poll          = poll,
            timeout       = timeout,
            start_timeout = start_timeout,
            settle_count  = settle_count,
        )

    def wait_closed_loop_done(
        self,
        poll:          float = 0.05,
        timeout:       float = 120.0,
        start_timeout: float = 2.0,
        settle_count:  int   = 3,
    ):
        """
        Block until a closed-loop move (goPosition/goInterval) is complete.

        Uses getStatusPositioning() per manual §9.2.2.
        """
        self._wait_flag(
            flag_fn       = self.getStatusPositioning,
            label         = "closed-loop",
            poll          = poll,
            timeout       = timeout,
            start_timeout = start_timeout,
            settle_count  = settle_count,
        )

    def _wait_flag(
        self,
        flag_fn:       Callable[[], bool],
        label:         str,
        poll:          float,
        timeout:       float,
        start_timeout: float,
        settle_count:  int,
    ):
        """
        Generic poller: waits for flag_fn() to return True (motion started),
        then waits for it to return False *settle_count* times in a row (motion
        done) before returning.

        If the flag never goes True within start_timeout the motion may have
        finished before the first poll — we fall through to the settle loop so
        fast moves are handled correctly.
        """
        t0 = time.monotonic()

        # Phase 1 – wait for motion to begin
        started = False
        while time.monotonic() - t0 < start_timeout:
            if flag_fn():
                started = True
                break
            time.sleep(poll)

        if not started:
            # Could be a very fast move that already finished, or a genuine
            # non-start.  Either way, fall through – the settle loop will exit
            # immediately on N consecutive False readings.
            pass

        # Phase 2 – wait for motion to end, confirmed by N stable False readings
        consecutive_stops = 0
        while True:
            elapsed = time.monotonic() - t0
            if elapsed > timeout:
                raise TimeoutError(
                    f"[NP-Drive] {label} move not done after {timeout:.1f}s"
                )
            if flag_fn():
                consecutive_stops = 0  # still moving – reset counter
            else:
                consecutive_stops += 1
                if consecutive_stops >= settle_count:
                    return          # confirmed stopped
            time.sleep(poll)




    # @wait_for_motion 
    # def goStepsForward(self, channel=1, steps=100, amplitude = DEFAULT_AMPLITUDE , frequency = DEFAULT_FREQUENCY):
    #     return self.rpc('goStepsForward',[channel, steps, amplitude, frequency])
    
    # @wait_for_motion 
    # def goStepsReverse(self, channel=1, steps=100, amplitude = DEFAULT_AMPLITUDE , frequency = DEFAULT_FREQUENCY):
    #     return self.rpc('goStepsReverse',[channel, steps, amplitude, frequency])

    # @wait_for_motion 
    # def goPosition(self, channel=1, target=0.0, amplitude = DEFAULT_AMPLITUDE , frequency = DEFAULT_FREQUENCY):
    #     t0 = time.time()
    #     return self.rpc('goPosition', [channel, target*1e-3, amplitude, frequency])

    # @wait_for_motion     
    # def goInterval(self, channel=1, delta=0.1, amplitude = DEFAULT_AMPLITUDE , frequency = DEFAULT_FREQUENCY):
    #     return self.rpc('goInterval', [channel, delta*1e-3, amplitude, frequency])
    
    # def getStatusPositioning(self):
    #     return self.rpc('getStatusPositioning').get('result')
    
    # def stopPositioning(self):
    #     return self.rpc('stopPositioning')
    
    # # @wait_for_motion
    # def getPosition(self, channel):
    #     return self.rpc('getPosition', [channel]).get('result')*1e3
    
    # def home(self):
    #     for ax in [1,2]:
    #         self.goPosition(ax, target=0.0, amplitude = DEFAULT_AMPLITUDE , frequency =1000)
    #     self.goPosition(3, target=7.5, amplitude = DEFAULT_AMPLITUDE , frequency =1000)

    # def wait_motion_done(self, poll=0.05, timeout=60, start_timeout=2.0, settle_count=3):
    #     t0 = time.monotonic()

    #     # Phase 1: wait for motion to BEGIN (with generous timeout)
    #     started = False
    #     while (time.monotonic() - t0 < start_timeout):
    #         if self.getStatusPositioning():
    #             started = True
    #             break
    #         time.sleep(poll)

    #     if not started:
    #         # Controller may have moved so fast it's already done,
    #         # OR it never started. Either way, give it one more check.
    #         print("Warning: motion may have completed before polling began")
    #         # Don't return — fall through and verify position is stable

    #     # Phase 2: wait for motion to END, confirmed by N consecutive stops
    #     consecutive_stops = 0
    #     while True:
    #         elapsed = time.monotonic() - t0
    #         if elapsed > timeout:
    #             raise TimeoutError(f"Motion not done after {timeout}s")

    #         moving = self.getStatusPositioning()

    #         if moving:
    #             consecutive_stops = 0  # reset — still going
    #         else:
    #             consecutive_stops += 1
    #             if consecutive_stops >= settle_count:
    #                 print(f"Motion done (confirmed {settle_count}x)")
    #                 return

    #         time.sleep(poll)
        


    