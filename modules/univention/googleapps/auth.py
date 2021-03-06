#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
#
# Univention Google Apps for Work App - handle auth
#
# Copyright 2016-2019 Univention GmbH
#
# http://www.univention.de/
#
# All rights reserved.
#
# The source code of this program is made available
# under the terms of the GNU Affero General Public License version 3
# (GNU AGPL V3) as published by the Free Software Foundation.
#
# Binary versions of this program provided by Univention to you as
# well as other copyrighted, protected or trademarked materials like
# Logos, graphics, fonts, specific documentations and configurations,
# cryptographic keys etc. are subject to a license agreement between
# you and Univention and not subject to the GNU AGPL V3.
#
# In the case you use this program under the terms of the GNU AGPL V3,
# the program is provided in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License with the Debian GNU/Linux or Univention distribution in file
# /usr/share/common-licenses/AGPL-3; if not, see
# <http://www.gnu.org/licenses/>.


import httplib2
import json
import sys
from urllib import quote
import os.path

from googleapiclient.discovery import build
from httplib2 import SSLHandshakeError
from oauth2client.file import Storage
from oauth2client.client import AccessTokenRefreshError, Error as Oauth2ClientError
from oauth2client.service_account import ServiceAccountCredentials

from univention.googleapps.logging2udebug import get_logger
from univention.lib.i18n import Translation
from univention.config_registry import ConfigRegistry
from univention.config_registry.frontend import ucr_update
from univention.config_registry import handler_commit
import univention.admin.modules as udm_modules
import univention.admin.objects as udm_objects
import univention.admin.uexceptions as udm_exceptions
import univention.admin.uldap as udm_uldap


_ = Translation('univention-googleapps').translate
ucr = ConfigRegistry()
ucr.load()


CONFDIR = "/etc/univention-google-apps"
CREDENTIALS_FILE = os.path.join(CONFDIR, "credentials.json")
SCOPE = [
	"https://www.googleapis.com/auth/admin.directory.user",
	"https://www.googleapis.com/auth/admin.directory.group",
	"https://www.googleapis.com/auth/admin.directory.group.member",
	"https://www.googleapis.com/auth/admin.directory.domain.readonly"]
GOOGLE_APPS_SERVICEPROVIDER_DN = "SAMLServiceProviderIdentifier=google.com,cn=saml-serviceprovider,cn=univention,%s" % ucr['ldap/base']


logger = get_logger("google-apps", "gafw")


class GoogleAppError(Exception):
	pass


class NoCredentials(GoogleAppError):
	pass


class MissingClientCredentials(GoogleAppError):
	pass


class CredentialsStorageError(GoogleAppError):
	pass


class AuthenticationError(GoogleAppError):
	def __init__(self, msg, chained_exc=None, *args, **kwargs):
		self.chained_exc = chained_exc
		super(AuthenticationError, self).__init__(msg, *args, **kwargs)


class AuthenticationErrorRetry(AuthenticationError):
	pass


class SSLError(AuthenticationError):
	pass


