# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from gi.repository import Gdk


def find_hardware_keycode(string):
    keymap = Gdk.Keymap.get_for_display(Gdk.Display.get_default())
    for i, c in enumerate(string):
        found, keys = keymap.get_entries_for_keyval(
            Gdk.unicode_to_keyval(ord(c)))
        if found:
            return i
    return -1


def set_underline(label):
    "Set underscore for mnemonic accelerator"
    label = label.replace('_', '__')
    position = find_hardware_keycode(label)
    if position >= 0:
        label = label[:position] + '_' + label[position:]
    return label
