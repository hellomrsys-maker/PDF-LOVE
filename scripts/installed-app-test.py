#!/usr/bin/env python3
"""
Drive real work through the engine that ships inside the installed app.

Run against the sidecar unpacked from the built AppImage, not the one in
the source tree — the point is to test the artifact a user downloads,
including that it was bundled with its compiled extensions intact.

    python scripts/installed-app-test.py path/to/pdflove-engine
    python scripts/installed-app-test.py path/to/pdflove-engine --offline

With --offline the script additionally asserts it really has no route out,
so a pass cannot be an accident of the sandbox still having network. Meant
to be run inside `unshare -n`.
"""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request


def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


def bring_up_loopback():
    """A fresh network namespace starts with loopback DOWN.

    That would make even 127.0.0.1 unreachable and the test would fail for
    a reason that has nothing to do with the app. Done here rather than
    with `ip link set lo up` because iproute2 is not guaranteed to be
    installed on a minimal runner image.
    """
    import fcntl
    import struct
    SIOCGIFFLAGS, SIOCSIFFLAGS, IFF_UP = 0x8913, 0x8914, 0x1
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        flags = struct.unpack("16sh", fcntl.ioctl(
            s, SIOCGIFFLAGS, struct.pack("16sh", b"lo", 0)))[1]
        if not flags & IFF_UP:
            fcntl.ioctl(s, SIOCSIFFLAGS,
                        struct.pack("16sh", b"lo", flags | IFF_UP))
            print("  brought loopback up inside the namespace")
    except OSError as e:
        print(f"  note: could not adjust loopback ({e}); continuing")


def assert_no_network():
    """Prove there is genuinely no way out before claiming an offline pass."""
    try:
        socket.setdefaulttimeout(5)
        socket.getaddrinfo("cloudflare.com", 443)
    except socket.gaierror:
        print("  confirmed: DNS does not resolve, this really is offline")
        return
    except Exception as e:
        print(f"  confirmed: no network ({type(e).__name__})")
        return
    fail("--offline was requested but DNS still resolves; the namespace did "
         "not isolate the process, so an offline pass would prove nothing")


def build_inputs(tmp, count=3, pages=4):
    import pikepdf
    paths = []
    for i in range(count):
        p = os.path.join(tmp, f"in{i}.pdf")
        pdf = pikepdf.Pdf.new()
        for _ in range(pages):
            pdf.add_blank_page(page_size=(612, 792))
        pdf.save(p)
        pdf.close()
        paths.append(p)
    return paths


def main():
    engine = sys.argv[1]
    offline = "--offline" in sys.argv
    if offline:
        bring_up_loopback()
        assert_no_network()

    proc = subprocess.Popen([engine], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True)
    line = proc.stdout.readline().strip()
    if not line.startswith("DOCKBENCH_READY"):
        fail(f"engine did not announce itself: {line!r}\n"
             f"{proc.stderr.read()[:2000]}")
    _, port, token = line.split()
    print(f"  engine up on 127.0.0.1:{port}")
    time.sleep(2)

    def call(path, payload=None):
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
        req.add_header("Authorization", "Bearer " + token)
        if payload is not None:
            req.add_header("Content-Type", "application/json")
            req.data = json.dumps(payload).encode()
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    status, caps = call("/capabilities")
    if status != 200:
        fail(f"/capabilities returned {status}")
    print(f"  imgproc backend: {caps.get('imgproc_backend')}")
    if caps.get("imgproc_backend") != "extension":
        fail(f"the installed app fell back to {caps.get('imgproc_backend')} — "
             "the compiled kernel did not make it into the bundle")

    tmp = tempfile.mkdtemp(prefix="installed-test-")
    try:
        inputs = build_inputs(tmp)
        out = os.path.join(tmp, "merged.pdf")

        status, body = call("/local/process",
                            {"op": "merge", "inputs": inputs, "output": out})
        if status != 200:
            fail(f"merge failed ({status}): {body}")
        if body.get("pages") != 12:
            fail(f"merge wrote {body.get('pages')} pages, expected 12")
        import pikepdf
        with pikepdf.open(out) as pdf:
            if len(pdf.pages) != 12:
                fail(f"output has {len(pdf.pages)} pages on disk, expected 12")
        print(f"  merge: 3 files -> {body['pages']} pages, verified on disk")

        rng = os.path.join(tmp, "range.pdf")
        status, body = call("/local/process",
                            {"op": "extract", "inputs": [out], "output": rng,
                             "first": 2, "last": 5})
        if status != 200 or body.get("pages") != 4:
            fail(f"extract failed ({status}): {body}")
        print(f"  extract: pages 2-5 -> {body['pages']} pages")

        status, body = call("/local/process",
                            {"op": "rotate", "inputs": [out],
                             "output": os.path.join(tmp, "rot.pdf"), "angle": 90})
        if status != 200:
            fail(f"rotate failed ({status}): {body}")
        print(f"  rotate: {body['pages']} pages")

        # The part-splitting path, which is what keeps a large job inside a
        # memory ceiling. Verified here because it is new machinery and the
        # installed build is where it has to work.
        parts_out = os.path.join(tmp, "parted.pdf")
        status, body = call("/local/process",
                            {"op": "merge", "inputs": inputs * 4,
                             "output": parts_out, "max_pages_per_part": 8})
        if status != 200:
            fail(f"parted merge failed ({status}): {body}")
        produced = sorted(f for f in os.listdir(tmp) if f.startswith("parted-part"))
        if not produced:
            fail("max_pages_per_part produced no part files")
        print(f"  parted merge: {body['pages']} pages across {len(produced)} parts")
    finally:
        proc.stdin.close()
        time.sleep(1)
        if proc.poll() is None:
            proc.kill()

    where = "offline" if offline else "online"
    print(f"PASS: the installed app does real work {where}.")


if __name__ == "__main__":
    main()
