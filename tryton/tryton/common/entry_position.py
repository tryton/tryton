# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.


def reset_position(entry):
    if entry.get_alignment() <= 0.5:
        entry.set_position(0)
    else:
        entry.set_position(-1)
