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


CONFDIR = "/etc/univention-google-apps"
CREDENTAILS_FILE = CONFDIR + "/credentials.json"
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
		try:
			sjac = cls._get_credentials()
			return not sjac.invalid
		except NoIDsStored:
			return False

	@staticmethod
	def uninitialize():
		with open(CREDENTAILS_FILE, "w") as fp:
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

			if credentials and not credentials.invalid:
				return credentials
			else:
				raise NoCredentials("No valid credentials found in '{}'.".format(CREDENTAILS_FILE))
		except (AttributeError, IOError, KeyError):
			raise NoCredentials("No valid credentials found in '{}'.".format(CREDENTAILS_FILE))

	@classmethod
	def store_credentials(cls, json_key_str, impersonate_user, **kwargs):
		"""
		Load data to store from a JSOn file supplied by Googles Developers Console.
		:param json_key_str: str: JSON object
		:param impersonate_user: str: email address of admin user
		:param kwargs: additional parameters to pass to SignedJwtAssertionCredentials()
		:return: None
		"""
		data = json.loads(json_key_str)
		credentials = SignedJwtAssertionCredentials(
			service_account_name=data["client_email"],
			private_key=data["private_key"],
			scope=SCOPE,
			sub=impersonate_user,
			client_id=data["client_id"],
			**kwargs)

		storage = Storage(CREDENTAILS_FILE)
		try:
			storage.put(credentials)
		except IOError:
			logger.exception("GappsAuth.store_credentials() IOError when writing %r.", CREDENTAILS_FILE)
			raise

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
