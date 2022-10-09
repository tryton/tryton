******
Design
******

The *Authentication SAML Module* introduces some new routes:

   - ``GET`` ``/<database>/authentication/saml/<identity>/login``:
     redirect to the identity provider location with a prepared request using
     the ``next`` argument as relay state.

   - ``GET`` ``/<database>/authentication/saml/<identity>/metadata``:
     return the metadata XML of the service provider.

   - ``POST`` ``/<database>/authentication/saml/<identity>/acs``:
     verify the authentication request and redirect to the relay state.
