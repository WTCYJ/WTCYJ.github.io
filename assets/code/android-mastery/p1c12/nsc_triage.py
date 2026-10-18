"""Effective Network Security Config of an app, one row per config, the way the platform resolves it.

usage: python nsc_triage.py APP.apk ... [--today YYYY-MM-DD]
Each APP.apk needs its apktool output next to it (apktool d -s APP.apk -o APP). The NSC and manifest
come from that folder; the APK itself is only scanned for classes that bring their own trust decisions.
Rules follow frameworks/base core/java/android/security/net/config (XmlConfigSource, NetworkSecurityConfig).
"""
import datetime, re, struct, sys, zipfile
import xml.etree.ElementTree as ET

A = "{http://schemas.android.com/apk/res/android}"


def parse(el, parent, kind, nodes):
    n = dict(kind=kind, parent=parent, domains=[], anchors=None, pins=None, exp=None,
             cleartext=el.get("cleartextTrafficPermitted"))
    nodes.append(n)
    for c in el:
        if c.tag == "domain":
            n["domains"].append(c.text.strip() + ("/*" if c.get("includeSubdomains") == "true" else ""))
        elif c.tag == "trust-anchors":   # overridePins defaults to true only inside debug-overrides
            n["anchors"] = [(x.get("src"), x.get("overridePins", str(kind == "debug").lower()) == "true")
                            for x in c if x.tag == "certificates"]
        elif c.tag == "pin-set":
            n["pins"], n["exp"] = [p.text.strip() for p in c if p.tag == "pin"], c.get("expiration")
        elif c.tag == "domain-config":
            parse(c, n, "domain", nodes)
    return n


def inherit(n, key):
    while n[key] is None and n["parent"]:
        n = n["parent"]
    return n[key], n


def triage(apk, today):
    d = apk[:-4]
    app = ET.parse(f"{d}/AndroidManifest.xml").getroot().find("application")
    sdk = int(re.search(r"targetSdkVersion:\s*'?(\d+)", open(f"{d}/apktool.yml", encoding="utf-8").read()).group(1))
    debuggable, res = app.get(A + "debuggable") == "true", app.get(A + "networkSecurityConfig")
    uct = app.get(A + "usesCleartextTraffic")
    print(f"== {d}  targetSdk={sdk} debuggable={str(debuggable).lower()} networkSecurityConfig={res or '-'}"
          + (f" usesCleartextTraffic={uct}" if uct else ""))
    # platform default: cleartext only below API 28, user CAs only up to API 23
    platform = dict(kind="platform", parent=None, domains=[], pins=None, exp=None,
                    cleartext=str(sdk < 28).lower(),
                    anchors=[("system", False)] + ([("user", False)] if sdk <= 23 else []))
    nodes, debug = [], None
    if res:
        root = ET.parse(f"{d}/res/xml/{res.split('/')[1]}.xml").getroot()
        base = next((parse(e, platform, "base", nodes) for e in root if e.tag == "base-config"), platform)
        for e in root:
            if e.tag == "domain-config":
                parse(e, base, "domain", nodes)
            elif e.tag == "debug-overrides":
                debug = parse(e, None, "debug", [])
        if not any(n["kind"] == "base" for n in nodes):
            nodes.insert(0, platform)
    else:   # no NSC: android:usesCleartextTraffic (default: targetSdk < 28) decides cleartext
        platform["cleartext"] = uct or platform["cleartext"]
        nodes = [platform]
    extra = (debug["anchors"] or []) if debug and debuggable else []
    print(f"  {'scope':<24}{'cleartext':<10}{'trust anchors (+ = overridePins)':<34}pins")
    for n in nodes:
        scope = ", ".join(n["domains"]) or {"platform": "(platform default)", "base": "base-config"}[n["kind"]]
        clear, src = inherit(n, "cleartext")
        anchors = inherit(n, "anchors")[0] + extra
        pins, pin_src = inherit(n, "pins")
        pinv = "-"
        if pins:
            exp = pin_src["exp"]
            pinv = f"{len(pins)} pin{'s' if len(pins) > 1 else ''}, " + ("no expiration" if not exp else
                   f"expired {exp} -> NOT checked" if today >= datetime.date.fromisoformat(exp) else f"until {exp}")
        a = ", ".join(s + ("+" if o else "") for s, o in anchors) or "(none)"
        print(f"  {scope:<24}{clear + ('' if src is n else '*'):<10}{a:<34}{pinv}")
    if debug:
        state = "applied" if debuggable else "ignored (not debuggable)"
        print(f"  debug-overrides: {state}" + (", its cleartextTrafficPermitted is never used"
                                                if debug["cleartext"] else ""))
    print("  * = inherited" + code_hints(apk))


