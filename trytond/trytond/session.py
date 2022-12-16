#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import random
import time


class Session(int):

    def __init__(self, x):
        super(Session, self).__init__()
        self.__data = {
            'session': str(random.random()),
            'timestamp': time.time(),
        }

    def __getattr__(self, name):
        return self.__data[name]

    def __getitem__(self, name):
        return self.__data[name]

    def reset_timestamp(self):
        self.__data['timestamp'] = time.time()
