# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import atexit
import os
import readline
import sys
from code import InteractiveConsole
from rlcompleter import Completer

from trytond import __version__
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.worker import run_task


class Console(InteractiveConsole):
    def __init__(self, locals=None, filename="<console>", histsize=-1,
            histfile=os.path.expanduser("~/.trytond_console_history")):
        super().__init__(locals, filename)
        self.init_completer(locals)
        self.init_history(histfile, histsize)

    def init_completer(selfi, locals):
        completer = Completer(locals)
        readline.set_completer(completer.complete)
        readline.parse_and_bind("tab: complete")

    def init_history(self, histfile, histsize):
        readline.parse_and_bind("tab: complete")
        if hasattr(readline, 'read_history_file'):
            try:
                readline.read_history_file(histfile)
            except FileNotFoundError:
                pass
            atexit.register(self.save_history, histfile, histsize)

    def save_history(self, histfile, histsize):
        readline.set_history_length(histsize)
        readline.write_history_file(histfile)


def run(options):
    db_name = options.database_name
    pool = Pool(db_name)
    with Transaction().start(db_name, 0, readonly=True):
        pool.init()

    with Transaction().start(db_name, 0) as transaction:
        local = {
            'pool': pool,
            'transaction': transaction,
            }
        if sys.stdin.isatty():
            console = Console(local, histsize=options.histsize)
            banner = "Tryton %s, Python %s on %s" % (
                __version__, sys.version, sys.platform)
            kwargs = {}
            if sys.version_info >= (3, 6):
                kwargs['exitmsg'] = ''
            console.interact(banner=banner, **kwargs)
        else:
            console = InteractiveConsole(local)
            console.runcode(sys.stdin.read())
        transaction.rollback()
    while transaction.tasks:
        task_id = transaction.tasks.pop()
        run_task(pool, task_id)
