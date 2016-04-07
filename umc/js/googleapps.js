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
/*global define,require*/

define([
	"dojo/_base/declare",
	"dojo/_base/lang",
	"dojo/_base/array",
	"dojo/Deferred",
	"umc/tools",
	"umc/dialog",
	"umc/widgets/Module",
	"umc/widgets/Wizard",
	"umc/widgets/Text",
	"umc/widgets/TextBox",
	"umc/widgets/TextArea",
	"umc/widgets/Uploader",
	"umc/widgets/ProgressBar",
	"umc/i18n!umc/modules/googleapps",
	"xstyle/css!./googleapps.css"
], function(declare, lang, array, Deferred, tools, dialog, Module, Wizard, Text, TextBox, TextArea, Uploader, ProgressBar, _) {
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
					headerText: _('Welcome'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'already-initialized',
						content: _('<b>Warning!</b> The configuration has already been done. If you continue, the current connection information will be replaced.'),
						visible: false
					}, {
						type: Text,
						name: 'info',
						content: this.getTextStart()
					}]
				}, {
					name: 'create-project',
					headerText: _('Create a new project'),
					helpText: _('To allow UCS to synchronize selected user accounts to the Google directory, a new project must be created in the Google Developers Console.'),
					widgets: [{
						name: 'infos',
						type: Text,
						content: this.getTextCreateProject()
					}]
				}, {
					name: 'enable-admin-sdk-api',
					headerText: _('Enable Admin SDK API'),
					helpText: _('The <i>Admin SDK API</i> will be used to create user accounts and groups in Googles directory.'),
					widgets: [{
						name: 'infos',
						type: Text,
						content: this.getTextEnableAdminSDKAPI()
					}]
				}, {
					name: 'create-service-account-key',
					headerText: _('Create service account key'),
					helpText: _('Create an encryption key to securly authenticate the UCS server to the Google directory.'),
					widgets: [{
						type: Text,
						name: 'infos',
						content: this.getTextCreateServiceAccountKey()
					}]
				}, {
					name: 'upload-service-account-key',
					headerText: _('Upload service account key'),
					helpText: _('UCS will use the encryption key for comunication with the Google directory.'),
					widgets: [{
						type: Text,
						name: 'infos',
						content: this.getTextUploadServiceAccountKeyEmail()
					}, {
						type: TextBox,
						name: 'email',
						label: _('E-mail address'),
						required: true,
						onChange: lang.hitch(this, function(value) {
							this.getWidget('upload-service-account-key', 'upload').set('dynamicOptions', {
								email: value
							});
						})
					}, {
						type: Text,
						name: 'complete',
						content: this.getTextUploadServiceAccountKey()
					}, {
						type: Uploader,
						name: 'upload',
						buttonLabel: _('Upload service account key'),
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
					name: 'enable-domain-wide-delegation',
					headerText: _('Enable Google Apps domain wide delegation'),
					helpText: _('To allow UCS to automatically create, modify and delete Google user accounts, "Domain-wide Delegation" must be enabled for the service account.'),
					widgets: [{
						type: Text,
						name: 'infos',
						content: this.getTextEnableDomainWideDelegation()
					}]
				}, {
					name: 'authorize',
					headerText: _('Authorize connection between Google and UCS'),
					helpText: _('Fine grained access permissions for the service account must be configured in the Admin console.'),
					widgets: [{
						type: Text,
						name: 'infos',
						content: this.getTextAuthorizeConnection()
					}, {
						type: TextBox,
						name: 'client_id',
						sizeClass: 'Two',
						label: _('Client Name')
					}, {
						type: TextArea,
						name: 'scope',
						sizeClass: 'Two',
						label: _('One or More API Scopes')
					}]
				}, {
					name: 'connectiontest',
					headerText: _('Successfully configured Google Apps for Work'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'infos',
						content: _('Congratulations, the connection between UCS and Google Apps for Work has been established.') + ' ' +
							_('Users can now be synced to Google Apps 4 Work by activating the sync on the users <i>Google Apps</i> tab.')
					}]

				}, {
					name: 'error',
					headerText: _('An error occurred'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'error',
						content: _('An error occurred during testing the connection to Google Apps for Work.')
					}]
				}]
			});
			array.forEach(this.pages, function(page) {
				page['class'] = 'umc-googleapps-page umc-googleapps-page-' + page.name;
			});

		},

		postCreate: function() {
			this.inherited(arguments);

			tools.forIn(this._pages, function(name, page) {
				page.addChild(new Text({
					'class': 'umcPageIcon',
					region: 'nav'
				}));
			});
		},

		initWizard: function(data) {
			this.getWidget('start', 'already-initialized').set('visible', data.result.initialized);
		},

		getTextStart: function() {
			return '<p>' + _('Welcome to the Univention <a href="https://apps.google.com/" target="_blank">Google Apps for Work</a> configuration wizard.') + '</p><p>' +
				_('It will guide you through the process of setting up automatic provisioning of Google Apps for Work accounts for your user accounts.') + '<br>' +
				_('To use this app you need a valid Google Apps for Work admin acccount.') +
				'</p>';
		},

		getTextCreateProject: function() {
			return this.formatOrderedList([
				_('Please login to the <a href="https://console.developers.google.com/" target="_blank">Google Developers Console</a>.'),
				_('Create a new project by using the drop-down menu in the top navgation bar.'),
				_('Give the project a name, for example "UCS sync".') + this.img('new_project') + '<br>' +  _('Continue when Google has finished creating the project.')
			]);
		},

		getTextEnableAdminSDKAPI: function() {
			return this.formatOrderedList([
				_('Go to the <i>API Manager</i>') + this.img('api_manager_nav.png'),
				_('Open the <i>Admin SDK</i> page in the <i>Google Apps APIs</i> section.') + this.img('google_admin_sdk_link.png'),
//				_('Select the <i>Admin SDK</i> and enable it') + this.img('admin-sdk.png'),
				_('Enable it.') + this.img('google_admin_sdk_enable.png') + '<br>' + _('This may take a minute, continue when Google has finished enabling the Admin SDK API.')
			]);
		},

		getTextCreateServiceAccountKey: function() {
			return this.formatOrderedList([
				_('Navigate to <i>Credentials</i>') + this.img('credentials_nav.png'),
				_('Create a new <i>Service account key</i>. Choose <i>new service account</i> in the drop down menu.') + this.img('create_sevice_account_key.png'),
				_('Enter a name for the service account (e.g. <i>UCS sync</i>) and select <i>JSON</i> as the key type.') + this.img('new_service_account.png'),
				_('This will offer you to download the key file after clicking on <i>create</i>. Save this key file on your hard disk in a secure location.')
			]);
		},

		getTextUploadServiceAccountKeyEmail: function() {
			return this.formatOrderedList([
				_('Enter the email adress of the admin user you used to login to the Google Developers Console') + this.img('admin_email.png')
			]);
		},

		getTextUploadServiceAccountKey: function() {
			return this.formatOrderedList([
				_('Upload the credentials key file below.')
			], {start: 2});
		},

		getTextEnableDomainWideDelegation: function() {
			return this.formatOrderedList([
				//_('Still on the <i>Credentials</i> page, click on <a href="{serviceaccounts_link}" target="_blank">Manage service accounts</a>'),
				_('Still on the <i>Credentials</i> page, click on <i>Manage service accounts</i> on the right.'),
				_('Edit the service account you just created by right clicking the three dots on the right') + this.img('edit_service_account.png'),
				_('Enable <i>Google Apps Domain-wide Delegation</i> and enter a <i>Product name for the consent screen</i>.') + this.img('enable_delegation_and_prod_name.png')
			]);
		},

		getTextAuthorizeConnection: function() {
			return _('To authorize the connection between this App and Google Apps for Work please follow these instructions:') + this.formatOrderedList([
				_('<a href="https://admin.google.com/ManageOauthClients" target="_blank">Click here to access the Admin console</a> to <i>Manage API client access</i>'),
				_('Copy and paste the information below into the corresponding field and click <i>Authorize</i>') + this.img('authorize_api_access.png')
			]);
		},

		formatParagraphs: function(data) {
			return '<p>' + data.join('</p><p>') + '</p>';
		},

		formatOrderedList: function(data, props) {
			var start = (props && props.start) ? 'start="' + props.start + '" ' : '';
			return '<ol '+ start + 'style="padding: 0; list-style-position: inside;"><li>' + data.join('</li><li>')  + '</li></ol>';
		},

		img: function(image) {
			return '<br/><img style="min-width: 250px; max-width: 100%; padding-left: 1em; /*border: thin solid red;*/" src="' + require.toUrl('umc/modules/googleapps/' + image) + '">';
		},

		keyUploaded: function(data) {
			tools.forIn(data.result, lang.hitch(this, function(key, val) {
				var widget = this.getWidget(key);
				if (widget) {
					widget.set('value', val);
				}
			}));
			this._next('upload-service-account-key');
		},

		next: function(pageName) {
			var nextPage = this.inherited(arguments);
			if (nextPage == 'connectiontest') {
				return this.standbyDuring(this.umcpCommand('googleapps/test_configuration').then(function() {
					return nextPage;
				}, function() {
					return 'error';
				}));
			}
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
			if (pageName == 'upload-service-account-key') {
				buttons = array.filter(buttons, function(button) { return button.name != 'next'; });
			}
			return buttons;
		},

		hasNext: function(pageName) {
			if (~array.indexOf(['connectiontest', 'error'], pageName)) {
				return false;
			}
			return this.inherited(arguments);
		},

		hasPrevious: function(pageName) {
			if (~array.indexOf(['enable-domain-wide-delegation', 'error', 'connectiontest'], pageName)) {
				return false;
			}
			return this.inherited(arguments);
		},

		canCancel: function(pageName) {
			if (~array.indexOf(['start', 'create-project', 'upload-service-account-key', 'connectiontest', 'error'], pageName)) {
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
