French Account Module
#####################

The French account module defines the standard chart of account

A wizard allows to generate the FEC file for a fiscal year.

Configuration
*************

The account_fr module uses the section `account_fr` to retrieve some parameters:

- `fec_opening_code`: defines the journal code for the opening balance in the
  FEC file. The default value is `OUV`.

- `fec_opening_name`: defines the journal name for the opening balance in the
  FEC file. The default value is `Balance Initiale`.

- `fec_opening_number`: defines the number of the opening balance in the FEC
  file. The default value is `0`.
