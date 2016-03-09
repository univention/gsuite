#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
#
# Univention Google Apps for Work App - setup test data
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

#
# Needs /etc/univention-google-apps/key.p12
#

from univention.googleapps.auth import GappsAuth, SCOPE

client_email = "655137666938-hjfqtqbpitgq30k5p897dunfltshs6mv@developer.gserviceaccount.com"
SUBACCOUNT = 'testadmin@univention.de'

my_key_file = "/root/MyProject-a2bcca242487.p12"

GappsAuth.store_ssl_key(open(my_key_file, "rb").read())
GappsAuth.store_credentials(client_email=client_email, scope=SCOPE, impersonate_user=SUBACCOUNT)
