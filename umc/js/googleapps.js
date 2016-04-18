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
/*global define,require,setTimeout*/

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
						content: _('<b>Warning!</b> The configuration has already been done. If you continue, the current connection settings will be replaced.'),
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
					headerText: _('Enable the <i>Admin SDK API</i>'),
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
					helpText: _('UCS will use the encryption key for communicating with the Google directory.'),
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
								email: value,
								domain: this.getWidget('upload-service-account-key', 'domain').get('value')
							});
						})
					}, {
						type: Text,
						name: 'info-domain',
						content: this.getTextUploadServiceAccountKeyDomain()
					}, {
						type: TextBox,
						name: 'domain',
						label: _('Verified domain name'),
						required: true,
						onChange: lang.hitch(this, function(value) {
							this.getWidget('upload-service-account-key', 'upload').set('dynamicOptions', {
								domain: value,
								email: this.getWidget('upload-service-account-key', 'email').get('value')
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
							email: '',
							domain: ''
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
					}, {
						type: Text,
						name: 'infos-end',
						content: this.getTextAuthorizeConnectionEnd()
					}]
				}, {
					name: 'single-sign-on-setup',
					headerText: _('Single Sign-On setup'),
					helpText: _('The UCS SAML Identity Provider needs to be configured in the security settings.'),
					widgets: [{
						type: Text,
						name: 'infos',
						content: this.getTextSingleSignOnSetup()
					}, {
						type: TextBox,
						name: 'sign-in-url',
						label: _('Sign-in page URL'),
						sizeClass: 'Two',
						value: ''
					}, {
						type: TextBox,
						name: 'sign-out-url',
						label: _('Sign-out page URL'),
						sizeClass: 'Two',
						value: ''
					}, {
						type: TextBox,
						name: 'change-password-url',
						label: _('Change password URL'),
						sizeClass: 'Two',
						value: ''
					}, {
						type: Text,
						name: 'download_link',
						content: this.getTextSingleSignOnSetupCertificate()
					}]
				}, {
					name: 'success1',
					headerText: _('Successfully configured Google Apps for Work'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'infos',
						content: _('Congratulations, the connection between UCS and Google Apps for Work has been established.') + ' ' +
							_('You can now activate the Google Apps for Work synchronization for users on the <i>Google Apps</i> tab in the %s.', [tools.linkToModule({module: 'udm', flavor: 'users/user'})]) + '<br>' + this.img(_('google_user.png'))
					}]
				}, {
/*					name: 'success2',
					headerText: _('Successfully configured Google Apps for Work'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'infos',
						content: '<p></p>'
					}]
				}, {
*/					name: 'success3',
					headerText: _('Successfully configured Google Apps for Work'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'infos',
						content: _('Synchronized users can log into Google Apps for Work by using the link on the <a href="/ucs-overview#services" target="_blank">UCS overview page</a>.') + '<br>' + this.img(_('google-sso-login.png'))
					}]
				}, {
					name: 'error',
					headerText: _('An error occurred'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'error',
						content: _('An error occurred while testing the connection to Google Apps for Work. Please run the wizard again.')
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
			tools.forIn(data.result, lang.hitch(this, function(key, value) {
				var widget = this.getWidget(key);
				if (widget) {
					widget.set('value', value);
				}
			}));
		},

		getTextStart: function() {
			return '<p>' + _('Welcome to the Univention <a href="https://apps.google.com/" target="_blank">Google Apps for Work</a> configuration wizard.') + '</p><p>' +
				_('It will guide you through the process of setting up automatic provisioning of Google Apps for Work accounts for your user accounts.') + '<br>' +
				_('To use this app you need a valid Google Apps for Work admin acccount and a <a href="https://support.google.com/a/topic/9196" target="_blank">verified domain</a>.') +
				'</p>';
		},

		getTextCreateProject: function() {
			return _('Please follow the steps to create a new project in the <i>Google Developers Console</i>.') + this.formatOrderedList([
				_('Login to the <a href="https://console.developers.google.com/" target="_blank">Google Developers Console</a>.'),
				_('Create a new project by using the drop down menu in the top navgation bar.') + this.img(_('new_project_navigation.png')),
				_('Give the project a name, for example "UCS sync".') + this.img(_('new_project.png')) + '<br>' +  _('Continue when Google has finished creating the project by clicking on <i>Next</i>.')
			]);
		},

		getTextEnableAdminSDKAPI: function() {
			return this.formatOrderedList([
				_('Make sure you are in the <i>API Manager</i>.') + this.img(_('api_manager_nav.png')),
				_('Open the <i>Admin SDK</i> page in the <i>Google Apps APIs</i> section.') + this.img(_('google_admin_sdk_link.png')),
				_('Enable it.') + this.img(_('google_admin_sdk_enable.png')) + '<br>' + _('This may take a minute. When Google has finished enabling the Admin SDK API, continue by clicking on <i>Next</i>.')
			]);
		},

		getTextCreateServiceAccountKey: function() {
			return this.formatOrderedList([
				_('Navigate to <i>Credentials</i>') + this.img(_('credentials_nav.png')),
				_('Click on <i>Create credentials</i> and select <i>Service account key</i>.') + this.img(_('create_service_account_key.png')),
				_('In the new window choose <i>New service account</i> from the drop down menu. Enter a name for the service account (e.g. <i>UCS sync</i>) and select <i>JSON</i> as the key type. The <i>Service account ID</i> will be generated automatically and can be kept like this.') + this.img(_('new_service_account.png')),
				_('This will offer you to download the key file after clicking on <i>Create</i>. Save this key file on your hard disk in a secure location.') + '<br>' + _('Then continue by clicking on <i>Next</i>.')
			]);
		},

		getTextUploadServiceAccountKeyEmail: function() {
			return '<p>' + _('The setup wizard now needs the e-mail address of the administrator user you used to login to the Google Developers Console. The e-mail address can be displayed by clicking on the profile button in the top right corner.') + this.img(_('admin_email.png')) + '</p>' + this.formatOrderedList([
				_('Enter the e-mail address into the input field below.')
			]);
		},

		getTextUploadServiceAccountKeyDomain: function() {
			return this.formatOrderedList([
				_('Enter the domain that was verified during the configuration of the Google Apps for Work account.')
			], {start: 2});
		},

		getTextUploadServiceAccountKey: function() {
			return this.formatOrderedList([
				_('Click on the button below and select the just downloaded JSON key file. This will upload the credentials key file to UCS.')
			], {start: 3});
		},

		getTextEnableDomainWideDelegation: function() {
			return this.formatOrderedList([
				//<a href="{serviceaccounts_link}" target="_blank">Manage service accounts</a>
				_('On the <i>Credentials</i> page in the Google Developers Console, click in the very right on <i>Manage service accounts</i>.'),
				_('Then edit the service account you just created by clicking the three dots on the right.') + this.img(_('edit_service_account.png')),
				_('Enable <i>Google Apps Domain-wide Delegation</i> and enter a <i>Product name for the consent screen</i> and click on <i>Save</i>.') + this.img(_('enable_delegation_and_prod_name.png')) + '<br>' + _('Continue by clicking on <i>Next</i>.')
			]);
		},

		getTextAuthorizeConnection: function() {
			return _('To authorize the connection between this App and Google Apps for Work please follow these instructions:') + this.formatOrderedList([
				_('<a href="https://admin.google.com/ManageOauthClients" target="_blank">Click here to access the Admin console</a> to <i>Manage API client access</i>.'),
				_('Copy and paste the information below into the corresponding fields.') + this.img(_('authorize_api_access_EN.png'))
			]);
		},

		getTextAuthorizeConnectionEnd: function() {
			return this.formatOrderedList([
				_('Click on <i>Authorize</i> and continue this wizard by clicking on <i>Next</i>.')
			], {start: 3});
		},

		getTextSingleSignOnSetup: function() {
			return '<p>' + _('To finalize the setup, single sign-on has to be configured for the Google Apps for Work domain.') + '</p>' + this.formatOrderedList([
				_('Open the <a href="https://admin.google.com/AdminHome?fral=1#SecuritySettings:flyout=sso" target="_blank">security settings in the Admin Console</a> to configure the single sign-on settings.'),
				_('In the security settings only the checkbox <i>Setup SSO with third party identity provider</i> needs to be activated and the following values inserted into the input fields:') + this.img('google_sso_EN.png')
			]);
		},

		getTextSingleSignOnSetupCertificate: function() {
			return this.formatOrderedList([
				_('After setting these addresses, click on <i>Save</i> in the Google Developers Console.'),
				_('Download the <a download="certificate.crt" href="/simplesamlphp/saml2/idp/certificate" target="_blank">UCS Identity Provider certificate</a>.'),
				_('Then upload it to the Google Developers Console under <i>Verification certificate</i>.'),
				_('Click on <i>Next</i> to complete the setup.')
			], {start: 3});
		},

		formatParagraphs: function(data) {
			return '<p>' + data.join('</p><p>') + '</p>';
		},

		formatOrderedList: function(data, props) {
			var start = (props && props.start) ? 'start="' + props.start + '" ' : '';
			return '<ol '+ start + 'style="padding: 0; list-style-position: inside;"><li>' + data.join('</li><li>')  + '</li></ol>';
		},

		img: function(image) {
			return '<br/><img style="min-width: 250px; max-width: 100%; padding-left: 1em;" src="' + require.toUrl('umc/modules/googleapps/' + image) + '">';
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
			if (nextPage == 'single-sign-on-setup') {
				return this.testConnection().then(function() {
					return nextPage;
				}, function() {
					return 'error';
				});
			}
			return nextPage;
		},

		testConnection: function() {
			this.resetProgress();
			this.startPolling();
			return this.standbyDuring(this._progressDeferred, this._progressBar);
		},

		resetProgress: function() {
			if (this._progressDeferred && !this._progressDeferred.isFulfilled()) {
				this._progressDeferred.cancel();
			}
			this._progressBar = new ProgressBar();
			this._progressDeferred = new Deferred();
			this._progressBar.setInfo(null, null, Infinity);
			this._progressBar.feedFromDeferred(this._progressDeferred, _('Google Apps for Work configuration'));
		},

		startPolling: function() {
			return this.umcpCommand('googleapps/state').then(lang.hitch(this, function(data) {
				var result = data.result || {};
				result.percentage = result.percentage || Infinity;
				this._progressDeferred.progress(result);
				if (result.finished) {
					this._progressDeferred.resolve(result);
					return;
				}
				if (!this._progressDeferred.isFulfilled()) {
					setTimeout(lang.hitch(this, 'startPolling'), 500);
				}
			}), lang.hitch(this, function(error) {
				this._progressDeferred.reject();
			}));
		},

		getFooterButtons: function(pageName) {
			var buttons = this.inherited(arguments);
			//if (pageName == 'single-sign-on-setup') {
			//	array.forEach(buttons, function(button) {
			//		if (button.name == 'next') {
			//			button.label = _('Finish');
			//		}
			//	});
			//} else
			if (pageName == 'upload-service-account-key') {
				buttons = array.filter(buttons, function(button) { return button.name != 'next'; });
			}
			return buttons;
		},

		hasNext: function(pageName) {
			if (~array.indexOf(['success3', 'error'], pageName)) {
				return false;
			}
			return this.inherited(arguments);
		},

		hasPrevious: function(pageName) {
			if (~array.indexOf(['enable-domain-wide-delegation', 'single-sign-on-setup', 'error', 'success1'], pageName)) {
				return false;
			}
			return this.inherited(arguments);
		},

		canCancel: function(pageName) {
			if (~array.indexOf(['start', 'create-project', 'upload-service-account-key', 'success1', 'success2', 'success3', 'error'], pageName)) {
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
			this.on('close', lang.hitch(this, function() {
				if (this._wizard._progressDeferred) {
					this._wizard._progressDeferred.reject();
				}
			}));
		},

		buildRendering: function() {
			this.inherited(arguments);
			this.addChild(this._wizard);
		}
	});
});
