from burp import IBurpExtender, IMessageEditorTabFactory, IMessageEditorTab
from javax.swing import JPanel, JButton, BoxLayout, JTabbedPane
from java.awt.event import ActionListener
from urllib import unquote
import json


class BurpExtender(IBurpExtender, IMessageEditorTabFactory):
    def registerExtenderCallbacks(self, callbacks):
        self._callbacks = callbacks
        self._helpers = callbacks.getHelpers()
        callbacks.setExtensionName("Meta GraphQL")
        callbacks.registerMessageEditorTabFactory(self)

    def createNewInstance(self, controller, editable):
        return GraphQLRequestTab(self, controller, editable)


class GraphQLRequestTab(IMessageEditorTab):
    def __init__(self, extender, controller, editable):
        self._extender = extender
        self._helpers = extender._helpers
        self._editable = editable

        # Use Burp Suite's built-in message editor
        self._editor = extender._callbacks.createMessageEditor(controller, editable)

        # Create panel UI
        self._panel = JPanel()
        self._panel.setLayout(BoxLayout(self._panel, BoxLayout.Y_AXIS))
        self._scanButton = JButton("Scan", actionPerformed=self.scanRequest)
        self._panel.add(self._editor.getComponent())
        self._panel.add(self._scanButton)

        self._currentMessage = None
        self._currentRequestInfo = None
        self._responseTab = None
        self._tabbedPane = None

    def getTabCaption(self):
        return "Meta GraphQL"

    def getUiComponent(self):
        return self._panel

    def isEnabled(self, content, isRequest):
        if isRequest:
            try:
                request_info = self._helpers.analyzeRequest(content)
                headers = request_info.getHeaders()
                body = content[request_info.getBodyOffset():].tostring()
                return "graphql" in headers[0].lower() and (
                    "fb_api_req_friendly_name" in body
                    or "variables" in body
                    or "doc_id" in body
                )
            except:
                return False
        return False

    def setMessage(self, content, isRequest):
        if content is None:
            self._editor.setMessage(None, isRequest)
        else:
            if isRequest:
                self._currentMessage = content
                self._currentRequestInfo = self._helpers.analyzeRequest(content)
                body = content[self._currentRequestInfo.getBodyOffset():].tostring()
                parsed_body = self.parseGraphQLBody(body)
                self._editor.setMessage(self._helpers.stringToBytes(parsed_body), isRequest)
            else:
                self._editor.setMessage(None, isRequest)

    def parseGraphQLBody(self, body):
        parsed_output = []

        if "fb_api_req_friendly_name" in body:
            parsed_output.append("fb_api_req_friendly_name: " +
                                 self.extractValue(body, "fb_api_req_friendly_name"))

        if "variables" in body:
            variables = self.extractValue(body, "variables")
            decoded_variables = unquote(variables)
            try:
                pretty_json = json.dumps(json.loads(decoded_variables), indent=4, ensure_ascii=False)
                parsed_output.append("variables:\n" + pretty_json)
            except:
                parsed_output.append("variables (raw): " + decoded_variables)

        if "doc_id" in body:
            parsed_output.append("doc_id: " + self.extractValue(body, "doc_id"))

        return "\n".join(parsed_output)

    def extractValue(self, body, key):
        start = body.find(key) + len(key) + 1
        end = body.find("&", start)
        if end == -1:
            end = len(body)
        return body[start:end]

    def scanRequest(self, event):
        if self._currentMessage is not None and self._currentRequestInfo is not None:
            try:
                modified_body = self._editor.getMessage()
                headers = self._currentRequestInfo.getHeaders()
                new_request = self._helpers.buildHttpMessage(headers, modified_body)
                http_service = self._currentMessage.getHttpService()
                response = self._extender._callbacks.makeHttpRequest(http_service, new_request)
                self.displayResponse(response)
            except:
                pass

    def displayResponse(self, response):
        if self._responseTab is None:
            self._responseTab = self._extender._callbacks.createMessageEditor(None, False)
            self._responsePanel = JPanel()
            self._responsePanel.setLayout(BoxLayout(self._responsePanel, BoxLayout.Y_AXIS))
            self._responsePanel.add(self._responseTab.getComponent())
            self._tabbedPane = JTabbedPane()
            self._tabbedPane.addTab("Meta GraphQL", self._panel)
            self._tabbedPane.addTab("GraphQL Response", self._responsePanel)
            self._panel.getParent().add(self._tabbedPane)
            self._panel.getParent().revalidate()

        self._responseTab.setMessage(response.getResponse(), False)

    def getMessage(self):
        return self._editor.getMessage()

    def isModified(self):
        return self._editor.isTextModified()

    def getSelectedData(self):
        return self._editor.getSelectedData()
