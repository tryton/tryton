# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import sys
import os
from os import path
from sphinx.util.console import nocolor
from sphinx.application import Sphinx

srcdir = confdir = path.abspath(path.normpath(path.dirname(__file__)))
outdir = os.path.join(srcdir, 'html')
static_dir = os.path.join(srcdir, 'static')
doctreedir = path.join(outdir, '.doctrees')
status = sys.stdout
confoverrides = {}
freshenv = True
buildername = 'html'
if not path.isdir(outdir):
    os.mkdir(outdir)
if not path.isdir(static_dir):
    os.mkdir(static_dir)
nocolor()

app = Sphinx(srcdir, confdir, outdir, doctreedir, buildername,
             confoverrides, status, sys.stderr, freshenv)
app.builder.build_all()
