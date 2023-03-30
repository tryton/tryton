{{ '#' * (cookiecutter.module_name|replace('_', ' ')|title|length + 7) }}
{{ cookiecutter.module_name.replace('_', ' ').title() }} Module
{{ '#' * (cookiecutter.module_name|replace('_', ' ')|title|length + 7) }}

.. to remove, see https://www.tryton.org/develop/guidelines/documentation#index.rst

.. toctree::
   :maxdepth: 2

   setup
   usage
   configuration
   design
   reference
   releases
