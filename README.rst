This repository contains all the packages of Tryton.

To have symlinks for modules created automatically on Mercurial update, add
the following line to the hooks section of your .hg/hgrc:

    update.modules = .hooks/link_modules

To automatically generate requirements files on Mercurial update, add
the following line to the hooks section of your .hg/hgrc:

    update.requirements = .hooks/update_requirements

.. warning::

    The process of updating requirements files may take some time

Then you can install the required dependencies with:

    pip install -r requirements.txt

And you can also install the development dependencies with:

    pip install -r requirements-dev.txt
