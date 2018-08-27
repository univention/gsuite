# -*- coding: utf-8 -*-
#
# Univention G Suite - UDM hook to set user property
# UniventionGoogleAppsPrimaryEmail that is configured notEditable=1
#
# Copyright 2016-2018 Univention GmbH
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

import json
import base64
import zlib

import univention.debug as ud
from univention.admin.hook import simpleHook
from univention.lib.i18n import Translation
import univention.admin.uexceptions

_ = Translation('univention-googleapps').translate
msg_require_mail = _("G Suite users must have a primary e-mail address specified.")


class GooglePrimaryAdressHook(simpleHook):
	type = "GooglePrimaryAdressHook"

	@staticmethod
	def log(msg):
		ud.debug(ud.LISTENER, ud.ERROR, msg)

	@staticmethod
	def str2bool(val):
		try:
			return bool(int(val))
		except TypeError:
			# None
			return False

	def get_google_primary_address(self, gdata_encoded):
		gdata = json.loads(zlib.decompress(base64.decodestring(gdata_encoded)))
		try:
			return gdata.get("primaryEmail")
		except AttributeError:
			# None
			# (We should actually never get here, as long as UniventionGoogleAppsEnabled=1.)
			return ""

	def hook_ldap_pre_create(self, module):
		if self.str2bool(module.get("UniventionGoogleAppsEnabled")) and not module.get("mailPrimaryAddress"):
			raise univention.admin.uexceptions.valueError(msg_require_mail)

	def hook_ldap_pre_modify(self, module):
		if self.str2bool(module.get("UniventionGoogleAppsEnabled")) and not module.get("mailPrimaryAddress"):
			raise univention.admin.uexceptions.valueError(msg_require_mail)

	def hook_ldap_modlist(self, module, ml=[]):
		if module.hasChanged("UniventionGoogleAppsData"):
			old = module.get("UniventionGoogleAppsPrimaryEmail")
			if self.str2bool(module.get("UniventionGoogleAppsEnabled")):
				new = self.get_google_primary_address(module["UniventionGoogleAppsData"])
			else:
				new = ""
			if old != new:
				ml.append(("univentionGoogleAppsPrimaryEmail", old, new))
		return ml
