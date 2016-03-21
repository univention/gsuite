#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
#
# Univention Management Console
#  module: Google Apps for Work setup wizard
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

import json
import subprocess

from univention.lib.i18n import Translation
from univention.management.console.base import Base, UMC_Error
from univention.management.console.config import ucr

from univention.management.console.modules.decorators import sanitize, simple_response, file_upload
from univention.management.console.modules.sanitizers import StringSanitizer, DictSanitizer, BooleanSanitizer

from univention.googleapps.auth import GappsAuth, SCOPE
from univention.googleapps.listener import GoogleAppsListener

_ = Translation('univention-management-console-module-googleapps').translate


class Instance(Base):

	@simple_response
	def query(self):
		return {
			'initialized': GappsAuth.is_initialized()
		}

	@file_upload
	@sanitize(DictSanitizer(dict(
		tmpfile=StringSanitizer(required=True)
	), required=True))
	def upload(self, request):
		GappsAuth.uninitialize()
		with open(request.options[0]['tmpfile']) as fd:
			data = fd.read()
			values = json.loads(data)
			GappsAuth.store_credentials(data, request.body['email'])
		self.finished(request.id, {
#			'service_account_name': values['service_account_name'],  # FIXME: doesn't exists
			'client_id': values['client_id'],
			'scope': ','.join(SCOPE)
		})

	@simple_response
	def test_configuration(self):
		if not GappsAuth.is_initialized():
			raise UMC_Error(_('The configuration to Google Apps for Work is not yet complete.'))
		ol = GoogleAppsListener(None, {}, {})
		try:
			return ol.gh.list_users(projection="basic")
		except oauth2client.client.AccessTokenRefreshError:
			# might be 'invalid_client' or 'access_denied'
			raise  # UMC_Error(str(exc))
