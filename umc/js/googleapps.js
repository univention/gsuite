/*
 * Copyright 2016 Univention GmbH
 *
 * http://www.univention.de/
 *
 * All rights reserved.
 *
 * The source code of this program is made available
 * under the terms of the GNU Affero General Public License version 3
 * (GNU AGPL V3) as published by the Free Software Foundation.
 *
 * Binary versions of this program provided by Univention to you as
 * well as other copyrighted, protected or trademarked materials like
 * Logos, graphics, fonts, specific documentations and configurations,
 * cryptographic keys etc. are subject to a license agreement between
 * you and Univention and not subject to the GNU AGPL V3.
 *
 * In the case you use this program under the terms of the GNU AGPL V3,
 * the program is provided in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public
 * License with the Debian GNU/Linux or Univention distribution in file
 * /usr/share/common-licenses/AGPL-3; if not, see
 * <http://www.gnu.org/licenses/>.
 */
/*global define,window*/

define([
	"dojo/_base/declare",
	"dojo/_base/lang",
	"dojo/_base/array",
	"dojo/Deferred",
	"umc/dialog",
	"umc/widgets/Module",
	"umc/widgets/Wizard",
	"umc/widgets/Text",
	"umc/widgets/TextBox",
	"umc/widgets/Uploader",
	"umc/widgets/ProgressBar",
	"umc/i18n!umc/modules/googleapps"
], function(declare, lang, array, Deferred, dialog, Module, Wizard, Text, TextBox, Uploader, ProgressBar, _) {
	var SetupWizard = declare('umc.modules.googleapps.SetupWizard', [Wizard], {

		_uploadDeferred: null,
		autoValidate: true,
		autoFocus: true,
		authorizationurl: null,

		constructor: function() {
			this.inherited(arguments);

			lang.mixin(this, {
				pages: [{
					name: 'start',
					headerText: _('HEADER TEXT'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'already-initialized',
						content: _('<b>Warning!</b> The current connection information will be replaced if the user continues.'),
						visible: false
					}, {
						type: Text,
						name: 'info',
						content: '<p>' + _('INTRODUCTION.') + '</p><p>' +
							_('Google Apps for Work account') + '<br>' +
							_('Domain the gapps account is registred for') +
							'</p>'
					}]
				}, {
					name: 'login',
					headerText: _('HEADER TEXT'),
					helpText: '',
					widgets: [{
						name: 'infos',
						type: Text,
						content: '<ol>' +
							'<li>' + _('login to the Google Developers Console https://console.developers.google.com/') + '</li>' +
							'<li>' + _('create a new project, the name doesnt matter') + '</li>' +
							'<li>' + _('go to the "API Manager", select the "Admin SDK" and enable it') + '</li>' +
							'</ol>'
					}]
				}, {
					name: 'create-service-account-key',
					headerText: _('Create service account key'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'infos',
						content: _('go to "Credentials" and create a new "Service account key"') + '<ol>' +
							'<li>' + _('the type must be "new service account", the key type must be "JSON".') + '</li>' +
							'<li>' + _('save the key file and upload it to the wizard') + '</li>' +
							'<li>' + _('enter the email adress of the admin user you used to login to the google dev console') + '</li>' +
							'</ol>'
					}, {
						type: TextBox,
						name: 'email',
						label: _('E-Mail address'),
						onChange: lang.hitch(this, function(value) {
							this.getWidget('create-service-account-key', 'upload').set('dynamicOptions', {
								email: value
							});
						})
					}, {
						type: Uploader,
						name: 'upload',
						buttonLabel: _('Upload JSON service account key'),
						command: 'googleapps/upload',
						dynamicOptions: {
							email: ''
						},
						onUploadStarted: lang.hitch(this, function() {
							this._uploadDeferred = new Deferred();
							this.standbyDuring(this._uploadDeferred);
							this._uploadDeferred.then(lang.hitch(this, 'keyUploaded'));
						}),
						onUploaded: lang.hitch(this, function(result) {
							this._uploadDeferred.resolve(result);
						}),
						onError: lang.hitch(this, function(error) {
							this._uploadDeferred.reject(error);
						})
					}]
				}, {
					name: 'foo',
					headerText: _('HEAD TEXT'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'infos',
						content: '<ol><li>' + _('still on the "Credentials" page, click on "Manage service account"') + '</li><li>' +
							_('click on the three dots on the right of the service account you just created and choose to "Edit" it') + '</li><li>' +
							_('Enable "Google Apps Domain-wide Delegation" and enter "UCS sync" as "Product name for the consent screen"')  + '</li>' +
							'</li></ol>'
					}]
				}, {
					name: 'authorize',
					headerText: _('AUTHORIZE'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'infos',
						content: _('To authorize the connection between this App and Google Apps for Work please follow these instructions:') +
							'<ol><li>' +
							_('go to the "Admin console" to "Manage API client access": https://admin.google.com/ManageOauthClients') + '</li><li>' +
							_('Authorize API access') + '</ul><li>' +
							_('Client Name: {client_id}') + '</li><li>' +
							_('One or More API Scopes: {scope}') + '</ul></li><li>' +
							_('click "Authorize"') + '</li></ol>'
					}]
				}, {
					name: 'connectiontest',
					headerText: _('Connectiontest'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'infos',
						content: _('Congratulations, the connection between UCS and Google Apps for Work has been established.') + ' ' +
							_('Users can now be synced to Google Apps 4 Work by activating the sync on the users <i>Google Apps for Work?</i> tab.')
					}]

				}]
			});
		},

		initWizard: function(data) {
			this.getWidget('start', 'already-initialized').set('visible', data.result.initialized);
		},

		next: function(pageName) {
			var nextPage = this.inherited(arguments);
			return nextPage;
		},

		getFooterButtons: function(pageName) {
			var buttons = this.inherited(arguments);
		//	if (pageName == '') {
		//		array.forEach(buttons, function(button) {
		//			if (button.name == 'next') {
		//				button.label = _('Finish');
		//			}
		//		});
		//	} else
			if (pageName == "") {
				buttons = array.filter(buttons, function(button) { return button.name != 'next'; });
			}
			return buttons;
		},

		hasNext: function(pageName) {
			if (~array.indexOf([], pageName)) {
				return false;
			}
			return this.inherited(arguments);
		},

		hasPrevious: function(pageName) {
			if (~array.indexOf([], pageName)) {
				return false;
			}
			return this.inherited(arguments);
		},

		canCancel: function(pageName) {
			if (~array.indexOf([], pageName)) {
				return false;
			}
			return this.inherited(arguments);
		}
	});
	return declare("umc.modules.googleapps", [ Module ], {
		_wizard: null,

		unique: true,

		postMixInProperties: function() {
			this.inherited(arguments);
			this._wizard = new SetupWizard({
				umcpCommand: lang.hitch(this, 'umcpCommand')
			});
			this.standbyDuring(this.umcpCommand('googleapps/query').then(lang.hitch(this._wizard, 'initWizard')));
			this._wizard.on('finished', lang.hitch(this, 'closeModule'));
			this._wizard.on('cancel', lang.hitch(this, 'closeModule'));
		},

		buildRendering: function() {
			this.inherited(arguments);
			this.addChild(this._wizard);
		}
	});
});
