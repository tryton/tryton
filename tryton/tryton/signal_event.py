# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"Signal event"


class SignalEvent(object):
    "Signal event"

    def __init__(self):
        self.__connects = {}

    def signal(self, signal, signal_data=None):
        for fnct, data, key in self.__connects.get(signal, []):
            fnct(self, signal_data, *data)
        return True

    def signal_connected(self, signal):
        return bool(self.__connects.get(signal))

    def signal_connect(self, key, signal, fnct, *data):
        self.__connects.setdefault(signal, [])
        if (fnct, data, key) not in self.__connects[signal]:
            self.__connects[signal].append((fnct, data, key))
        return True

    def signal_unconnect(self, key, signal=None):
        if signal is None:
            signal = self.__connects.keys()
        else:
            signal = [signal]
        for sig in signal:
            i = 0
            while i < len(self.__connects[sig]):
                if self.__connects[sig][i][2] is key:
                    del self.__connects[sig][i]
                else:
                    i += 1
        return True

    def destroy(self):
        self.__connects = {}
