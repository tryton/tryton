Party Module
############

The party module defines the concepts of party, identifier, category and
contact mechanism. It also comes with reports to print labels and letters and a
*Check VIES* wizard.


Party
*****

A party can be a person, a company or any organisation that one want
to consider as the same entity. A party is defined by a name, a code,
a language, identifiers, categories, contact mechanisms and a list of
addresses.

Two reports are available:

- The *Labels* report creates a document with the names and addresses
  of all selected parties which are preformatted to be printed on
  labels that can be stuck on an envelope.
- The *Letter* report create a document pre-filled with the company
  header, the address of the recipient, a date, a greeting, an ending
  and the signature of the current reader.

The *Check VIES* wizard allows to check the European VAT number identifier of
parties with the VIES web service.

The *Replace* wizard allows to replace duplicate record by the original and
relink all the related documents.

The *Erase* wizard allows to erase all personal data of a party from the system
included the historized data and the resources attached for all the parties
which were replaced by this one.

Address
*******

An address is made of a name, a street, a zip number, a city, a
country, a subdivision. A sequence allow to order them.
The field *Full Address* returns the formatted address included the name of the
party if the context has `address_with_party` set to True, the attention name
if the context has `address_attention_party` set to a party and without the
country if the context key `address_from_country` is the same as the country of
the address.


Address Format
**************

It allows to define per country and language, how addresses should be
formatted.

Address Subdivision Type
************************

It allows to define for each country which types of subdivision are allowed on
the address.

Contact Mechanism
*****************

A contact mechanism is made of a type, value and comment. Type can be
*Phone*, *Mobile*, *Fax*, *E-Mail*, *Website*, *Skype*, *SIP*, *IRC*,
*Jabber* or *Other*.


Category
********

A Category is just composed of a name, thus constituting tags that can
be associated to parties. Categories are organised in a tree structure.
