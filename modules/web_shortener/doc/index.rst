Web Shortener Module
####################

The web_shortener module allows URLs to be shortened. It counts the number of
times the URL is accessed and optionally triggers action.

The module defines a route `/s/<shortened_id>`
which will redirect the queries to the URL registered previously with
`ShortenedURL.get_url`.

Models that need to be callable from a shortened URL must define the method
`shortened_url_execute`. This class method will be called from the underlying
queue with the record and the keywords arguments transmitted when calling
`get_url`.

Shortened URL
*************

- Shortened URL: The shortened URL
- Redirect URL: The URL the request is redirected to
- Record: The record on which `method` will be executed
- Method: The name of the method to call on `record`
- Count: The number of times this shortened URL has been triggered

Configuration
*************

The web_shortener modules uses the parameter from the section:

- `[web]`:

    - `shortener_base`: The base URL without path for shortened URL.
      The default value is composed with the configuration `[web]` `hostname`.
