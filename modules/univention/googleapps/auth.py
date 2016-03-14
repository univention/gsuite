#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
#
# Univention Google Apps for Work App - handle auth
#
# Copyright 2016 Univention GmbH
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

from apiclient import discovery
from oauth2client.file import Storage
from oauth2client.client import SignedJwtAssertionCredentials

from univention.googleapps.logging2udebug import get_logger


NAME = "google-apps"
CONFDIR = "/etc/univention-google-apps"
CREDENTAILS_FILE = CONFDIR + "/credentials.json"
SSL_KEY_FILE = CONFDIR + "/key.p12"
SCOPE = [
	"https://www.googleapis.com/auth/admin.directory.user",
	"https://www.googleapis.com/auth/admin.directory.group",
	"https://www.googleapis.com/auth/admin.directory.group.member",
	"https://www.googleapis.com/auth/admin.directory.domain.readonly"]


logger = get_logger("google-apps", "gafw")


class GoogleAppError(Exception):
	pass


class NoCredentials(GoogleAppError):
	pass


class NoIDsStored(GoogleAppError):
	pass


class GappsAuth(object):
	def __init__(self, listener):
		self.listener = listener
		self.credentials = None
		self.service_objects = dict()
		if self.listener:
			self.ucr = self.listener.configRegistry
		else:
			# allow use of this class outside listener
			from univention.config_registry import ConfigRegistry
			self.ucr = ConfigRegistry()
			self.ucr.load()
		if self.ucr.is_true("google-apps/debug/api-calls"):
			httplib2.debuglevel = 4

	@classmethod
	def is_initialized(cls):
		"""
		Checks if the credentials to use the google directory are available.
		:return: bool
		"""
		# TODO: check content of Storage object
		try:
			cls._load_credentials()
			return True
		except (NoIDsStored, IOError):
			logger.exception("GappsAuth.is_initialized()")
			return False

	def get_credentials(self):
		"""
		Fetch credentials from disk for usage by oauth2client library.
		:return: oauth2client.file.Storage object
		"""
		if self.credentials:
			return self.credentials
		else:
			self.credentials = GappsAuth._load_credentials()

		if self.credentials:
			return self.credentials
		else:
			raise NoCredentials("No credentials found in '{}'.".format(CREDENTAILS_FILE))

	@classmethod
	def store_credentials(cls, client_email, impersonate_user, **kwargs):
		"""
		Store credentials for later use.
		:param client_email: str: service account (very long email address)
		:param scope: str or list: scope(s) to request access to
		:param impersonate_user: str: email address of admin user
		:param kwargs: additional parameters to pass to SignedJwtAssertionCredentials()
		May contain "private_key" in PEM or P12 format and "client_id" of service account.
		:return:
		"""
		try:
			private_key = kwargs.pop("private_key")
		except KeyError:
			private_key = cls._load_ssl_key()

		credentials = SignedJwtAssertionCredentials(
			service_account_name=client_email,
			private_key=private_key,
			scope=SCOPE,
			sub=impersonate_user,
			**kwargs)

		storage = Storage(CREDENTAILS_FILE)
		try:
			storage.put(credentials)
		except IOError:
			logger.exception("GappsAuth.store_credentials() IOError when writing %r.", CREDENTAILS_FILE)
			raise

	@classmethod
	def store_credentials_from_json(cls, json_key_str, impersonate_user, **kwargs):
		"""
		Load data to store from a JSOn file supplied by Googles Developers Console.
		:param json_key_str: str: JSON object
		:param impersonate_user: str: email address of admin user
		:param kwargs: additional parameters to pass to SignedJwtAssertionCredentials()
		:return: None
		"""
		data = json.loads(json_key_str)
		cls.store_credentials(
			data["client_email"],
			impersonate_user,
			client_id=data["client_id"],
			private_key=data["private_key"],
			**kwargs
		)

	@staticmethod
	def _load_credentials():
		"""
		Fetch credentials from disk for usage by oauth2client library.
		:return: oauth2client.file.Storage object
		"""
		storage = Storage(CREDENTAILS_FILE)
		try:
			return storage.get()
		except IOError:
			logger.exception("GappsAuth.get_credentials() IOError when reading %r.", CREDENTAILS_FILE)
			raise

	@staticmethod
	def _load_ssl_key():
		"""
		Load SSL key from disk.
		:return: str: the SSL key
		"""
		try:
			with open(SSL_KEY_FILE, "rb") as f:
				return f.read()
		except IOError:
			logger.exception("GappsAuth.load_ssl_key() Error reading SSL key from %r.", SSL_KEY_FILE)
			raise

	@staticmethod
	def store_ssl_key(key_str):
		"""
		Store SSL key for later use.
		:param key_str: str: SSL key
		:return: None
		"""
		try:
			with open(SSL_KEY_FILE, "wb") as f:
				f.write(key_str)
				f.flush()
		except IOError:
			logger.exception("GappsAuth.store_ssl_key() Error writing SSL key to %r.", SSL_KEY_FILE)
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
			http = credentials.authorize(httplib2.Http())
			service = discovery.build(service_name, version, http=http)
			self.service_objects[key] = service
		return service
