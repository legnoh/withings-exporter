import logging,os,sys,urllib,webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from withings_api import WithingsAuth, AuthScope

hostName = "localhost"
serverPort = 8000

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s : %(message)s', datefmt="%Y-%m-%dT%H:%M:%S%z")

auth = WithingsAuth(
    client_id=os.environ['WITHINGS_CLIENT_ID'],
    consumer_secret=os.environ['WITHINGS_CONSUMER_SECRET'],
    callback_uri= "http://{host}:{port}/".format(host=hostName, port=serverPort),
    scope=(
        AuthScope.USER_ACTIVITY,
        AuthScope.USER_METRICS,
        AuthScope.USER_INFO,
        AuthScope.USER_SLEEP_EVENTS,
    )
)

class MyServer(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path.startswith("/?code="):
            req = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(req.query)
            credentials = auth.get_credentials(query['code'][0])
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(bytes("<html><head><title>OK</title></head>", "utf-8"))
            self.wfile.write(bytes("<body>", "utf-8"))
            self.wfile.write(bytes("<p>Please paste it to your .env file.</p>", "utf-8"))
            self.wfile.write(bytes("<p>WITHINGS_ACCESS_TOKEN=%s<br>" % credentials.access_token, "utf-8"))
            self.wfile.write(bytes("WITHINGS_TOKEN_TYPE=%s<br>" % credentials.token_type, "utf-8"))
            self.wfile.write(bytes("WITHINGS_REFRESH_TOKEN=%s<br>" % credentials.refresh_token, "utf-8"))
            self.wfile.write(bytes("WITHINGS_USERID=%s<br>" % credentials.userid, "utf-8"))
            self.wfile.write(bytes("WITHINGS_EXPIRES_IN=%s<br>" % credentials.expires_in, "utf-8"))
            self.wfile.write(bytes("WITHINGS_CREATED=%s</p>" % credentials.created, "utf-8"))
            self.wfile.write(bytes("</body></html>", "utf-8"))
            sys.exit(0)

if __name__ == "__main__":
    authorize_url = auth.get_authorize_url()
    logger.info("------\nURL: {url}\n------".format(url=authorize_url))
    webbrowser.open(authorize_url)

    webServer = HTTPServer((hostName, serverPort), MyServer)
    try:
        webServer.serve_forever()
    except SystemExit:
        pass

    webServer.server_close()
    logger.info("Create Token Successfully!")
