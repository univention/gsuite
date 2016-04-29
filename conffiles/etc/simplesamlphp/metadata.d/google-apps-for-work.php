<?php
@%@UCRWARNING=# @%@

$metadata['google.com'] = array(
@!@
from univention.googleapps.auth import GappsAuth
domain = GappsAuth.get_domain()
print"	'AssertionConsumerService'	=> array('https://www.google.com/a/%s/acs')," % domain
@!@	
	'NameIDFormat'	=> 'urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified',
	'simplesaml.nameidattribute'	=> 'univentionGoogleAppsPrimaryEmail',
	'attributes'	=> array('univentionGoogleAppsEnabled', 'univentionGoogleAppsPrimaryEmail'),
	'OrganizationName'	=> 'Google Apps for Work',
	'privacypolicy'	=> 'http://support.google.com/a/bin/answer.py?hl=en&answer=60762',
	'authproc' => array(
		10 => array(
		'class' => 'authorize:Authorize',
		'regex' => FALSE,
		'univentionGoogleAppsEnabled' => '1',
		)
	),
	70 => array(
		'class' => 'core:AttributeLimit',
		''
	),
);
