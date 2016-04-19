"""
Common functions used by tests.
"""
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

import random
from operator import itemgetter


import univention.admin.objects  # Bug #33359
import univention.admin.syntax as udm_syntax
import univention.testing.strings as uts
import univention.testing.ucr as ucr_test
import univention.testing.utils as utils

from univention.googleapps.handler import ResourceNotFoundError


udm2google = dict(
	firstname=lambda x: itemgetter("givenName")(itemgetter("name")(x)),
	lastname=lambda x: itemgetter("familyName")(itemgetter("name")(x)),
	set=dict(
		mailPrimaryAddress=lambda x: itemgetter("primaryEmail")(x),
		city=lambda x: [y.get("locality") for y in itemgetter("addresses")(x)],
		country=lambda x: [y.get("countryCode") for y in itemgetter("addresses")(x)],
		departmentNumber=lambda x: [y.get("extendedAddress") for y in itemgetter("addresses")(x)],
		employeeNumber=lambda x: [y.get("value") for y in itemgetter("externalIds")(x)],
		employeeType=lambda x: [y.get("description") for y in itemgetter("organizations")(x)],
		organisation=lambda x: [y.get("name") for y in itemgetter("organizations")(x)],
		postcode=lambda x: [y.get("postalCode") for y in itemgetter("addresses")(x)],
		roomNumber=lambda x: [y.get("locality") for y in itemgetter("addresses")(x)],
		street=lambda x: [y.get("streetAddress") for y in itemgetter("addresses")(x)]
	),
	append=dict(
		homePostalAddress=lambda x: [y.get("formatted") for y in itemgetter("addresses")(x)],
		homeTelephoneNumber=lambda x: [y.get("value") for y in itemgetter("phones")(x)],
		mailAlternativeAddress=lambda x: [y.get("address") for y in itemgetter("emails")(x)],
		mobileTelephoneNumber=lambda x: [y.get("value") for y in itemgetter("phones")(x)],
		pagerTelephoneNumber=lambda x: [y.get("value") for y in itemgetter("phones")(x)],
		phone=lambda x: [y.get("value") for y in itemgetter("phones")(x)],
		secretary=lambda x: [y.get("value") for y in itemgetter("relations")(x)]
	)
)
udm2google["append"]["e-mail"] = lambda x: [y.get("address") for y in itemgetter("emails")(x)]

listener_attributes_data = dict(
	anonymize=[],
	listener=["cn", "description", "uniqueMember", "mailPrimaryAddress"],
	template=dict(
		organizations=[
			dict(
				description='%employeeType',
				primary='True',
				name='%o'
			)
		],
		externalIds=[
			dict(
				type='organization',
				value='%employeeNumber'
			)
		],
		name=dict(
			givenName='%givenName',
			familyName='%sn',
			fullName='%displayName'
		),
		phones=[
			dict(
				type='work',
				value='%telephoneNumber'
			),
			dict(
				type='home',
				value='%homePhone'
			),
			dict(
				type='pager',
				value='%pager'
			),
			dict(
				type='mobile',
				value='%mobile'
			)
		],
		relations=[
			dict(
				customType='secretary',
				type='custom',
				value='%secretary'
			)
		],
		emails=[
			dict(
				type='work',
				address='%mail'
			),
			dict(
				type='other',
				address='%mailAlternativeAddress'
			)
		],
		addresses=[
			dict(
				type='home',
				formatted='%homePostalAddress'
			),
			dict(
				customType='locality',
				type='custom',
				locality='%roomNumber'
			),
			dict(
				countryCode='%st',
				locality='%l',
				streetAddress='%street',
				postalCode='%postalCode',
				extendedAddress='%departmentNumber',
				type='work'
			)
		]
	),
	never=[],
	google_attribs=dict(
		telephoneNumber=['phones'],
		departmentNumber=['addresses'],
		employeeType=['organizations'],
		homePostalAddress=['addresses'],
		mobile=['phones'],
		sn=['name'],
		roomNumber=['addresses'],
		l=['addresses'],
		o=['organizations'],
		st=['addresses'],
		mailAlternativeAddress=['emails'],
		street=['addresses'],
		employeeNumber=['externalIds'],
		mail=['emails'],
		postalCode=['addresses'],
		displayName=['name'],
		mailPrimaryAddress=['primaryEmail'],
		givenName=['name'],
		pager=['phones'],
		homePhone=['phones'],
		secretary=['relations']
	),
	required_properties=dict(
		emails=["address"],
		externalIds=["value"],
		ims=["im"],
		name=["familyName", "givenName"],
		notes=["value"],
		phones=["value"],
		relations=["value"],
		websites=["value"]
	)
)


