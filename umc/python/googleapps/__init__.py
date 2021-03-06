#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
#
# Univention Management Console
#  module: Google Apps for Work setup wizard
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

import json
import functools
import subprocess

from univention.lib.i18n import Translation
from univention.management.console.base import Base
from univention.management.console.error import UMC_Error, UnprocessableEntity
from univention.management.console.config import ucr

from univention.management.console.modules.decorators import sanitize, simple_response, file_upload, allow_get_request
from univention.management.console.modules.sanitizers import StringSanitizer, DictSanitizer, EmailSanitizer, ValidationError, MultiValidationError

from univention.googleapps.auth import GappsAuth, SCOPE, GoogleAppError, AuthenticationError, AuthenticationErrorRetry, SSLError
from univention.googleapps.listener import GoogleAppsListener
from univention.googleapps.handler import ForbiddenError

_ = Translation('univention-management-console-module-googleapps').translate


def sanitize_body(sanizer):  # TODO: move into UMC core
	def _decorator(function):
		@functools.wraps(function)
		def _decorated(self, request, *args, **kwargs):
			try:
				sanizer.sanitize('request.body', {'request.body': request.body})
			except MultiValidationError as exc:
				raise UnprocessableEntity(str(exc), exc.result())
			except ValidationError as exc:
				raise UnprocessableEntity(str(exc), {exc.name: str(exc)})
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
		fqdn = '%s.%s' % (ucr['hostname'], ucr['domainname'])
		sso_fqdn = ucr.get('ucs/server/sso/fqdn', 'ucs-sso.%s' % (ucr['domainname'],))
		return {
			'initialized': GappsAuth.is_initialized(),
			'sign-in-url': 'https://%s/simplesamlphp/saml2/idp/SSOService.php' % (sso_fqdn,),
			'sign-out-url': 'https://%s/simplesamlphp/saml2/idp/SingleLogoutService.php?ReturnTo=/univention/' % (sso_fqdn,),
			'change-password-url': 'https://%s/univention/management/' % (fqdn,),
		}

	@allow_get_request
	def certificate(self, request):
		with open(ucr['saml/idp/certificate/certificate'], 'rb') as fd:
			self.finished(request.id, fd.read(), mimetype='application/octet-stream')

	@file_upload
	@sanitize(DictSanitizer(dict(
		tmpfile=StringSanitizer(required=True)
	), required=True))
	@sanitize_body(DictSanitizer(dict(
		email=EmailSanitizer(required=True),
		domain=StringSanitizer(required=True),
	), required=True))
	def upload(self, request):
		GappsAuth.uninitialize()
		with open(request.options[0]['tmpfile']) as fd:
			try:
				data = json.load(fd)
			except ValueError:
				raise UMC_Error(_('The uploaded file is not a JSON credentials file.'))
			try:
				GappsAuth.store_credentials(data, request.body['email'], domain=request.body['domain'])
			except GoogleAppError as exc:
				raise UMC_Error(str(exc))
		self.finished(request.id, {
			'client_id': data['client_id'],
			'scope': ','.join(SCOPE),
			# 'serviceaccounts_link': 'https://console.developers.google.com/permissions/serviceaccounts?project=%s' % (urllib.quote(data['project_id']),)
		}, message=_('The credentials have been successfully uploaded.'))

	@simple_response
	def state(self):
		if not GappsAuth.is_initialized():
			raise UMC_Error(_('The configuration of Google Apps for Work is not yet complete.'))
		try:
			ol = GoogleAppsListener(None, {}, {})
			ol.gh.list_users(projection="basic")
			try:
				subprocess.call(["service", "univention-directory-listener", "restart"])
			except (EnvironmentError,):
				pass
			return progress(finished=True)
		except AuthenticationErrorRetry:
			return progress(message=_('Waiting for Google directory to authorize the connection.'))
		except (AuthenticationError, ForbiddenError, SSLError) as exc:
			raise UMC_Error(str(exc))
