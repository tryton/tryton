import os
import shutil

try:
    os.symlink('doc/index.rst', 'README.rst')
except (AttributeError, OSError):
    shutil.copyfile('doc/index.rst', 'README.rst')
