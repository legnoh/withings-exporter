import logging
import os
import secrets
import threading
import urllib
from http.server import BaseHTTPRequestHandler, HTTPServer

from withings import WithingsClient

HOSTNAME = "localhost"
PORT = int(os.environ.get("WITHINGS_CALLBACK_PORT", "8000"))
DEFAULT_SCOPES = (
    "user.activity",
    "user.metrics",
    "user.info",
    "user.sleepevents",
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

callback_uri = os.environ.get("WITHINGS_REDIRECT_URI", f"http://{HOSTNAME}:{PORT}/")
auth = None
state = None
scope = ()


def initialize_auth():
    client = WithingsClient(
        client_id=os.environ['WITHINGS_CLIENT_ID'],
        client_secret=os.environ['WITHINGS_CONSUMER_SECRET'],
        redirect_uri=callback_uri,
    )
    auth_state = secrets.token_urlsafe(24)
    auth_scope = tuple(
        part.strip()
        for part in os.environ.get("WITHINGS_SCOPE", ",".join(DEFAULT_SCOPES)).split(",")
        if part.strip()
    )
    return client, auth_state, auth_scope

class MyServer(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path.startswith("/?"):
            req = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(req.query)
            if query.get("state", [None])[0] != state:
                self.send_error(400, "invalid state")
                return

            code = query.get("code", [None])[0]
            if not code:
                self.send_error(400, "authorization code is missing")
                return

            credentials = auth.request_access_token(code)
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(bytes("<html><head><title>OK</title></head>", "utf-8"))
            self.wfile.write(bytes("<body>", "utf-8"))
            self.wfile.write(bytes("<p>Please paste it to your .env file.</p>", "utf-8"))
            self.wfile.write(bytes("<p>WITHINGS_CLIENT_ID=%s<br>" % os.environ['WITHINGS_CLIENT_ID'], "utf-8"))
            self.wfile.write(bytes("WITHINGS_CONSUMER_SECRET=%s<br>" % os.environ['WITHINGS_CONSUMER_SECRET'], "utf-8"))
            self.wfile.write(bytes("WITHINGS_ACCESS_TOKEN=%s<br>" % credentials.access_token, "utf-8"))
            self.wfile.write(bytes("WITHINGS_TOKEN_TYPE=%s<br>" % credentials.token_type, "utf-8"))
            self.wfile.write(bytes("WITHINGS_REFRESH_TOKEN=%s<br>" % credentials.refresh_token, "utf-8"))
            self.wfile.write(bytes("WITHINGS_USERID=%s<br>" % credentials.userid, "utf-8"))
            self.wfile.write(bytes("WITHINGS_EXPIRES_IN=%s<br>" % credentials.expires_in, "utf-8"))
            self.wfile.write(bytes("WITHINGS_SCOPE=%s<br>" % credentials.scope, "utf-8"))
            self.wfile.write(bytes("WITHINGS_CREATED=%s<br>" % credentials.obtained_at.isoformat(), "utf-8"))
            self.wfile.write(bytes("TZ=Your/Timezone</p>", "utf-8"))
            self.wfile.write(bytes("</body></html>", "utf-8"))
            threading.Thread(target=self.server.shutdown, daemon=True).start()

if __name__ == "__main__":
    auth, state, scope = initialize_auth()
    authorize_url = auth.build_authorization_url(scope, state)
    logger.info(f"Open URL and approve it:\n\n{authorize_url}\n\n")

    webServer = HTTPServer(('', PORT), MyServer)
    try:
        webServer.serve_forever()
    finally:
        webServer.server_close()
        logger.info("Create Token Successfully!")
