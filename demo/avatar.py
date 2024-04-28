# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import os

_AVATAR_DIR = os.path.join(os.path.dirname(__file__), 'avatars')


def get(name):
    with open(os.path.join(_AVATAR_DIR, name), 'rb') as fp:
        return fp.read()
