# PYTHON_ARGCOMPLETE_OK
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import trytond.commandline as commandline
import trytond.config as config


def main():
    parser = commandline.get_parser_admin()
    commandline.set_autocomplete(parser)
    options = parser.parse_args()
    if options.indexes is None:
        options.indexes = bool(options.update)
    config.update_etc(options.configfile)
    commandline.config_log(options)

    # Import after application is configured
    import trytond.admin as admin

    admin.run(options)


if __name__ == '__main__':
    main()
