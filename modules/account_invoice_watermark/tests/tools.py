# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import subprocess
from tempfile import TemporaryDirectory

__all__ = ['pdf_contains']


def pdf_contains(pdf, text):
    with TemporaryDirectory() as dirname:
        input_file = os.path.join(dirname, 'input.pdf')
        output_file = os.path.join(dirname, 'output.text')
        with open(input_file, 'wb') as fp:
            fp.write(pdf)
        subprocess.check_call([
                'mutool', 'convert', '-F', 'text',
                '-o', output_file, input_file])
        with open(output_file, 'r') as fp:
            return text in fp.read()
