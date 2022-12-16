#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import os
import base64
import time


class Session(int):

    def __init__(self, value):
        super(Session, self).__init__()
        self.__data = {
            'session': base64.b64encode(os.urandom(32)),
            'timestamp': time.time(),
            'name': '',
        }

    def __getattr__(self, name):
        return self.__data[name]

    def __getitem__(self, name):
        return self.__data[name]

    def reset_timestamp(self):
        self.__data['timestamp'] = time.time()