class GoogleDirectoryTestObjects(object):
	def __init__(self, otype, gapps_handler, obj_ids=None):
		"""
		:param otype: str: type of object to delete ("user", "group")
		:param gapps_handler: GappsHandler object
		:param obj_ids: list of object IDs to delete from google directory
		when leaving the context manager
		"""
		self._otype = otype
		assert isinstance(obj_ids, list)
		self._obj_ids = obj_ids
		self._gapps_handler = gapps_handler

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		if not self._gapps_handler:
			return
		for obj_id in self._obj_ids:
			print ">>> Deleting test-{} '{}'...".format(self._otype, obj_id)
			try:
				obj_res = getattr(self._gapps_handler, "delete_{}".format(self._otype))(obj_id)
			except ResourceNotFoundError:
				print ">>> OK: Doesn't exist (anymore): {} '{}'.".format(self._otype, obj_id)
				continue

			if obj_res == "":
				print ">>> OK: deleted test-{} '{}'.".format(self._otype, obj_id)
			else:
				print ">>> Fail: could not delete test-{} '{}': {}".format(self._otype, obj_id, obj_res)


class GoogleDirectoryTestUsers(GoogleDirectoryTestObjects):
	def __init__(self, gapps_handler, user_ids=None):
		"""
		:param gapps_handler: GappsHandler object
		:param user_ids: list of user IDs to delete from google directory
		when leaving the context manager
		"""
		super(GoogleDirectoryTestUsers, self).__init__("user", gapps_handler, user_ids)


class GoogleDirectoryTestGroups(GoogleDirectoryTestObjects):
	def __init__(self, gapps_handler, group_ids=None):
		"""
		:param gapps_handler: GappsHandler object
		:param group_ids: list of group IDs to delete from google directory
		when leaving the context manager
		"""
		super(GoogleDirectoryTestGroups, self).__init__("group", gapps_handler, group_ids)


def google_group_args(domain=None):
	if not domain:
		ucr = ucr_test.UCSTestConfigRegistry()
		ucr.load()
		domain = ucr["domainname"]
	return dict(
		email="{}.{}@{}".format(uts.random_username(), uts.random_username(), domain),
		description=" ".join([uts.random_string() for _ in range(10)]),
		name=" ".join([uts.random_string() for _ in range(3)]),
	)


def google_user_args(domain=None, minimal=True):
	if not domain:
		ucr = ucr_test.UCSTestConfigRegistry()
		ucr.load()
		domain = ucr["domainname"]
	res = dict(
		name=dict(
			givenName=uts.random_string(),
			familyName=uts.random_string()
		),
		password=uts.random_string(),
		primaryEmail="{}@{}".format(uts.random_username(), domain),
	)
	if not minimal:
		res.update(dict(
			emails=[
				dict(
					address="{}@{}.com".format(uts.random_username(), uts.random_username()),
					type="work",
					primary=False
				),
				dict(
					address="{}@{}.com".format(uts.random_username(), uts.random_username()),
					type="home",
					primary=False
				)
			],
			addresses=[
				dict(
					countryCode="DE",
					streetAddress="Mary-Somerville-Str. 1",
					postalCode="28359",
					locality="Bremen",
					type="work"
				),
				dict(
					countryCode="FR",
					locality="Lyon",
					type="home",
				)
			],
			phones=[
				dict(
					type="work",
					value="+49 421 22232-00"
				),
				dict(
					type="home",
					value="+49 30 1234-56 79 / 0"
				),
			]
		))
	return res


