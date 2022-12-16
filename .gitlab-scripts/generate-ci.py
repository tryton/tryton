#!/bin/env python
import glob
import os
import subprocess
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
  ${stage}
  ${when}

""")

TEMPLATE_IMAGE = Template("""
test-${name}:
  extends: .test-tox
  image: $${CI_DEPENDENCY_PROXY_GROUP_IMAGE_PREFIX}/tryton/${package}-test:$${PYTHON_VERSION}
  variables:
    PACKAGE: ${package}
  ${stage}
  ${when}

""")  # noqa: E501

TEMPLATE_DB = Template("""
test-${name}-sqlite:
  extends: .test-sqlite
  variables:
    PACKAGE: ${package}
  ${stage}
  ${when}

test-${name}-postgresql:
  extends: .test-postgresql
  variables:
    PACKAGE: ${package}
  ${stage}
  ${when}

""")

TEMPLATE_GIS = Template("""
test-${name}-postgis:
  extends: .test-postgis
  variables:
    PACKAGE: ${package}
  ${stage}
  ${when}

""")

TEMPLATE_NPM_IMAGE = Template("""
test-${name}:
  extends: .test-npm
  image: $${CI_DEPENDENCY_PROXY_GROUP_IMAGE_PREFIX}/tryton/${package}-test
  variables:
    PACKAGE: ${package}
  ${stage}
  ${when}

""")

STAGE_MANUAL = "stage: manual"
WHEN_MANUAL = """
  allow_failure: true
  rules:
    - when: manual
"""
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
    modified = set(modified_packages(packages))
    for package in packages:
        mapping = {
            'name': package.replace('/', '-'),
            'package': package,
            'stage': STAGE_MANUAL if package not in modified else '',
            'when': WHEN_MANUAL if package not in modified else '',
            }
        if os.path.exists(os.path.join(package, 'doc')):
            file.write(TEMPLATE_DOC.substitute(mapping))
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
            glob.glob('**/setup.py', recursive=True, root_dir=root_dir),
            glob.glob('**/package.json', recursive=True, root_dir=root_dir)):
        yield os.path.dirname(filename)


def modified_packages(packages):
    env = os.environ.copy()
    env['HGPLAIN'] = '1'
    if env.get('CI_COMMIT_TAG'):
        tagged = env['CI_COMMIT_TAG'].split('-')[0]
        for package in packages:
            if tagged in package:
                yield package
    else:
        if not subprocess.run(
                ['hg', 'topic', '--current'],
                env=env, stdout=subprocess.DEVNULL).returncode:
            cmd = ['hg', 'status', '--rev', 's0', '--no-status']
        else:
            cmd = ['hg', 'status', '--change', '.', '--no-status']
        proc = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, text=True)
        proc.check_returncode()
        modified_files = proc.stdout.splitlines()

        modified = set()
        for filename in modified_files:
            parts = filename.split(os.sep)
            modified.add(parts[0])
            modified.add(os.sep.join(parts[:2]))
        for package in packages:
            if package in modified:
                yield package


if __name__ == '__main__':
    try:
        filename = sys.argv[1]
    except IndexError:
        filename = '-'
    main(filename)
