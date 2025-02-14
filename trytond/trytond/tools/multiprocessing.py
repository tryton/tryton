# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import os
from threading import Lock

_lock = Lock()


class _local_impl:
    __slots__ = 'dict', 'pid', 'localargs'

    def __init__(self, localargs):
        self.localargs = localargs
        self.reset()

    def reset(self):
        self.dict = {}
        self.pid = os.getpid()


class local:
    __slots__ = '_local_impl', '__dict__'

    def __new__(cls, /, *args, **kwargs):
        self = super().__new__(cls)
        # do not trigger __setattr__ below
        object.__setattr__(self, '_local_impl', _local_impl((args, kwargs)))
        return self

    def __getattribute__(self, name):
        impl = object.__getattribute__(self, '_local_impl')
        if impl.pid == os.getpid():
            d = impl.dict
        else:
            impl.reset()
            d = impl.dict
            args, kwargs = impl.localargs
            with _lock:
                self.__init__(*args, **kwargs)
        object.__setattr__(self, '__dict__', d)
        return object.__getattribute__(self, name)

    def __setattr__(self, name, value):
        impl = object.__getattribute__(self, '_local_impl')
        if impl.pid == os.getpid():
            d = impl.dict
        else:
            impl.reset()
            d = impl.dict
            args, kwargs = impl.localargs
            with _lock:
                self.__init__(*args, **kwargs)
        object.__setattr__(self, '__dict__', d)
        return object.__setattr__(self, name, value)
