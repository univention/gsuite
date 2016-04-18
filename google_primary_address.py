import re

import univention.debug as ud
from univention.admin.hook import simpleHook
from univention.lib.i18n import Translation
import univention.admin.uexceptions

from univention.googleapps.auth import GappsAuth

_ = Translation('univention-googleapps').translate
msg_require_mail = _("Google Apps for Work users must have a primary e-mail address specified.")


class GooglePrimaryAdressHook(simpleHook):
	type = "GooglePrimaryAdressHook"

	@staticmethod
	def log(msg):
		ud.debug(ud.LISTENER, ud.ERROR, msg)

	@staticmethod
	def get_google_primary_address(mailPrimaryAddress):
		m = re.match(r"(.*)@([^@]*)", mailPrimaryAddress)
		if m:
			local_part, domain_part = m.groups()
		else:
			raise univention.admin.uexceptions.valueError(msg_require_mail)
		domain_part = GappsAuth.get_domain()
		return "{}@{}".format(local_part, domain_part)

	def hook_ldap_pre_create(self, module):
		if not module.get("mailPrimaryAddress"):
			raise univention.admin.uexceptions.valueError(msg_require_mail)

	def hook_ldap_pre_modify(self, module):
		if not module.get("mailPrimaryAddress"):
			raise univention.admin.uexceptions.valueError(msg_require_mail)

	def hook_ldap_modlist(self, module, ml=[]):
		if module.get("UniventionGoogleAppsEnabled") and module.hasChanged("mailPrimaryAddress"):
			ml.append((
				"univentionGoogleAppsPrimaryEmail",
				module.get("UniventionGoogleAppsPrimaryEmail"),
				self.get_google_primary_address(module["mailPrimaryAddress"])
			))
		return ml
