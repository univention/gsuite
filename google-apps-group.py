# -*- coding: utf-8 -*-
#
# Univention Google Apps for Work - listener module to manage groups in
# Google Directory
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

import os
try:
	import cPickle as pickle
except ImportError:
	# py3
	import pickle
import copy
from stat import S_IRUSR, S_IWUSR

import listener
from univention.googleapps.auth import GappsAuth
from univention.googleapps.listener import GoogleAppsListener
from univention.googleapps.logging2udebug import get_logger

listener.configRegistry.load()
logger = get_logger("google-apps", "gafw")

name = 'google-apps-group'
description = 'sync groups to Google Directory'
if GappsAuth.is_initialized() and listener.configRegistry.is_true("google-apps/groups/sync", False):
	filter = '(objectClass=posixGroup)'
	logger.info("group listener active")
else:
	filter = '(foo=bar)'
	logger.info("group listener deactivated")
attributes = ["cn", "description", "uniqueMember", "mailPrimaryAddress"]
modrdn = "1"

GOOGLEAPPS_GROUP_OLD_PICKLE = os.path.join("/var/lib/univention-google-apps", "google-apps-group_old_dn")

ldap_cred = dict()
attributes_copy = copy.deepcopy(attributes)  # when handler() runs, all kinds of stuff is suddenly in attributes


def load_old(old):
	if os.path.exists(GOOGLEAPPS_GROUP_OLD_PICKLE):
		f = open(GOOGLEAPPS_GROUP_OLD_PICKLE, "r")
		p = pickle.Unpickler(f)
		old = p.load()
		f.close()
		os.unlink(GOOGLEAPPS_GROUP_OLD_PICKLE)
		return old
	else:
		return old


def save_old(old):
	f = open(GOOGLEAPPS_GROUP_OLD_PICKLE, "w+")
	os.chmod(GOOGLEAPPS_GROUP_OLD_PICKLE, S_IRUSR | S_IWUSR)
	p = pickle.Pickler(f)
	p.dump(old)
	p.clear_memo()
	f.close()


def setdata(key, value):
	global ldap_cred
	ldap_cred[key] = value


def initialize():
	if not listener.configRegistry.is_true("google-apps/groups/sync", False):
		raise RuntimeError("Google Apps for Work App: syncing of groups is deactivated.")

	if not GappsAuth.is_initialized():
		raise RuntimeError("Google Apps for Work App not initialized yet, please run wizard.")


def clean():
	"""
	Remove  univentionGoogleAppsObjectID and univentionGoogleAppsData from all
	user objects.
	"""
	logger.info("Removing Google Apps for Work ObjectID and Data from all groups.")
	GoogleAppsListener.clean_udm_objects("groups/group", listener.configRegistry["ldap/base"], ldap_cred)


def handler(dn, new, old, command):
	logger.debug("command: %s", command)  # DEBUG

	if not listener.configRegistry.is_true("google-apps/groups/sync", False):
		return
	if not GappsAuth.is_initialized():
		# TODO: store [dn] = action for replay later
		raise RuntimeError("{}.handler() Google Apps for Work App not initialized yet, please run wizard.".format(name))
	else:
		# TODO: replay postponed actions
		pass

	if command == 'r':
		save_old(old)
		return
	elif command == 'a':
		old = load_old(old)

	ol = GoogleAppsListener(listener, dict(listener=attributes_copy), ldap_cred)

	#
	# NEW group
	#
	if new and not old:
		logger.debug("new and not old -> NEW (%s)", dn)
		if ol.udm_group_has_google_users(dn):
			new_google_group = ol.create_google_group_from_ldap(dn)
			logger.info("Created group %r with ID %r.", new_google_group["name"], new_google_group["id"])
		logger.debug("done (%s)", dn)
		return

	#
	# DELETE group
	#
	if old and not new:
		logger.debug("old and not new -> DELETE (%s)", dn)
		if "univentionGoogleAppsObjectID" in old:
			ol.delete_google_group(old["univentionGoogleAppsObjectID"][0])
			logger.info("Deleted group %r with ID %r.", old["cn"][0], old["univentionGoogleAppsObjectID"][0])
		logger.debug("done (%s)", dn)
		return

	#
	# MODIFY group
	#
	if old and new:
		logger.debug("old and new -> MODIFY (%s)", dn)
		if "univentionGoogleAppsObjectID" in old or ol.udm_group_has_google_users(dn):
			ol.modify_google_group(old, new)
			# save objectId in UDM object
			group_id = ol.get_udm_group(new["entryDN"][0]).get("UniventionGoogleAppsObjectID")
			if not group_id:
				# not (properly) synced, will be next time
				# missing / unsynced groups are not a problem for users
				logger.warn("Modified a group, but cannot find UniventionGoogleAppsObjectID (was probably deleted).")
				group_id = None
			ol.udm_group_set_group_id(new["entryDN"][0], group_id)
			logger.info("Modified group %r (%r).", old["cn"][0], group_id)
		logger.debug("done (%s)", dn)
		return
