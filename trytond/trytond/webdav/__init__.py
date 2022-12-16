#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from ..pool import Pool
from .webdav import *


def register():
    Pool.register(
        Collection,
        Share,
        Attachment,
        module='webdav', type_='model')
