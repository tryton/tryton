#!/bin/env python
import glob
import os
import sys
from itertools import chain
from string import Template

BASE_DIR = os.path.dirname(__file__)
TEMPLATE_DOC = Template("""
check-doc-${name}:
  extends: .check-doc
  variables:
     PACKAGE: ${package}

trigger-doc-build-${name}:
  extends: .trigger-doc-build
  variables:
     PACKAGE: ${package}

""")

TEMPLATE = Template("""
test-${name}:
  extends: .test-tox
  variables:
    PACKAGE: ${package}
    TAG_PATTERN: '/^${tag_name}-.*/'

""")

TEMPLATE_IMAGE = Template("""
test-${name}:
  extends: .test-tox
  image: $${CI_DEPENDENCY_PROXY_GROUP_IMAGE_PREFIX}/tryton/${package}-test:$${PYTHON_VERSION}
  variables:
    PACKAGE: ${package}
    TAG_PATTERN: '/^${tag_name}-.*/'

""")  # noqa: E501

TEMPLATE_DB = Template("""
test-${name}-sqlite:
  extends: .test-sqlite
  variables:
    PACKAGE: ${package}
    TAG_PATTERN: '/^${tag_name}-.*/'

test-${name}-postgresql:
  extends: .test-postgresql
  variables:
    PACKAGE: ${package}
    TAG_PATTERN: '/^${tag_name}-.*/'

""")

TEMPLATE_GIS = Template("""
test-${name}-postgis:
  extends: .test-postgis
  variables:
    PACKAGE: ${package}
    TAG_PATTERN: '/^${tag_name}-.*/'

""")

TEMPLATE_NPM_IMAGE = Template("""
test-${name}:
  extends: .test-npm
  image: $${CI_DEPENDENCY_PROXY_GROUP_IMAGE_PREFIX}/tryton/${package}-test
  variables:
    PACKAGE: ${package}
    TAG_PATTERN: '/^${tag_name}-.*/'

""")

NO_DB = {'proteus'}
CUSTOM_IMAGE = {'tryton'}
CUSTOM_NPM_IMAGE = {'sao'}
GIS = {'trytond-gis'}


def main(filename):
    if filename == '-':
        render(sys.stdout)
    else:
        with open(filename, 'w') as file:
            render(file)


def render(file):
    file.write(open(os.path.join(BASE_DIR, 'gitlab-ci.yml'), 'r').read())
    packages = list(all_packages())
    for package in packages:
        name = tag_name = package.replace('/', '-')
        if tag_name.startswith('modules-'):
            tag_name = tag_name[len('modules-'):]
        mapping = {
            'name': name,
            'package': package,
            'tag_name': tag_name,
            }
        if os.path.exists(os.path.join(package, 'doc')):
            file.write(TEMPLATE_DOC.substitute(mapping))
        if (not os.path.exists(os.path.join(package, 'tox.ini'))
                and not os.path.exists(os.path.join(package, 'package.json'))):
            continue
        if package in NO_DB:
            file.write(TEMPLATE.substitute(mapping))
        elif package in CUSTOM_IMAGE:
            file.write(TEMPLATE_IMAGE.substitute(mapping))
        elif package in CUSTOM_NPM_IMAGE:
            file.write(TEMPLATE_NPM_IMAGE.substitute(mapping))
        elif package in GIS:
            file.write(TEMPLATE_GIS.substitute(mapping))
        else:
            file.write(TEMPLATE_DB.substitute(mapping))


def all_packages():
    root_dir = os.path.dirname(BASE_DIR)
    for filename in chain(
            glob.glob('*/setup.py', root_dir=root_dir),
            glob.glob('modules/*/setup.py', root_dir=root_dir),
            glob.glob('*/package.json', root_dir=root_dir)):
        yield os.path.dirname(filename)


if __name__ == '__main__':
    try:
        filename = sys.argv[1]
    except IndexError:
        filename = '-'
    main(filename)
