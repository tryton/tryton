# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import os
from threading import RLock

_lock = RLock()


class _local_impl:
    __slots__ = 'dict', 'pid', 'localargs', 'initialized'

    def __init__(self, localargs):
        self.localargs = localargs
        self.pid = os.getpid()
        self.initialized = None

    def initialize(self, local_obj):
        self.initialized = False
        self.pid = os.getpid()
        self.dict = {}
        object.__setattr__(local_obj, '__dict__', self.dict)
        args, kwargs = self.localargs
        init = object.__getattribute__(local_obj, '__init__')
        init(*args, **kwargs)
        self.initialized = True


# We'll be using the double-checked locking technique to have a fast path in
# the code once the local object has been initialized.
# https://en.wikipedia.org/wiki/Double-checked_locking
#
# But it comes with a twist because we're using a re-entrant lock and a call to
# __getattribute__ could trigger a call to __setattr__ through the __init__
# call.
#
# Hence this is why the second check is not exactly the same as the first one.
# None means that it's not yet started, False that we're initializing the
# object and True that it's fully initialized. We're taking advantage of the
# difference between False and None to initialize the object without triggering
# an infinite recursion.
def _initialize_for_current_process(local_obj):
    impl = object.__getattribute__(local_obj, '_local_impl')
    if not impl.initialized or impl.pid != os.getpid():
        with _lock:
            if impl.initialized is None or impl.pid != os.getpid():
                impl.initialize(local_obj)


class local:
    __slots__ = '_local_impl', '__dict__'

    def __new__(cls, /, *args, **kwargs):
        self = super().__new__(cls)
        # do not trigger __setattr__ below
        object.__setattr__(self, '_local_impl', _local_impl((args, kwargs)))
        return self

    def __getattribute__(self, name):
        _initialize_for_current_process(self)
        return object.__getattribute__(self, name)

    def __setattr__(self, name, value):
        _initialize_for_current_process(self)
        return object.__setattr__(self, name, value)
