#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
#
# Univention Google Apps for Work - handle google API calls
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

__package__ = ''  # workaround for PEP 366
import operator
import json
import random
import string
import re

from apiclient.errors import HttpError
from univention.googleapps.auth import GappsAuth, GoogleAppError
from univention.googleapps.logging2udebug import get_logger


class BadArgumentError(GoogleAppError):
	pass


class ApiError(GoogleAppError):
	def __init__(self, *args, **kwargs):
		try:
			self.http_error = kwargs.pop("http_error")
		except KeyError:
			self.http_error = None
		super(ApiError, self).__init__(*args, **kwargs)


class ResourceNotFoundError(ApiError):
	pass


class LimitReachedError(ApiError):
	pass


class GappsHandler(object):
	"""
	Abstraction of Googles Admin Directory API.
	https://developers.google.com/resources/api-libraries/documentation/admin/directory_v1/python/latest/index.html
	"""
	def __init__(self, listener):
		self.listener = listener
		self.logger = get_logger("google-apps", "gafw")
		self.auth = GappsAuth(listener)
		self.service = self.auth.get_service_object(service_name="admin", version="directory_v1")

	def get_user(self, user_id, **kwargs):
		"""
		Get a user from google directory.
		:param user_id: str: user's primary email address, alias email address, or ID
		:param kwargs: dict: all parameters that are allowed for the get() methods of the
		user object (https://developers.google.com/admin-sdk/directory/v1/reference/users/get)
		:return: dict: user
		"""
		key = dict(userKey=user_id)
		return self._get_object("users", key)

	def create_user(self, properties):
		"""
		Create a user in the google directory.
		If user exists, it will be modified instead.
		properties MUST contain the mandatory attributes
		* "name": {"givenName", "familyName"}
		* "password",
		* "primaryEmail"
		:param properties: dict: properties as documented in
		https://developers.google.com/admin-sdk/directory/v1/reference/users/insert
		:return: dict: created user
		"""
		# check mandatory properties
		try:
			_ = properties["name"]
			for attribute in ["givenName", "familyName"]:
				try:
					_ = properties["name"][attribute]
				except KeyError:
					self.logger.error("Mandatory property %r not supplied when creating user, using random string.",
						attribute)
					properties["name"][attribute] = self.get_random_ascii_string()
		except KeyError:
			self.logger.error("Mandatory property 'name' not supplied when creating user, creating random name.")
			properties["name"] = dict(
				givenName=self.get_random_ascii_string(),
				familyName=self.get_random_ascii_string()
			)
		if not properties.get("password"):
			properties["password"] = self.get_random_ascii_string(32)
		properties["primaryEmail"] = self.fix_email(properties["primaryEmail"])

		key = dict(userKey=properties["primaryEmail"])
		return self._create_object("users", properties, modify_key=key)

	def list_users(self, customer="my_customer", domain=None, **kwargs):
		"""
		Get list of users from google directory.
		Paging is done by this method.
		:param customer: str: ID of the google account, "my_customer" is an alias to
		represent the account's customerId, either customer or domain must be set
		:param domain: str: get fields from only one domain, either customer or
		domain must be set
		:param kwargs: dict: all parameters (except pageToken) that are documented in
		https://developers.google.com/admin-sdk/directory/v1/reference/users/list
		:return: list of users (dicts)
		"""
		return self._list_objects("users", customer, domain, **kwargs)

	def list_groups_of_user(self, user_id):
		"""
		Get the groups a user is in from google directory.
		:param user_id: str: user's primary email address, alias email address, or ID
		:return: list of groups (dicts)
		"""
		return self.list_groups(customer="", domain="", userKey=user_id)

	def modify_user(self, user_id, properties, method="patch"):
		"""
		Modify a user in the google directory.
		:param user_id: str: primary email address, alias email address, or user ID
		:param properties: dict: properties to change
		:param method: str: see _modify_object()
		:return: dict: modified user
		"""
		key = dict(userKey=user_id)
		return self._modify_object("users", properties, key, method)

	def delete_user(self, user_id):
		"""
		Deletes a user
		:param user_id: str: primary email address, alias email address, or user ID
		:return: empty str or ResourceNotFoundError
		"""
		key = dict(userKey=user_id)
		return self._delete_object("users", key)

	def get_group(self, group_id):
		"""
		Get a group from google directory.
		:param group_id: str: group's email address, group alias, or ID
		:return: dict: group resource
		"""
		key = dict(groupKey=group_id)
		return self._get_object("groups", key)

	def create_group(self, email, description=None, name=None):
		"""
		Create a user in the google directory.
		If group exists, it will be modified instead.
		:param email: str: group's email address, must be unique
		:param description: str: group's description
		:param name: str: group's name
		:return: dict: created group
		"""
		email = self.fix_email(email)
		properties = dict(email=email, description=description, name=name)
		key = dict(groupKey=email)
		return self._create_object("groups", properties, modify_key=key)

	def list_groups(self, customer="my_customer", domain=None, **kwargs):
		"""
		Get list of groups from google directory.
		Paging is done by this method.
		:param customer: str: ID of the google account, "my_customer" is an alias to
		represent the account's customerId, either customer or domain must be set
		:param domain: str: get fields from only one domain, either customer or
		domain must be set
		:param kwargs: dict: all parameters (except pageToken) that are documented in
		https://developers.google.com/admin-sdk/directory/v1/reference/groups/list
		Don't use the 'userKey' argument, use list_groups_of_user() instead.
		:return: list of groups (dicts)
		"""
		return self._list_objects("groups", customer, domain, **kwargs)

	def modify_group(self, group_id, email=None, description=None, name=None, method="patch"):
		"""
		Modify a user in the google directory.
		:param group_id: str: group's email address, group alias, or group ID
		:param email: str: group's email address, must be unique
		:param description: str: group's description
		:param name: str: group's name
		:param method: str: see _modify_object()
		:return: dict: modified group
		"""
		if method == "patch":
			properties = dict()
			if email:
				properties["email"] = self.fix_email(email)
			if description:
				properties["description"] = description
			if name:
				properties["name"] = name
		else:
			properties = dict(email=self.fix_email(email), description=description, name=name)
		key = dict(groupKey=group_id)
		return self._modify_object("groups", properties, key, method)

	def delete_group(self, group_id):
		"""
		Deletes a user
		:param group_id: str: group's email address, group alias, or group ID
		:return: empty str or ResourceNotFoundError
		"""
		key = dict(groupKey=group_id)
		return self._delete_object("groups", key)

	def list_members_of_group(self, group_id):
		"""
		Get list of member of a group from google directory.
		Paging is done by this method.
		:param group_id: str: group's email address, group alias, or group ID
		:return: list of dicts of member ressources
		"""
		return self._list_objects("members", groupKey=group_id)

	def get_member_of_group(self, group_id, member_id):
		"""
		Retrieve a single group member.
		:param group_id: string: group's email address, group alias, or group ID
		:param member_id: user's primary email address, alias email address, or ID
		:return: dict: member ressource
		"""
		key = dict(groupKey=group_id)
		return self._get_object("members", key, memberKey=member_id)

	def add_member_to_group(self, group_id, obj_id, role="MEMBER"):
		"""
		Add a user or group to a group.
		:param group_id: str: group's email address, group alias, or group ID
		:param obj_id: str: user's or groups primary email address, alias email address, or ID
		:param role: str: "MANAGER", "MEMBER" or "OWNER"
		:return: dict: member resource
		"""
		modify_args = dict(memberKey=obj_id)
		properties = dict(id=obj_id, role=role)
		return self._create_object("members", properties, modify_args, groupKey=group_id)

	def delete_member_from_group(self, group_id, obj_id):
		"""
		Remove a user or group from a group.
		:param group_id: str: group's email address, group alias, or group ID
		:param obj_id: str: user's or groups primary email address, alias email address, or ID
		:return: None
		"""
		key = dict(groupKey=group_id)
		return self._delete_object("members", key=key, memberKey=obj_id)

	def get_customer_id(self):
		"""
		Fetches the customerId - expecting a single-tenant
		:return: str
		"""
		return self.list_users(maxResults=1)[0]["customerId"]

	def list_domains(self):
		"""
		Retrieves the list of registered domains.
		:return: list of dicts (domain resource:
		https://developers.google.com/admin-sdk/directory/v1/reference/domains)
		"""
		customer_id = self.get_customer_id()
		return self._list_objects("domains", customer=customer_id)

	def get_primary_domain(self):
		"""
		Fetches the primary domain from the list of registered domains.
		:return: dict (domain resource)
		"""
		domains = self.list_domains()
		if not domains:
			raise RuntimeError("No domains")
		for domain in domains:
			if domain["isPrimary"]:
				return domain
		return domains[0]

	def fix_email(self, email):
		"""
		Check and optionally modify an email address to use one of the registered domains.
		:param email: str: email address to check
		:return: str: possibly modified email address
		"""
		# TODO: impl. (mem)cache, ~5min for domains

		m = re.match(r"(.*)@([^@]*)", email)
		if m:
			local_part, domain_part = m.groups()
		else:
			local_part = email
			domain_part = None
		if local_part:
			local_part = local_part.replace(" ", "_")
		else:
			local_part = self.get_random_ascii_string()
		if not domain_part or domain_part not in map(operator.itemgetter("domainName"), self.list_domains()):
			domain_part = self.get_primary_domain()["domainName"]
		new_email = "{}@{}".format(local_part, domain_part)
		if email != new_email:
			self.logger.error("Email address %r invalid, changed to %r.", email, new_email)
		return new_email

	def get_random_ascii_string(self, length=12):
		"""
		Get a string of ascii chars and numbers.
		:param length: int: number of chars of returned string
		:return: str
		"""
		return "".join([random.choice(string.ascii_letters + string.digits) for _ in range(length)])

	def _get_object(self, object_type, key, **kwargs):
		"""
		Retrieve object from google directory.
		(Tested only for users, groups and members.)
		:param object_type: str: "users", "groups" or "members"
		:param key: dict: with a single key->value used to identify object
		:param kwargs: dict: all parameters that are allowed for the get()
		methods of the respective objects
		:return: dict (object_type resources)
		"""
		self.logger.debug("object_type=%r key=%r kwargs=%r", object_type, key, kwargs)
		kwargs.update(key)
		kwargs["prettyPrint"] = False

		try:
			return getattr(self.service, object_type)().get(**kwargs).execute()
		except HttpError as exc:
			if exc.resp.status == 404:
				raise ResourceNotFoundError(http_error=exc)
			else:
				raise

	def _list_objects(self, object_type, customer=None, domain=None, **kwargs):
		"""
		Retrieve objects from google directory.
		Paging is done by this method.
		(Tested only for users, groups and members.)
		:param object_type: str: "users", "groups" or "members"
		:param customer: str: ID of the google account, "my_customer" is an alias to
		represent the account's customerId, either customer or domain must be set
		for object_type="users"
		:param domain: str: get fields from only one domain, either customer or
		domain must be set for object_type="users"
		:param kwargs: dict: all parameters (except "pageToken") that are allowed for the
		list() methods of the respective objects
		:return: list dicts (object_type resources)
		"""
		self.logger.debug("object_type=%r customer=%r domain=%r kwargs=%r", object_type, customer, domain, kwargs)
		if object_type == "users" and not (customer or domain):
			raise BadArgumentError("GappsHandler._list_objects(object_type='{}', customer='{}', domain='{}', kwargs={}):"
				"either customer or domain must be set.".format(object_type, customer, domain, kwargs))
		if kwargs.get("pageToken"):
			raise BadArgumentError("GappsHandler._list_objects() pageToken is not allowed.")

		if customer:
			kwargs["customer"] = customer
		if domain:
			kwargs["domain"] = domain
		kwargs["prettyPrint"] = False

		objs = list()
		while True:
			try:
				results = getattr(self.service, object_type)().list(**kwargs).execute()
			except HttpError as exc:
				results = dict()
				if exc.resp.status == 404:
					raise ResourceNotFoundError(http_error=exc)
				else:
					self.logger.exception("Error listing, object_type=%r customer=%r domain=%r kwargs=%r.",
						object_type, customer, domain, kwargs)
					raise
			objs.extend(results.get(object_type, []))
			next_page_token = results.get("nextPageToken")
			if next_page_token:
				kwargs["pageToken"] = next_page_token
			else:
				break
		return objs

	def _create_object(self, object_type, properties, modify_key, **kwargs):
		"""
		Create an object in the google directory, modify if it exists.
		(Tested only for users, groups and members.)
		:param object_type:  str: "users", "groups" or "members"
		:param properties: dict: properties as documented for the respective objects
		:param modify_key: dict: with a single key->value used to identify object
		in directory, passed to possible patch call only
		:param kwargs: dict: additional arguments to pass to insert and patch call
		:return: dict: resource of created object
		"""
		self.logger.debug("object_type=%r properties=%r modify_key=%r kwargs=%r", object_type, properties, modify_key,
			kwargs)
		kwargs["prettyPrint"] = False
		try:
			return getattr(self.service, object_type)().insert(body=properties, **kwargs).execute()
		except HttpError as exc:
			if exc.resp.status == 409:
				# "Entity already exists."
				self.logger.info("Object (%r) exists, modifying instead.", object_type[:-1])
				return self._modify_object(object_type, properties, modify_key, **kwargs)
			elif exc.resp.status == 412:
				# PRECONDITION_FAILED / conditionNotMet
				# probably a license limit was reached
				if "application/json" in exc.resp["content-type"]:
					content = json.loads(exc.content)
					error = content.get("error")
					try:
						message = error["message"]
					except KeyError:
						message = str(error)
					self.logger.exception("Could not create %r: %r", object_type[:-1], message)
					if "limit" in message:
						raise LimitReachedError(http_error=exc)
					else:
						pass
			else:
				pass
			self.logger.exception("HttpError %d trying to create %r with properties %r and key %r.", exc.resp.status,
				object_type, properties, modify_key)
			raise

	def _modify_object(self, object_type, properties, key, method="patch", **kwargs):
		"""
		Modify an object in the google directory.
		(Tested only for users and groups.)
		:param object_type:  str: "users" or "groups"
		:param properties: dict: properties as documented for the respective objects
		:param key: dict: with a single key->value used to identify object in the directory
		:param method: str: how to modify an object: 'patch' changes only the properties given,
		'update' sets all properties of an object
		:param kwargs: dict: additional arguments to pass to patch/update call
		:return: dict: resource of modified object
		"""
		self.logger.debug("object_type=%r properties=%r key=%r method=%r kwargs=%r", object_type, properties, key,
			method, kwargs)
		obj = getattr(self.service, object_type)()
		meth = getattr(obj, method)
		kwargs["prettyPrint"] = False
		kwargs.update(key)
		self.logger.debug("kwargs=%r", kwargs)
		try:
			return meth(body=properties, **kwargs).execute()
		except HttpError as exc:
			if exc.resp.status == 404:
				raise ResourceNotFoundError(http_error=exc)
			self.logger.exception("HttpError %d trying to modify %r with properties %r, key %r and method %r.",
				exc.resp.status, object_type, properties, key, method)
			raise

	def _delete_object(self, object_type, key, **kwargs):
		"""
		Delete an object from the google directory
		(Tested only for users, groups and members.)
		:param object_type: str: "users", "groups" or "members"
		:param key: dict: with a single key->value used to identify object in the directory
		:param kwargs: dict: optional arguments to pass to delete()
		:return: empty str or ResourceNotFoundError
		"""
		self.logger.debug("object_type=%r key=%r kwargs=%r", object_type, key, kwargs)
		kwargs["prettyPrint"] = False
		kwargs.update(key)
		try:
			return getattr(self.service, object_type)().delete(**kwargs).execute()
		except HttpError as exc:
			if exc.resp.status == 404:
				raise ResourceNotFoundError(http_error=exc)
			self.logger.exception("HttpError %d trying to delete %r with  key %r.", exc.resp.status, object_type, key)
			raise
