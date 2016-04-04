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
					headerText: _('Google Apps for Work information'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'already-initialized',
						content: _('<b>Warning!</b> The current connection information will be replaced if the user continues.'),
						visible: false
					}, {
						type: Text,
						name: 'info',
						content: this.getTextStart()
					}]
				}, {
					name: 'create-project',
					headerText: _('Create a new project'),
					helpText: '',
					widgets: [{
						name: 'infos',
						type: Text,
						content: this.getTextCreateProject()
					}]
				}, {
					name: 'create-service-account-key',
					headerText: _('Create service account key'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'infos',
						content: this.getTextCreateServiceAccountKey()
					}, {
						type: TextBox,
						name: 'email',
						label: _('E-mail address'),
						required: true,
						onChange: lang.hitch(this, function(value) {
							this.getWidget('create-service-account-key', 'upload').set('dynamicOptions', {
								email: value
							});
						})
					}, {
						type: Text,
						name: 'complete',
						content: this.formatOrderedList([_('Upload the credentials key file below')], {start: 4})
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
					helpText: '',
					widgets: [{
						type: Text,
						name: 'infos',
						content: this.getTextEnableDomainWideDelegation()
					}]
				}, {
					name: 'authorize',
					headerText: _('Authorize connection between Google and UCS'),
					helpText: '',
					widgets: [{
						type: Text,
						name: 'infos',
						content: _('To authorize the connection between this App and Google Apps for Work please follow these instructions:') +
							'<ol><li>' +
							_('Access the <a href="https://admin.google.com/ManageOauthClients" target="_blank">Admin console</a> to <i>Manage API client access</i>') + '</li><li>' +
							_('Enter the information below into the corresponding field and click <i>Authorize</i>') + '</li></ol>'
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
							_('Users can now be synced to Google Apps 4 Work by activating the sync on the users <i>Google Apps for Work?</i> tab.')
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
			return '<p>' + _('Google Apps for Work is ….') + '</p><p>' +
				_('To configure the connection to Google a Google Apps for Work account is required.') + '<br>' +
				_('…Domain the gapps account is registred for…') +
				'</p>';
		},

		getTextCreateProject: function() {
			return this.formatOrderedList([
				_('Please login to the <a href="https://console.developers.google.com/" target="_blank">Google Developers Console</a>'),
				_('Create a new project, an arbritrary name can be chosen.'),
				_('Go to the <i>API Manager</i>, select the <i>Admin SDK</i> and enable it') + this.img('create-project') + this.img('admin-sdk.png')
			]);
		},

		getTextCreateServiceAccountKey: function() {
			return _('Navigate to <i>Credentials</i> and create a new <i>Service account key</i>') + this.formatOrderedList([
				_('Choose <i>new service account</i> in the drop down menu, enter a name for the service account (e.g. <i>UCS sync</i>) and select <i>JSON</i> as the key type') + this.img('create-service-account-key.png') + this.img('credentials-tab.png'),
				_('This will offer you to download the key file after clicking on <i>create</i>. Save this key file on your hard disk'),
				_('Enter the email adress of the admin user you used to login to the Google Developers Console')
			]);
				
		},

		getTextEnableDomainWideDelegation: function() {
			return this.formatOrderedList([
				_('Still on the <i>Credentials</i> page, click on <a href="{serviceaccounts_link}" target="_blank">Manage service accounts</a>'),
				_('Edit the service account you just created by right clicking the three dots on the right') + this.img('edit-dots.png'),
				_('Enable <i>Google Apps Domain-wide Delegation</i> and enter <i>UCS sync FIXME: required?</i> as <i>Product name for the consent screen</i>') + this.img('edit-service-account')
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
			this._next('create-service-account-key');
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
			if (pageName == 'create-service-account-key') {
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
			if (~array.indexOf(['start', 'create-project', 'create-service-account-key', 'connectiontest', 'error'], pageName)) {
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