def udm_user_args(domain=None, minimal=True):
	ucr = ucr_test.UCSTestConfigRegistry()
	ucr.load()
	if not domain:
		domain = ucr["domainname"]
	res = dict(
		firstname=uts.random_string(),
		lastname=uts.random_string(),
		set=dict(
			password=uts.random_string(),
			mailHomeServer="{}.{}".format(ucr["hostname"], ucr["domainname"]),
			mailPrimaryAddress="{}@{}".format(uts.random_username(), domain),
		)
	)
	if not minimal:
		res["set"].update(dict(
			birthday="19{}-0{}-{}{}".format(2 * uts.random_int(), uts.random_int(1, 9), uts.random_int(0, 2), uts.random_int(1)),
			city=uts.random_string(),
			country=random.choice(map(itemgetter(0), udm_syntax.Country.choices)),
			departmentNumber=uts.random_string(),
			description=uts.random_string(),
			employeeNumber=3 * uts.random_int(),
			employeeType=uts.random_string(),
			organisation=uts.random_string(),
			postcode=3 * uts.random_int(),
			roomNumber=3 * uts.random_int(),
			street=uts.random_string(),
			title=uts.random_string()
		))
		res["append"] = dict(
			homePostalAddress=['"{}" "{}" "{}"'.format(uts.random_string(), uts.random_string(), uts.random_string()),
				'"{}" "{}" "{}"'.format(uts.random_string(), uts.random_string(), uts.random_string())],
			homeTelephoneNumber=[uts.random_string(), uts.random_string()],
			mailAlternativeAddress=["{}@{}".format(uts.random_username(), domain),
				"{}@{}".format(uts.random_username(), domain)],
			mobileTelephoneNumber=[uts.random_string(), uts.random_string()],
			pagerTelephoneNumber=[uts.random_string(), uts.random_string()],
			phone=[12 * uts.random_int(), 12 * uts.random_int()],
			secretary=["uid=Administrator,cn=users,{}".format(ucr["ldap/base"]),
				"uid=Guest,cn=users,{}".format(ucr["ldap/base"])]
		)
		# func arg name with '-' not allowed
		res["append"]["e-mail"] = ["{}@{}".format(uts.random_username(), uts.random_username()),
			"{}@{}".format(uts.random_username(), uts.random_username())]
	return res


def check_udm2google_user(udm_args, g_user, domain=None, complete=True):
	# does not check if everything is perfect (e.g. for mobileTelephoneNumber
	# "type" should be "mobile"), but assumes that if the value can be found
	# where expected, then the rest will be fine too
	if not domain:
		ucr = ucr_test.UCSTestConfigRegistry()
		ucr.load()
		domain = ucr["domainname"]
	res = list()
	fail = False
	for k, v in [("firstname", udm2google["firstname"]), ("lastname", udm2google["lastname"])]:
		try:
			udm_value = udm_args[k]
		except KeyError:
			if complete:
				fail = True
				res.append((k, "value was not set", "cannot compare"))
			continue
		google_value = v(g_user)
		if udm_value != google_value:
			fail = True
			res.append((k, udm_value, google_value))

	for k, v in udm2google["set"].items():
		try:
			udm_value = udm_args["set"][k]
		except KeyError:
			if complete:
				fail = True
				res.append((k, "value was not set", "cannot compare"))
			continue
		try:
			google_value = v(g_user)
		except KeyError:
			fail = True
			res.append((k, "value was not set", "cannot compare"))
			continue
		if k == "mailPrimaryAddress":
			udm_value = "{}@{}".format(udm_value.rpartition("@")[0], domain)
		if isinstance(google_value, list):
			tmp_ok = udm_value in google_value
		else:
			tmp_ok = udm_value == google_value
		if not tmp_ok:
			fail = True
			res.append((k, udm_value, google_value))

	for k, v in udm2google["append"].items():
		try:
			udm_values = udm_args["append"][k]
		except KeyError:
			if complete:
				fail = True
				res.append((k, "value was not set", "cannot compare"))
			continue
		google_values = udm2google["append"][k](g_user)
		for udm_value in udm_values:
			if k == "homePostalAddress":
				udm_value = udm_value.replace('"', '').replace(" ", "$")
			if udm_value not in google_values:
				fail = True
				res.append((k, "'{}' (from {})".format(udm_value, udm_values), google_values))

	return not fail, res


def setup_domain(domainname, udm, ucr):
		position = "cn=domain,cn=mail,{}".format(ucr["ldap/base"])
		try:
			utils.verify_ldap_object("cn={},{}".format(domainname, position))
		except utils.LDAPObjectNotFound:
			print "*** Creating mail domain matching domain registered with google..."
			udm.create_object(
				"mail/domain",
				position=position,
				name=domainname
			)
