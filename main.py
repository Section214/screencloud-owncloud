import ScreenCloud
from PythonQt.QtCore import QFile, QSettings, QUrl
from PythonQt.QtGui import QWidget, QDialog, QDesktopServices, QMessageBox
from PythonQt.QtUiTools import QUiLoader
import owncloud, time, os, requests
from rfc3987 import match

class OwnCloudUploader():
    def __init__(self):
        self.uil = QUiLoader()
        self.loadSettings()

    def updateUi(self):
        self.loadSettings()
        if self.connectStatus:
            self.settingsDialog.group_connection.widget_status.label_status.setText("Valid")
        else:
            self.settingsDialog.group_connection.widget_status.label_status.setText("Unknown")
        self.settingsDialog.group_name.input_name.setText(self.nameFormat)
        self.settingsDialog.adjustSize()

    def showSettingsUI(self, parentWidget):
        self.parentWidget = parentWidget
        self.settingsDialog = self.uil.load(QFile(workingDir + "/settings.ui"), parentWidget)
        self.settingsDialog.group_connection.button_authenticate.connect("clicked()", self.startAuthenticationProcess)
        self.settingsDialog.group_name.input_name.connect("textChanged(QString)", self.nameFormatEdited)
        self.settingsDialog.connect("accepted()", self.saveSettings)

        self.loadSettings()
        self.settingsDialog.group_account.input_url.text = self.url
        self.settingsDialog.group_account.input_username.text = self.username
        self.settingsDialog.group_account.input_password.text = self.password
        self.settingsDialog.group_name.input_path.text = self.remotePath
        self.settingsDialog.group_name.input_name.text = self.nameFormat
        self.settingsDialog.group_clipboard.radio_dontcopy.setChecked(not self.copyLink)
        self.settingsDialog.group_clipboard.radio_directlink.setChecked(self.copyDirectLink)
        self.updateUi()
        self.settingsDialog.open()

    def loadSettings(self):
        settings = QSettings()
        settings.beginGroup("uploaders")
        settings.beginGroup("owncloud")
        self.url = settings.value("url", "")
        self.username = settings.value("username", "")
        self.password = settings.value("password", "")
        self.remotePath = settings.value("remote-path", "")
        self.connectStatus = settings.value("connect-status", "")
        self.nameFormat = settings.value("name-format", "Screenshot at %H:%M:%S")
        self.copyLink = settings.value("copy-link", "true") in ['true', True]
        self.copyDirectLink = settings.value("copy-direct-link", "false") in ['true', True]
        settings.endGroup()
        settings.endGroup()

    def saveSettings(self):
        settings = QSettings()
        settings.beginGroup("uploaders")
        settings.beginGroup("owncloud")
        settings.setValue("url", self.settingsDialog.group_account.input_url.text)
        settings.setValue("username", self.settingsDialog.group_account.input_username.text)
        settings.setValue("password", self.settingsDialog.group_account.input_password.text)
        settings.setValue("remote-path", self.settingsDialog.group_name.input_path.text)
        settings.setValue("connect-status", self.connectStatus)
        settings.setValue("name-format", self.settingsDialog.group_name.input_name.text)
        settings.setValue("copy-link", not self.settingsDialog.group_clipboard.radio_dontcopy.checked)
        settings.setValue("copy-direct-link", self.settingsDialog.group_clipboard.radio_directlink.checked)
        settings.endGroup()
        settings.endGroup()

    def isConfigured(self):
        self.loadSettings()
        return self.connectStatus

    def getFilename(self):
        self.loadSettings()
        return ScreenCloud.formatFilename(self.nameFormat)

    def upload(self, screenshot, name):
        return True

    def startAuthenticationProcess(self):
        if self.settingsDialog.group_account.input_url.text and self.settingsDialog.group_account.input_username.text and self.settingsDialog.group_account.input_password.text:
            self.saveSettings()
            self.loadSettings()
            if match(self.url, "URI"):
                try:
                    request = requests.get(self.url, timeout=3);

                    if request.status_code == 200:
                        oc = owncloud.Client(self.url)
                        oc.login(self.username, self.password)
                        self.connectStatus = "true"
                        self.saveSettings()
                        self.updateUi()
                except requests.exceptions.RequestException as e:
                    QMessageBox.critical(self.settingsDialog, "OwnCloud Connection Error", "The specified Server URL is invalid!")
                    settings = QSettings()
                    settings.remove("connect-status")
                    self.saveSettings()
                    self.updateUi()
                except Exception as e:
                    errorMessage = self.formatConnectionError(e.message)

                    if errorMessage == "401":
                        self.settingsDialog.group_connection.widget_status.label_status.setText("Invalid")
                    else:
                        QMessageBox.critical(self.settingsDialog, "OwnCloud Connection Error", errorMessage)
            else:
                QMessageBox.critical(self.settingsDialog, "OwnCloud Connection Error", "The specified Server URL is invalid!")
        else:
            missingFields = ""
            fieldText = "field"

            if not self.settingsDialog.group_account.input_url.text:
                missingFields = "\"Server URL\""

            if not self.settingsDialog.group_account.input_username.text:
                if missingFields == "":
                    missingFields = "\"Username\""
                else:
                    missingFields = missingFields + " and \"Username\""
                    fieldText = "fields"

            if not self.settingsDialog.group_account.input_password.text:
                if missingFields == "":
                    missingFields = "\"Password\""
                else:
                    missingFields = missingFields.replace(" and", ",") + " and \"Password\""
                    fieldText = "fields"

            QMessageBox.critical(self.settingsDialog, "OwnCloud Connection Error", "The " + missingFields + " " + fieldText + " must be filled in!")

    def upload(self, screenshot, name):
        self.loadSettings()
        timestamp = time.time()

        try:
            tmpFilename = QDesktopServices.storageLocation(QDesktopServices.TempLocation) + "/" + ScreenCloud.formatFilename(str(timestamp))
        except AttributeError:
            from PythonQt.QtCore import QStandardPaths #fix for Qt5
            tmpFilename = QStandardPaths.writableLocation(QStandardPaths.TempLocation) + "/" + ScreenCloud.formatFilename(str(timestamp))

        screenshot.save(QFile(tmpFilename), ScreenCloud.getScreenshotFormat())

        try:
            oc = owncloud.Client(self.url)
            oc.login(self.username, self.password)

            remotePath = ""

            if self.remotePath:
                remotePath = self.remotePath

                try:
                    oc.file_info(remotePath)
                except Exception:
                    oc.mkdir(remotePath)

            uploaded_image = oc.put_file(remotePath + "/" + ScreenCloud.formatFilename(name, False), tmpFilename)

            if self.copyLink:
                link_info = oc.share_file_with_link(remotePath + "/" + ScreenCloud.formatFilename(name, False))
                share_link = link_info.get_link()

                if self.copyDirectLink:
                    share_link = share_link + "/download"

                ScreenCloud.setUrl(share_link)
            return True
        except Exception as e:
            ScreenCloud.setError("Failed to upload to OwnCloud. " + e.message)
            return False

    def nameFormatEdited(self, nameFormat):
        self.settingsDialog.group_name.label_example.setText(ScreenCloud.formatFilename(nameFormat, False))

    def formatConnectionError(self, e):
        return {
            "HTTP error: 400": "OwnCloud was unable to process the request due to a client error!",
            "HTTP error: 401": "401",
            "HTTP error: 403": "The specified user is not permitted to access the API!",
            "HTTP error: 404": "The specified Server URL is invalid!",
            "HTTP error: 500": "OwnCloud was unable to process the request due to a server error!",
            "HTTP error: 502": "The specified Server URL appears to be offline!"
        }.get(e, e.replace("/ocs/v1.php/cloud/capabilities", ""))
