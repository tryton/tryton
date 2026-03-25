#!/usr/bin/env python3
import sys
import xml.etree.ElementTree as ET


def _replace_path(root, tag, attribute, old_prefix, new_prefix):
    for element in root.iter(tag):
        original_path = element.get(attribute)

        if old_prefix and original_path.startswith(old_prefix):
            new_path = original_path.replace(old_prefix, new_prefix, 1)
            element.set(attribute, new_path)
        elif not old_prefix:
            new_path = new_prefix + original_path
            element.set(attribute, new_path)


def rewrite_coverage_xml(file_path, old_prefix, new_prefix):
    tree = ET.parse(file_path)
    root = tree.getroot()

    if root.tag == 'coverage':
        _replace_path(root, 'class', 'filename', old_prefix, new_prefix)
    elif root.tag == 'testsuites':
        _replace_path(root, 'testcase', 'file', old_prefix, new_prefix)

    tree.write(file_path)


if __name__ == "__main__":
    old_prefix, new_prefix, *file_paths = sys.argv[1:]
    for file_path in file_paths:
        rewrite_coverage_xml(file_path, old_prefix, new_prefix)
