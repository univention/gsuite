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
import functools

from univention.lib.i18n import Translation
from univention.management.console.base import Base, UMC_Error, UMC_OptionSanitizeError
from univention.management.console.config import ucr

from univention.management.console.modules.decorators import sanitize, simple_response, file_upload
from univention.management.console.modules.sanitizers import StringSanitizer, DictSanitizer, EmailSanitizer, ValidationError, MultiValidationError

from univention.googleapps.auth import GappsAuth, SCOPE, GoogleAppError, AuthenticationError, AuthenticationErrorRetry
from univention.googleapps.listener import GoogleAppsListener

_ = Translation('univention-management-console-module-googleapps').translate


def sanitize_body(sanizer):  # TODO: move into UMC core
	def _decorator(function):
		@functools.wraps(function)
		def _decorated(self, request, *args, **kwargs):
			try:
				sanizer.sanitize('request.body', {'request.body': request.body})
			except MultiValidationError as exc:
				raise UMC_OptionSanitizeError(str(exc), exc.result())
			except ValidationError as exc:
				raise UMC_OptionSanitizeError(str(exc), {exc.name: str(exc)})
			return function(self, request, *args, **kwargs)
		return _decorated
	return _decorator


def progress(component=None, message=None, percentage=None, errors=None, critical=None, finished=False, **kwargs):
	return dict(
		component=component,
		message=message,
		percentage=percentage,
		errors=errors or [],
		critical=critical,
		finished=finished,
		**kwargs
	)


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
	@sanitize_body(DictSanitizer(dict(
		email=EmailSanitizer(required=True)
	), required=True))
	def upload(self, request):
		GappsAuth.uninitialize()
		with open(request.options[0]['tmpfile']) as fd:
			try:
				data = json.load(fd)
			except ValueError:
				raise UMC_Error(_('The uploaded file is not a JSON credentials file.'))
			try:
				GappsAuth.store_credentials(data, request.body['email'])
			except GoogleAppError as exc:
				raise UMC_Error(str(exc))
		self.finished(request.id, {
			'client_id': data['client_id'],
			'scope': ','.join(SCOPE),
#			'serviceaccounts_link': 'https://console.developers.google.com/permissions/serviceaccounts?project=%s' % (urllib.quote(data['project_id']),)
		})

	@simple_response
	def state(self):
		if not GappsAuth.is_initialized():
			raise UMC_Error(_('The configuration to Google Apps for Work is not yet complete.'))
		try:
			ol = GoogleAppsListener(None, {}, {})
			ol.gh.list_users(projection="basic")
			return progress(finished=True)
		except AuthenticationErrorRetry:
			return progress(message=_('Waiting for Google directory to authorize the connection.'))
		except AuthenticationError as exc:
			raise UMC_Error(str(exc))
