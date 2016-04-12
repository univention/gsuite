# -*- coding: utf-8 -*-
#
# Univention Google Apps for Work - listener module impl
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

import uuid
import random
import string
import json
import base64
import zlib
import copy

import univention.admin.uldap
import univention.admin.objects

from univention.googleapps.handler import GappsHandler, ResourceNotFoundError
from univention.googleapps.logging2udebug import get_logger

logger = get_logger("google-apps", "gafw")


class GoogleAppsListener(object):
	def __init__(self, listener, attrs, ldap_cred):
		"""
		:param listener: listener object or None
		:param attrs: {"listener": [attributes, listener, listens, on], ... }
		:param ldap_cred: {ldapserver: FQDN, binddn: cn=admin,$ldap_base, basedn: $ldap_base, bindpw: s3cr3t} or None
		"""
		self.gh = GappsHandler(listener)
		self.listener = listener
		self.attrs = attrs or dict(never=["customerId"])
		self.ldap_cred = ldap_cred
		self.lo = None
		self.po = None
		self.groupmod = None

		if self.listener:
			self.ucr = self.listener.configRegistry
		else:
			# allow use of this class outside listener
			from univention.config_registry import ConfigRegistry
			self.ucr = ConfigRegistry()
		self.ucr.load()

	def create_google_user(self, new):
		"""
		Create a user in the google directory.
		:param new: dict: listener object
		:return: dict: user resource
		"""
		logger.debug("entryUUID=%r", new["entryUUID"][0])

		resource = copy.deepcopy(self.attrs["template"])
		resource = self._walk_resource(resource, new)

		self._fix_user_resource(resource)

		# mandatory properties
		if not resource.get("name"):
			resource["name"] = dict()
		if not resource["name"].get("givenName"):
			resource["name"]["givenName"] = new.get("givenName", [self.gh.get_random_ascii_string()])[0]
		if not resource["name"].get("familyName"):
			resource["name"]["familyName"] = new.get("sn", [self.gh.get_random_ascii_string()])[0]
		if not resource.get("password"):
			resource["password"] = self._get_random_pw()
		if not resource.get("primaryEmail"):
			resource["primaryEmail"] = new.get("mailPrimaryAddress", [self._get_random_email_address()])[0]

		external_ids = self._create_ldap_id_entries(new)
		try:
			resource["externalIds"].extend(external_ids)
		except KeyError:
			resource["externalIds"] = [external_ids]

		for k, v in resource.items():
			# remove empty list and dict, don't delete empty string or int 0
			if v is None or hasattr(v, "__iter__") and len(v) == 0:
				logger.debug("Removing property %r with empty value.", k)
				del resource[k]

		for attrib in set(resource).intersection(set(self.attrs["never"])):
			# this should not happen, as it is done in user-listener.get_listener_attributes()
			logger.warn("Ignoring blacklisted attribute %r.", attrib)
			del resource[attrib]

		return self.gh.create_user(resource)

	def get_google_user(self, new):
		"""
		Fetch google user resource. Will try with univentionGoogleAppsObjectID
		and if not available entryUUID.
		:param new: dict: listener old or new object
		:return: dict: user resource
		"""
		try:
			user_id = new["univentionGoogleAppsObjectID"][0]
			return self.gh.get_user(user_id)
		except KeyError:
			logger.warn("Trying to retrieve user '{}' without an univentionGoogleAppsObjectID.".format(
				new["entryDN"][0]))
		try:
			return self.gh.list_users(query="externalId={}".format(new["entryUUID"][0]))[0]
		except IndexError:
			logger.exception("Could not find user '{}' with entryUUID={} in google directory.".format(
				new["entryDN"][0], new["entryUUID"][0]))
			raise ResourceNotFoundError("Could not find user in google directory.")

	def modify_google_user(self, old, new):
		"""
		Change a user resource in the google directory.
		:param old:  dict: listener old object
		:param new:  dict: listener new object
		:return: dict: user resource
		"""
		# import pprint
		# logger.debug("**************** old *************")
		# logger.debug(pprint.pformat(old))
		# logger.debug("**************** new *************")
		# logger.debug(pprint.pformat(new))
		# logger.debug("**********************************")
		modifications = self._diff_old_new(self.attrs["listener"], old, new)
		if not modifications:
			logger.debug("No modifications - nothing to do.")  # DEBUG
			return
		logger.debug("modifications: %r",
			["{} ({}): {}".format(mod, ",".join(self.attrs["google_attribs"][mod]), new[mod]) for mod in modifications])

		changed_google_properties = set()
		for modification in modifications:
			try:
				google_properties = self.attrs["google_attribs"][modification]
			except KeyError:
				logger.warn("No mapping found for LDAP attribute %r, ignoring modification.", modification)
				continue
			changed_google_properties.update(google_properties)

		resource = dict()
		for google_property in changed_google_properties:
			property_template = copy.deepcopy(self.attrs["template"][google_property])
			property_with_data = self._walk_resource(property_template, new)
			resource[google_property] = property_with_data

		self._fix_user_resource(resource)

		if "externalIds" in resource or old["entryDN"][0] != new["entryDN"][0]:
			try:
				resource["externalIds"].extend(self._create_ldap_id_entries(new))
			except KeyError:
				resource["externalIds"] = self._create_ldap_id_entries(new)

		for attrib in set(resource).intersection(set(self.attrs["never"])):
			# this should not happen, as it is done in user-listener.get_listener_attributes()
			logger.warn("Ignoring blacklisted attribute %r.", attrib)
			del resource[attrib]

		object_id = new["univentionGoogleAppsObjectID"][0]
		return self.gh.modify_user(user_id=object_id, properties=resource)

	def delete_google_user(self, user_id):
		try:
			return self.gh.delete_user(user_id)
		except ResourceNotFoundError:
			logger.warn("GoogleAppsListener.delete_google_user() user with ID %r didn't exist in google directory.", user_id)
			return

	def create_google_group(self, name, description, group_dn, email, add_members=True):
		"""
		Create a group in the google directory. Store object ID in UDM object.
		:param name: str: groups name
		:param description: str: group's description
		:param group_dn: str: DN of group in UCS
		:param email: str: group's email address, must be unique
		:param add_members: if UDM groups members should be added to google directory
		:return: dict: created group resource
		"""
		logger.debug("name=%r description=%r group_dn=%r email=%r add_members=%r", name, description, group_dn, email,
			add_members)
		new_group = self.gh.create_group(email, description, name)

		if new_group:
			self.udm_group_set_group_id(group_dn, new_group["id"])
		else:
			raise RuntimeError("GoogleAppsListener.create_google_group() failed creating group '{}'.".format(name))

		if add_members:
			self.udm_group_add_members_to_google_group(group_dn, new_group["id"])
		return new_group

	def create_google_group_from_new(self, new):
		"""
		Create a group in the google directory. Store object ID in UDM object.
		UDM groups members will automatically be added to the google directory.
		:param new: dict: listener object
		:return: dict: created group resource
		"""
		desc = new.get("description", [""])[0] or None
		name = new["cn"][0]
		email = new["mailPrimaryAddress"][0] or "{}@{}".format(name.replace(" ", "_"),
			self.gh.get_primary_domain()["domainName"])
		return self.create_google_group(name, desc, new["entryDN"][0], email)

	def create_google_group_from_ldap(self, group_dn, add_members=True):
		"""
		Create a group in the google directory. Store object ID in UDM object.
		:param group_dn: str: DN of group in UCS
		:param add_members: if UDM groups members should be added to google directory
		:return: dict: created group resource
		"""
		logger.debug("groupdn=%r add_members=%r", group_dn, add_members)
		udm_group = self.get_udm_group(group_dn)
		desc = udm_group["description"]
		name = udm_group["name"]
		email = udm_group["mailAddress"] or "{}@{}".format(name.replace(" ", "_"),
			self.gh.get_primary_domain()["domainName"])
		return self.create_google_group(name, desc, group_dn, email, add_members)

	def modify_google_group(self, old, new):
		"""
		This will also _create_ the google group, if it didn't exist before.
		The group will only be created if it has a member that is already
		synced to the google directory.
		:param old: dict: listener old object
		:param new: dict: listener new object
		:return: None if nothing to do or dict (group resource) if it was
		changed
		"""
		# TODO: test renaming group (cn)
		modification_attributes = self._diff_old_new(self.attrs["listener"], old, new)
		logger.debug("old DN=%r new DN=%r modification_attributes=%r", old["entryDN"], new["entryDN"],
			modification_attributes)

		if not modification_attributes:
			logger.warn("No modifications found, ignoring.")
			return

		udm_group = self.get_udm_group(new["entryDN"][0])
		group_id = udm_group.get("UniventionGoogleAppsObjectID")
		logger.debug("udm_group[name]=%r group_id=%r", udm_group.get("name"), group_id)

		new_google_group = None

		if "uniqueMember" in modification_attributes:
			# In uniqueMember users and groups are both listed. There is no
			# secure way to distinguish between them, so lets have UDM do that
			# for us.
			modification_attributes.remove("uniqueMember")
			set_old = set(old.get("uniqueMember", []))
			set_new = set(new.get("uniqueMember", []))
			removed_members = set_old - set_new
			added_members = set_new - set_old
			logger.debug("members to add: %r, members to remove: %r", added_members, removed_members)

			# add new members to google directory
			for added_member in added_members:
				if added_member in udm_group["users"]:
					udm_user = self.get_udm_user(added_member)
					if (bool(int(udm_user.get("UniventionGoogleAppsEnabled", "0"))) and
						udm_user.get("UniventionGoogleAppsObjectID")):
						if group_id:
							self.gh.add_member_to_group(group_id, udm_user["UniventionGoogleAppsObjectID"])
						else:
							# group doesn't exist yet, this is the first member -> create it
							# all group members will be added automatically (if they are synced)
							new_google_group = self.create_google_group_from_new(new)
							group_id = new_google_group["id"]
							break
				elif added_member in udm_group["nestedGroup"]:
					# ignore, let's not support nested groups for now
					logger.info("Nested group %r ignored.", added_member)
				else:
					raise RuntimeError("GoogleAppsListener.modify_google_group() '{}' from new[uniqueMember] not in "
						"'nestedGroup' or 'users'.".format(added_member))

			# remove members
			if group_id:
				for removed_member in removed_members:
					# try with UDM user
					udm_obj = self.get_udm_user(removed_member)
					member_id = udm_obj.get("UniventionGoogleAppsObjectID")
					if not member_id:
						# try with UDM group
						udm_obj = self.get_udm_group(removed_member)
						member_id = udm_obj.get("UniventionGoogleAppsObjectID")
					if not member_id:
						# user/group may have been deleted or user/group may not be marked as a google group
						# let's try to remove it from google directory anyway
						# get user or group using DN/email

						# try with a user, have to use entryDN, entryUUID is not accessible to us
						google_user = self.gh.list_users(query="externalId={}".format(removed_member))
						if google_user:
							logger.debug("google_user=%r", google_user)
							member_id = google_user[0]["id"]
						else:
							# try with a group
							# ignore, let's not support nested groups for now
							pass

						if not member_id:
							# not a google user or group or already deleted in google directory
							logger.info("Couldn't find %r in google directory, was not deleted.", removed_member)
							continue

					self.gh.delete_member_from_group(group_id, member_id)
		logger.debug("Done handling 'uniqueMember' for group %r (%r).", udm_group.get("name"), group_id)

		# remove google group if it is empty
		if group_id:
			if self.delete_google_group_if_empty(old["entryDN"][0], group_id):
				group_id = None

		# modify other attributes
		if not group_id:
			# not yet created or already removed -> no group to modify
			return
		supported_attributes = set(self.attrs["listener"])
		supported_attributes.remove("uniqueMember")
		unsupported_attributes = set(modification_attributes) - supported_attributes
		if unsupported_attributes:
			logger.info("Ignoring attributes not supported by google directory: %r.", unsupported_attributes)
		attribs_todo = supported_attributes.intersection(set(modification_attributes))
		logger.debug("attribs_todo=%r", attribs_todo)
		# patch only modified attributes, so we don't overwrite changes the
		# user may have made in the google directory (not that there is a lot
		# that can be changed...)
		args = dict()
		for attrib in attribs_todo:
			if attrib == "description":
				args["description"] = new.get("description", [""])[0]
			elif attrib == "cn":
				args["name"] = new["cn"][0]
			elif attrib == "mailPrimaryAddress":
				args["email"] = new.get("mailPrimaryAddress", [""])[0] or "{}@{}".format(
					new["cn"].replace(" ", "_"), self.gh.get_primary_domain()["domainName"])
			else:
				pass
		if args:
			return self.gh.modify_group(group_id=group_id, **args)
		else:
			return new_google_group or self.gh.get_group(group_id)

	def delete_google_group(self, group_id):
		"""
		Delete a google group.
		:param group_id: str: ID of google group
		:return: empty str or None
		"""
		try:
			return self.gh.delete_group(group_id)
		except ResourceNotFoundError:
			logger.warn("Group %r didn't exist in Google Directory.", group_id)
			return

	def delete_google_group_if_empty(self, group_dn, group_id):
		"""
		Removes a group if it has no more users.
		:param group_dn: str: DN of group in LDAP
		:param group_id: str: ID of group in googles directory
		:return: bool: if the group was removed
		"""
		google_users = self.gh.list_members_of_group(group_id)
		if google_users:
			return False
		else:
			logger.info("Group %r (%r) has no users in google directory, removing...", group_id, group_dn)
			self.delete_google_group(group_id)
			self.udm_group_set_group_id(group_dn, None)
			return True

	def get_udm_user(self, userdn):
		"""
		Fetch UDM user object.
		:param userdn: str: DN of user to get
		:return: dict: opened UDM user object
		"""
		lo, po = self._get_ldap_connection()
		univention.admin.modules.update()
		usersmod = univention.admin.modules.get("users/user")
		univention.admin.modules.init(lo, po, usersmod)
		user = usersmod.object(None, lo, po, userdn)
		user.open()
		return user

	@staticmethod
	def find_udm_objects(module_s, filter_s, base, ldap_cred):
		"""
		search LDAP for UDM objects, static for listener.clean()
		:param module_s: str: "users/user", "groups/group", etc
		:param filter_s: str: LDAP filter string
		:param base: str: LDAP base to search from
		:param ldap_cred: dict: credentials collected by listener.setdata()
		:return: list of (not yet opened) UDM objects
		"""
		lo = univention.admin.uldap.access(
					host=ldap_cred["ldapserver"],
					base=ldap_cred["basedn"],
					binddn=ldap_cred["binddn"],
					bindpw=ldap_cred["bindpw"])
		po = univention.admin.uldap.position(base)
		univention.admin.modules.update()
		module = univention.admin.modules.get(module_s)
		univention.admin.modules.init(lo, po, module)
		config = univention.admin.config.config()
		return module.lookup(config, lo, filter_s=filter_s, base=base)

	def udm_group_add_members_to_google_group(self, group_dn, group_id):
		"""
		Add all members of UDM group that are synced to the google directory
		to the google group.
		:param group_dn: DN of UCS group whos members should be added to google group
		:param group_id: ID of google group that should contain the new members
		:return: None
		"""
		logger.debug("group_dn=%r group_id=%r", group_dn, group_id)
		for user in self.udm_group_list_google_users(group_dn):
			if user["UniventionGoogleAppsObjectID"]:
				self.gh.add_member_to_group(group_id, user["UniventionGoogleAppsObjectID"])
			else:
				logger.error("User %r has no objectID, not adding to group %r.", user["username"], group_id)

	def udm_group_set_group_id(self, group_dn, group_id):
		"""
		Save the object ID of the google group in LDAP.
		:param group_dn: DN of group in UCS
		:param group_id: object ID of google group
		:return: opened UDM group
		"""
		logger.debug("storing %r in %r.", group_id, group_dn)
		udm_group = self.get_udm_group(group_dn)
		udm_group["UniventionGoogleAppsObjectID"] = group_id
		udm_group.modify()
		return udm_group

	@classmethod
	def clean_udm_objects(cls, module_s, base, ldap_cred):
		"""
		Remove  univentionGoogleAppsObjectID and univentionGoogleAppsData
		from all user/group objects, static for listener.clean().
		:param module_s: str: 'users/user' or 'groups/group'
		:param base: str: search base
		:param ldap_cred: dict: credentials collected by listener.setdata()
		or None if run by root
		"""
		logger.info("Cleaning %r objects...", module_s)
		filter_s = "(|(univentionGoogleAppsObjectID=*)(univentionGoogleAppsData=*))"
		udm_objs = cls.find_udm_objects(module_s, filter_s, base, ldap_cred)
		for udm_obj in udm_objs:
			udm_obj.open()
			logger.info("%r...".format(udm_obj["username"] if "username" in udm_obj else udm_obj["name"]))
			udm_obj["univentionGoogleAppsObjectID"] = None
			if "univentionGoogleAppsData" in udm_obj:
				udm_obj["univentionGoogleAppsData"] = base64.encodestring(zlib.compress(json.dumps(None)))
			udm_obj.modify()
		logger.info("Cleaning %r objects done.", module_s)

	def get_udm_group(self, group_dn):
		"""
		Fetch UDM group object.
		:param group_dn: str: DN of group to get
		:return: dict: opened UDM group object
		"""
		lo, po = self._get_ldap_connection()
		if not self.groupmod:
			univention.admin.modules.update()
			self.groupmod = univention.admin.modules.get("groups/group")
			univention.admin.modules.init(lo, po, self.groupmod)
		group = self.groupmod.object(None, lo, po, group_dn)
		group.open()
		return group

	def udm_group_list_google_users(self, group_dn):
		"""
		Get users of this group that are google users (non-recursively).
		:param group_dn: group to check
		:return: list: opened UDM users in this group that are google users
		"""
		logger.debug("groupdn=%r", group_dn)
		udm_group = self.get_udm_group(group_dn)
		result = list()
		for userdn in udm_group.get("users", []):
			udm_user = self.get_udm_user(userdn)
			if bool(int(udm_user.get("UniventionGoogleAppsEnabled", "0"))) and udm_user.get("UniventionGoogleAppsObjectID"):
				result.append(udm_user)
		return result

	def udm_group_has_google_users(self, group_dn):
		"""
		Check if this group has any google users (non-recursively).

		:param group_dn: group to check
		:return: bool: if group has at least one user with univentionGoogleAppsEnabled=1
		"""
		logger.debug("groupdn=%r", group_dn)
		udm_group = self.get_udm_group(group_dn)
		for userdn in udm_group.get("users", []):
			udm_user = self.get_udm_user(userdn)
			if bool(int(udm_user.get("UniventionGoogleAppsEnabled", "0"))):
				return True
		return False

	@staticmethod
	def _anonymize(txt):
		"""
		Get a random string.
		:param txt: str: String to anonymize.
		:return: str: random string
		"""
		return uuid.uuid4().get_hex()

	@staticmethod
	def _get_random_pw():
		# have at least one char from each category in password
		# https://msdn.microsoft.com/en-us/library/azure/jj943764.aspx
		pw = list(random.choice(string.lowercase))
		pw.append(random.choice(string.uppercase))
		pw.append(random.choice(string.digits))
		pw.append(random.choice(u"@#$%^&*-_+=[]{}|\:,.?/`~();"))
		pw.extend(random.choice(string.ascii_letters + string.digits + u"@#$%^&*-_+=[]{}|\:,.?/`~();")
			for _ in range(12))
		random.shuffle(pw)
		return u"".join(pw)

	@staticmethod
	def _diff_old_new(attribs, old, new):
		"""
		:param attribs: list of attributes to take into consideration when looking for modifications
		:param old: listener 'old' dict
		:param new: listener 'new' dict
		:return: list of attributes that changed
		"""
		return [attr for attr in attribs
			if attr in new and attr not in old or
			attr in old and attr not in new or
			(attr in old and attr in new and old[attr] != new[attr])
		]

	def _get_ldap_connection(self):
		"""
		Get lo and po, allows this class to be used outside listener by root.
		:return: tuple (lo, po)
		"""
		if not self.lo or not self.po:
			if self.ldap_cred:
				self.lo = univention.admin.uldap.access(
					host=self.ldap_cred["ldapserver"],
					base=self.ldap_cred["basedn"],
					binddn=self.ldap_cred["binddn"],
					bindpw=self.ldap_cred["bindpw"])
				self.po = univention.admin.uldap.position(self.ucr["ldap/base"])
			else:
				self.lo, self.po = univention.admin.uldap.getAdminConnection()
		return self.lo, self.po

	def _get_random_email_address(self):
		local_part = "".join([random.choice(string.ascii_letters + string.digits) for _ in range(12)])
		return "{}@{}".format(local_part, self.gh.get_primary_domain()["domainName"])

	def _walk_resource(self, node, data_source):
		"""
		Recursively traverse a dict / list / object and modify all leaves.
		Does not handle loops!
		:param node: structure to traverse
		:param data_source: dict: listener new/old object or opened UDM object
		:return: (modified) copy of structure
		"""
		def get_ldap_val_none_anon_or_static(key):
			if key.startswith("%"):
				key = key[1:]
				data = data_source[key]
				if isinstance(data, list) and len(data) == 1:
					data = data[0]
				if key in self.attrs["never"]:
					raise Exception()
				elif key in self.attrs["anonymize"]:
					return self._anonymize(data)
				else:
					return data
				# if isinstance(tmp, list) and len(tmp) == 1:
				# 	return tmp[0]
				# else:
				# 	return tmp
			else:
				return key

		def walk(node):
			if isinstance(node, list):
				res = list()
				for item in node:
					tmp = walk(item)
					if tmp:
						res.append(tmp)
				return res
			elif isinstance(node, dict):
				res = dict()
				for k, v in node.items():
					tmp = walk(v)
					if tmp is not None:
						res[k] = tmp
				return res
			else:
				try:
					return get_ldap_val_none_anon_or_static(node)
				except:
					return None

		return walk(node)

	def _fix_user_resource(self, resource):
		"""
		Looks through the supplied google directory resource and removes
		those parts that miss required entries, untangles parts with lists.
		Works in-place!
		:param resource: dict: the resource to check and possibly fix
		:return: None
		"""
		required_properties = self.attrs["required_properties"]
		logger.debug("required_properties=%r", required_properties)
		logger.debug("resource=%r", resource)
		def _test(struct, key):
			return all([x in struct.keys() for x in required_properties[key]])

		def _multiply_if_has_list(prop):
			# prop is a list of dicts
			li = list()
			while prop:
				p = prop.pop()
				was_multiplied = False
				if not isinstance(p, dict):
					raise RuntimeError("Unexpected type '{}' for item '{}' in property '{}'.".format(type(p), p,
						prop))
				for k, v in p.items():
					if isinstance(v, list):
						values = p.pop(k)
						for value in values:
							p2 = p.copy()
							p2[k] = value
							li.append(p2)
						was_multiplied = True
				if not was_multiplied:
					li.append(p)
			return li

		for k, v in resource.items():
			if k in required_properties:
				if isinstance(v, list):
					resource[k] = [item for item in v if _test(item, k)]
				elif isinstance(v, dict):
					if not _test(v, k):
						del resource[k]
				else:
					raise RuntimeError("Unexpected type '{}' for key '{}' in resource '{}'.".format(type(v), k,
						resource))
			if isinstance(v, list):
				resource[k] = _multiply_if_has_list(resource[k])

		logger.debug("resource=%r", resource)
		return resource

	@staticmethod
	def _create_ldap_id_entries(data_source):
		"""
		Create data to later find user by in google directory.
		* 'entryUUID' will be used to find users in google directory if the
		google ID is lost.
		* 'entryDN' will be used to find users in google directory if the UUID
		is lost (e.g. when modifying a group after a user was deleted).
		:param data_source: dict: listener new/old object
		:return: list: to be used as 'externalIds' property of user resource
		"""
		return [
			dict(
				customType="entryUUID",
				type="custom",
				value=data_source["entryUUID"][0]
			),
			dict(
				customType="entryDN",
				type="custom",
				value=data_source["entryDN"][0]
			)
		]
