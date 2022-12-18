#!/usr/bin/env python
#
# Requires $RTD_CONFIG to point to a file providing the webhook data for each
# package. The file is in Python cfg file format.
# Each section defines on package. Example::
#
#    [modules/party]
#    url: https://readthedocs.org/api/v2/webhook/modules-party/12345/
#    token: 93afe1ce2d1107597f69774009964990c0643dad

import configparser
import sys
from argparse import ArgumentParser
from urllib import request
from urllib.parse import urlencode

parser = ArgumentParser()
parser.add_argument('--config', '-c', required=True)
parser.add_argument('--package', '-p', required=True)
parser.add_argument('--branches', '-b', nargs='*')
args = parser.parse_args()

cfg = configparser.ConfigParser()
cfg.read(args.config)

url = cfg.get(args.package, 'url')
token = cfg.get(args.package, 'token')
if not url:
    sys.exit(f"Missing url for {args.package!r}")
elif not token:
    sys.exit(f"Missing token for {args.package!r}")

data = [
    ('token', token),
    *(('branches', branch) for branch in args.branches),
    ]

req = request.Request(
    url,
    data=urlencode(data).encode(),
    headers={
        'User-Agent': 'python-urllib/%s' % request.__version__,
        })
with request.urlopen(req) as resp:
    print(resp.read())
