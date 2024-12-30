#!/bin/env python
import glob
import os
import sys
from itertools import chain
from string import Template

BASE_DIR = os.path.dirname(__file__)
TEMPLATE = Template("""
check-doc-${name}:
  extends: .check-doc
  variables:
    PACKAGE: ${package}

test-${name}-sqlite:
  extends: .test-sqlite
  variables:
    PACKAGE: ${package}
    TAG_PATTERN: '/^${tag_name}-.*/'
${extra}
test-${name}-postgresql:
  extends: .test-postgresql
  variables:
    PACKAGE: ${package}
    TAG_PATTERN: '/^${tag_name}-.*/'
${extra}""")
RESOURCE_GROUPS = {
    'account_fr_chorus': 'chorus',
    'account_payment_stripe': 'stripe',
    'web_shop_shopify': 'shopify',
    }


def main(filename):
    if filename == '-':
        render(sys.stdout)
    else:
        with open(filename, 'w') as file:
            render(file)


def render(file):
    packages = sorted(all_packages())
    for package in packages:
        name = tag_name = package.replace('/', '-')
        if tag_name.startswith('modules-'):
            tag_name = tag_name[len('modules-'):]
        if resource_group := RESOURCE_GROUPS.get(tag_name):
            extra = '  resource_group: ' + resource_group + '\n'
        else:
            extra = ''
        mapping = {
            'name': name,
            'package': package,
            'tag_name': tag_name,
            'extra': extra,
            }
        file.write(TEMPLATE.substitute(mapping))


def all_packages():
    root_dir = os.path.dirname(BASE_DIR)
    for filename in chain(
            glob.glob('modules/*/setup.py', root_dir=root_dir)):
        yield os.path.dirname(filename)


if __name__ == '__main__':
    try:
        filename = sys.argv[1]
    except IndexError:
        filename = '-'
    main(filename)