STACKS = {"Lokhttp3/": "okhttp3", "Lcom/squareup/okhttp/": "okhttp2", "Lorg/chromium/net/": "cronet",
          "Lcom/android/volley/": "volley"}


def code_hints(apk):
    """Code that makes its own TLS decisions (TrustManager, HostnameVerifier, code pins, WebView SSL errors)."""
    want = {"Ljavax/net/ssl/X509TrustManager;", "Ljavax/net/ssl/X509ExtendedTrustManager;",
            "Ljavax/net/ssl/HostnameVerifier;"}
    found, stacks, code_pins, ssl_err = set(), set(), set(), set()
    with zipfile.ZipFile(apk) as z:
        libs = sorted({n.rsplit("/", 1)[1] for n in z.namelist()
                       if n.startswith("lib/") and re.search(r"lib(flutter|cronet|ssl|crypto|curl)", n)})
        for name in z.namelist():
            if re.fullmatch(r"classes\d*\.dex", name):
                classes, strings, methods = dex_scan(z.read(name))
                ssl_err |= {c for c, m in methods if m == "onReceivedSslError" and not c.startswith("Landroid")}
                code_pins |= {s for s in strings if re.fullmatch(r"sha256/[A-Za-z0-9+/]{43}=", s)}
                for cls, sup_ifaces in classes:
                    lib = next((v for k, v in STACKS.items() if cls.startswith(k)), None)
                    if lib:
                        stacks.add(lib)
                    elif want & sup_ifaces:
                        found.add(cls[1:-1].replace("/", "."))
    out = ""
    if stacks or libs:
        out += "\n  stacks: " + ", ".join(sorted(stacks) + libs)
    for c in sorted(found)[:6]:
        out += "\n  own trust code: " + c
    if code_pins:
        out += f"\n  pins in code (sha256/... strings, OkHttp CertificatePinner style): {len(code_pins)}"
    for c in sorted(ssl_err)[:3]:
        out += "\n  WebView onReceivedSslError overridden: " + c[1:-1].replace("/", ".")
    return out


def dex_scan(b):
    """(class, {superclass, interfaces...}) per class_def, all strings, (class, name) per method_id."""
    n_str, sid_off = struct.unpack_from("<II", b, 0x38)
    tid_off = struct.unpack_from("<I", b, 0x44)[0]
    n_cls, cls_off = struct.unpack_from("<II", b, 0x60)

    def string(i):
        off = struct.unpack_from("<I", b, sid_off + 4 * i)[0]
        while b[off] & 0x80:   # skip the uleb128 utf16 length
            off += 1
        return b[off + 1:b.index(0, off + 1)].decode("utf-8", "replace")

    def typ(i):
        return string(struct.unpack_from("<I", b, tid_off + 4 * i)[0])

    classes = []
    for k in range(n_cls):
        c, _, sup, ifs = struct.unpack_from("<IIII", b, cls_off + 32 * k)
        rel = {typ(sup)} if sup != 0xFFFFFFFF else set()
        if ifs:
            rel |= {typ(struct.unpack_from("<H", b, ifs + 4 + 2 * j)[0])
                    for j in range(struct.unpack_from("<I", b, ifs)[0])}
        classes.append((typ(c), rel))
    n_m, m_off = struct.unpack_from("<II", b, 0x58)
    methods = [(typ(struct.unpack_from("<H", b, m_off + 8 * k)[0]),
                string(struct.unpack_from("<I", b, m_off + 8 * k + 4)[0])) for k in range(n_m)]
    return classes, [string(i) for i in range(n_str)], methods


if __name__ == "__main__":
    args = sys.argv[1:]
    today = datetime.date.today()
    if "--today" in args:
        i = args.index("--today")
        today = datetime.date.fromisoformat(args[i + 1])
        del args[i:i + 2]
    print(f"today = {today}")
    for apk in args:
        triage(apk, today)
