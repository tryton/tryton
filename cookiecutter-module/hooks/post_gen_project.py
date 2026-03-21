import os
import shutil

try:
    os.symlink('doc/index.rst', 'README.rst')
except (AttributeError, OSError):
    shutil.copyfile('doc/index.rst', 'README.rst')

{% if cookiecutter.prefix %}
try:
    os.symlink('.', '{{ cookiecutter.package_name }}')
except (AttributeError, OSError):
    pass
{% endif %}