class GappsAuth(object):
	def __init__(self, listener):
		self.listener = listener
		self.credentials = None
		self.service_objects = dict()
		self.ucr = ucr
		if self.ucr.is_true("google-apps/debug/api-calls"):
			httplib2.debuglevel = 4

	@classmethod
	def is_initialized(cls):
		"""
		Checks if the credentials to use the google directory are available.
		:return: bool
		"""
		try:
			sjac = cls._get_credentials()
			return not sjac.invalid
		except NoCredentials:
			return False

	@staticmethod
	def uninitialize():
		with open(CREDENTIALS_FILE, "w") as fp:
			json.dump({}, fp)

	def get_credentials(self):
		"""
		Fetch credentials from disk for usage by oauth2client library.
		:return: oauth2client.file.Storage object or NoIDsStored
		"""
		if not self.credentials:
			self.credentials = self._get_credentials()
		return self.credentials

	@classmethod
	def _get_credentials(cls):
		"""
		Static version without caching the storage object.
		:return: oauth2client.file.Storage object or NoIDsStored
		"""
		try:
			credentials = cls._load_credentials()

			if credentials and not credentials.invalid and credentials._kwargs["domain"]:
				return credentials
			else:
				raise NoCredentials("No valid credentials found in '{}'.".format(CREDENTIALS_FILE))
		except (AttributeError, IOError, KeyError):
			raise NoCredentials("No valid credentials found in '{}'.".format(CREDENTIALS_FILE))

	@classmethod
	def update_saml_configuration(cls, gsuite_domain):
		try:
			udm_modules.update()
			access, position = udm_uldap.getAdminConnection()
			service_provider = udm_objects.get(udm_modules.get("saml/serviceprovider"), None, access, None,
				GOOGLE_APPS_SERVICEPROVIDER_DN)
			if service_provider:
				with open("/usr/share/univention-google-apps/google-apps-for-work.php") as templatefile:
					service_provider_config = templatefile.read()
				service_provider["isActivated"] = True
				service_provider["AssertionConsumerService"] = "https://www.google.com/a/%s/acs" % gsuite_domain
				service_provider["rawsimplesamlSPconfig"] = service_provider_config % {"domain": gsuite_domain}
				service_provider.modify()
			else:
				logger.exception("GappsAuth.update_saml_configuration() SAML service provider object not found %s.",
					GOOGLE_APPS_SERVICEPROVIDER_DN)
		except udm_exceptions.base as exc:
			# from umc.modules.udm.udm_ldap.py
			def __get_udm_exception_msg(e):
				msg = getattr(e, 'message', '')
				if getattr(e, 'args', False):
					if e.args[0] != msg or len(e.args) != 1:
						for arg in e.args:
							msg += ' ' + arg
				return msg
			msg = __get_udm_exception_msg(exc)
			logger.exception("GappsAuth.update_saml_configuration() udm exception %s.", msg)
			raise CredentialsStorageError(_("Error when modifying SAML service provider."))
		except IOError as exc:
			logger.exception("GappsAuth.iupdate_saml_configuration() IOError while reading sp config template: %s", exc)
			raise CredentialsStorageError(_("IOError when modifying SAML service provider."))

	@classmethod
	def store_credentials(cls, client_credentials, impersonate_user, **kwargs):
		"""
		Store credentials from a JSON file supplied by Googles Developers Console.
		:param client_credentials: dict: service account credentials, must have
			keys client_email, client_id and private_key
		:param impersonate_user: str: email address of admin user
		:param kwargs: additional parameters to pass to SignedJwtAssertionCredentials()
			must contain "domain=<domain validated by google>"
		:return: None
		"""
		try:
			if "." not in kwargs["domain"]:
				raise KeyError("")
		except (KeyError, TypeError):
			logger.exception("GappsAuth.store_credentials() Missing name of validated domain.")
			raise MissingClientCredentials(_("Please supply the name of a validated domain."))

		credentials = ServiceAccountCredentials.from_json_keyfile_dict(client_credentials, SCOPE)
		credentials = credentials.create_scoped(SCOPE).create_delegated(impersonate_user).create_with_claims(kwargs)

		storage = Storage(CREDENTIALS_FILE)
		try:
			storage.put(credentials)
		except IOError:
			logger.exception("GappsAuth.store_credentials() IOError when writing %r.", CREDENTIALS_FILE)
			raise CredentialsStorageError(_("Error when writing credentials to disk."))

		cls.update_saml_configuration(kwargs['domain'])

		sp_query_string = "?spentityid=google.com&RelayState={}".format(
			quote("https://www.google.com/a/{}/Dashboard".format(kwargs["domain"])))
		sp_link = "https://{}/simplesamlphp/saml2/idp/SSOService.php{}".format(
			ucr["ucs/server/sso/fqdn"], sp_query_string)
		ucr_update(ucr, {
			"ucs/web/overview/entries/service/SP/description": "Single Sign-On login for Google Apps for Work",
			"ucs/web/overview/entries/service/SP/label": "Google Apps for Work login",
			"ucs/web/overview/entries/service/SP/link": sp_link,
			"ucs/web/overview/entries/service/SP/description/de": "Single-Sign-On Link für Google Apps for Work",
			"ucs/web/overview/entries/service/SP/label/de": "Google Apps for Work login",
			"ucs/web/overview/entries/service/SP/priority": "50",
			"ucs/web/overview/entries/service/SP/icon": "/googleapps.png"
			})
		handler_commit(['/etc/simplesamlphp/metadata.include/google-apps-for-work.php'])

	@classmethod
	def get_domain(cls):
		"""
		Get validated domain that was configured in wizard.
		:return: str: domain name or raises NoCredentials
		"""
		credentials = cls._get_credentials()
		return credentials._kwargs["domain"]

	@staticmethod
	def _load_credentials():
		"""
		Fetch credentials from disk for usage by oauth2client library.
		:return: oauth2client.file.Storage object
		"""
		storage = Storage(CREDENTIALS_FILE)
		try:
			return storage.get()
		except IOError:
			logger.exception("GappsAuth.get_credentials() IOError when reading %r.", CREDENTIALS_FILE)
			raise

	def get_service_object(self, service_name="admin", version="directory_v1"):
		"""
		Create the proxy object to use the google api.
		:param service_name: str: api to use
		:param version: str: version of api to use
		:return: service object
		"""
		key = "{}.{}".format(service_name, version)
		service = self.service_objects.get(key)
		if not service:
			credentials = self.get_credentials()
			try:
				service = build(service_name, version, credentials=credentials)
			except AccessTokenRefreshError as exc:
				if str(exc) != "unauthorized_client":
					raise
				# Happens when the user has just authorized a service account
				# for API access, but Googles servers have not realized yet it.
				# The oauthlib will set the credentials to "invalid", which
				# will make further connection attempts fail.
				with open(CREDENTIALS_FILE, "rb") as fp:
					creds = json.load(fp)
				creds["invalid"] = False
				with open(CREDENTIALS_FILE, "wb") as fp:
					json.dump(creds, fp)
				raise AuthenticationErrorRetry, AuthenticationErrorRetry(_("Token could not be refreshed, "
					"you may try to connect again later."), chained_exc=exc), sys.exc_info()[2]
			except SSLHandshakeError as exc:
				raise SSLError, SSLError(_('SSL error. Please check your firewall/proxy settings and the servers system time. Error: {}').format(exc), chained_exc=exc), sys.exc_info()[2]
			except Oauth2ClientError as exc:
				raise AuthenticationError, AuthenticationError(str(exc), chained_exc=exc), sys.exc_info()[2]
			self.service_objects[key] = service
		return service
