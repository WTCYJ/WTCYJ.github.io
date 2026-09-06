import http.server, urllib.parse, json, hashlib, base64, secrets, time

REGISTERED_REDIRECT = "aasoauth://cb"      # 등록된 redirect_uri (정확 일치만 허용)
CLIENT_ID = "aas-client"
codes = {}   # code -> {challenge, state, redirect_uri}

def b64url(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

class H(http.server.BaseHTTPRequestHandler):
    def _json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        if u.path == "/authorize":
            # redirect_uri 정확 일치 검증
            if q.get("redirect_uri") != REGISTERED_REDIRECT:
                return self._json({"error": "invalid_redirect_uri",
                                   "given": q.get("redirect_uri")}, 400)
            if q.get("client_id") != CLIENT_ID:
                return self._json({"error": "invalid_client"}, 400)
            if q.get("code_challenge_method") != "S256" or not q.get("code_challenge"):
                return self._json({"error": "pkce_required"}, 400)
            code = secrets.token_urlsafe(16)
            codes[code] = {"challenge": q["code_challenge"],
                           "state": q.get("state"),
                           "redirect_uri": q["redirect_uri"]}
            # 실제로는 302 redirect. 데모 클라이언트는 이 JSON에서 code/state를 읽는다.
            return self._json({"redirect_to": q["redirect_uri"],
                               "code": code, "state": q.get("state")})
        self._json({"error": "not_found"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n).decode()
        q = dict(urllib.parse.parse_qsl(body))
        if self.path == "/token":
            code = q.get("code")
            rec = codes.get(code)
            if not rec:
                return self._json({"error": "invalid_grant", "reason": "unknown code"}, 400)
            if q.get("redirect_uri") != rec["redirect_uri"]:
                return self._json({"error": "invalid_grant", "reason": "redirect_uri mismatch"}, 400)
            # PKCE 검증: S256(code_verifier) == 저장된 challenge ?
            verifier = q.get("code_verifier", "")
            calc = b64url(hashlib.sha256(verifier.encode()).digest())
            if calc != rec["challenge"]:
                return self._json({"error": "invalid_grant",
                                   "reason": "PKCE verifier mismatch",
                                   "expected_challenge": rec["challenge"],
                                   "got_challenge": calc}, 400)
            del codes[code]  # code 1회용
            header = b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode())
            payload = b64url(json.dumps({"sub": "user-42", "name": "Test User",
                                         "iss": "aas-mock", "aud": CLIENT_ID,
                                         "iat": int(time.time())}).encode())
            id_token = header + "." + payload + "."
            return self._json({"access_token": "at_" + secrets.token_urlsafe(12),
                               "token_type": "Bearer", "expires_in": 3600,
                               "id_token": id_token})
        self._json({"error": "not_found"}, 404)

    def log_message(self, *a):
        pass

http.server.HTTPServer(("127.0.0.1", 8011), H).serve_forever()
