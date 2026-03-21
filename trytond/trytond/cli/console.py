# PYTHON_ARGCOMPLETE_OK
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import trytond.commandline as commandline
import trytond.config as config


def main():
    parser = commandline.get_parser_console()
    commandline.set_autocomplete(parser)
    options = parser.parse_args()
    config.update_etc(options.configfile)

    # Import after application is configured
    import trytond.console as console

    console.run(options)


if __name__ == '__main__':
    main()
