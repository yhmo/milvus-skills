#!/usr/bin/env python3
"""Run the cpp snippets of a user-guide page against a live Milvus server using a
prebuilt milvus-sdk-cpp binary.

Two sources are tried, in order:
1. the `default-conan-local2` Conan repo
   (`conan install --requires="milvus-sdk-cpp/<ver>@milvus/dev" --build=never`),
   then
2. the **GitHub releases** page of `milvus-io/milvus-sdk-cpp`
   (https://github.com/milvus-io/milvus-sdk-cpp/releases/tag/v<ver>). The
   release **Assets** carry prebuilt binary packages for each platform
   (`libmilvus-<ver>-<arch>-<OS>.[deb|rpm|tar.gz]`); the matching asset for the
   current platform is downloaded and extracted, and its `include/` + `lib/`
   are used.

If neither source provides a usable binary, cpp verification is SKIPPED
(reported, not failed — never a from-source build).

Optionally pre-checks API calls against the per-tag SDK index (see
gen_api_index.py / api_index.py): pass --api-index DIR --sdk-tag cpp@TAG to
pin the requested version to TAG and report unknown SDK calls before compiling.

Usage: python3 run_page_cpp.py <page.md> [<version>] [--api-index DIR --sdk-tag cpp@TAG]
"""
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
PROJ = os.path.join(REPO, "sdk-tmp", "snippet-run", "cpp")
DEPLOY = os.path.join(PROJ, "deploy")       # conan full_deploy output
GH_DEPLOY = os.path.join(PROJ, "gh-deploy")  # github release extraction output
REMOTE = "default-conan-local2"
CONAN_HOME = os.environ.get("CONAN_HOME", os.path.join(os.path.expanduser("~"), "work", ".conan2"))

GH_REPO = "milvus-io/milvus-sdk-cpp"
GH_API = f"https://api.github.com/repos/{GH_REPO}/releases"
GH_DL_BASE = f"https://github.com/{GH_REPO}/releases/download"
GH_UA = "milvus-user-guide-snippet-runner/1.0"


def install_prebuilt(version):
    """Try to fetch a prebuilt milvus-sdk-cpp/<version> binary from Conan.
    Return True on success. The published binaries are built with cppstd=14 —
    match that setting."""
    attempts = [
        ["-s", "compiler.cppstd=14"],
        ["-s", "compiler.version=11", "-s", "compiler.cppstd=14"],
        ["-s", "compiler.version=12", "-s", "compiler.cppstd=14", "-s", "build_type=Release"],
    ]
    for extra in attempts:
        cmd = ["conan", "install", f"--requires=milvus-sdk-cpp/{version}@milvus/dev",
               "--build=never", f"--deployer=full_deploy",
               f"--output-folder={DEPLOY}"] + extra
        r = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, "CONAN_HOME": CONAN_HOME})
        if r.returncode == 0 and os.path.isdir(os.path.join(DEPLOY, "include")) and os.path.isdir(os.path.join(DEPLOY, "lib")):
            return True
    return False


def latest_remote_version():
    """Query the Conan remote for the newest milvus-sdk-cpp version."""
    r = subprocess.run(["conan", "search", "milvus-sdk-cpp/*", "-r", REMOTE],
                       capture_output=True, text=True, env={**os.environ, "CONAN_HOME": CONAN_HOME})
    vers = re.findall(r"milvus-sdk-cpp/([0-9]+\.[0-9]+\.[0-9]+)@milvus/dev", r.stdout)
    vers.sort(key=lambda v: [int(x) for x in v.split(".")])
    return vers[-1] if vers else None


def _gh_api(path):
    """Query the GitHub API, preferring the authenticated `gh` CLI when
    available (avoids anonymous rate limits), else falling back to urllib."""
    if shutil.which("gh"):
        r = subprocess.run(["gh", "api", f"repos/{GH_REPO}/releases/{path}",
                            "--jq", "."], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout)
    req = urllib.request.Request(f"{GH_API}/{path}", headers={"User-Agent": GH_UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def latest_github_version():
    """Query GitHub for the newest released milvus-sdk-cpp version."""
    try:
        data = _gh_api("latest")
        return data["tag_name"].lstrip("v")
    except Exception:
        return None


def github_assets(version):
    """Return the asset filenames of the release for `version`."""
    data = _gh_api(f"tags/v{version}")
    return [a["name"] for a in data.get("assets", [])]


def linux_distro():
    """Return (ID, VERSION_ID) from /etc/os-release, e.g. ('ubuntu', '22.04')."""
    info = {}
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if "=" in line:
                    k, _, v = line.partition("=")
                    info[k.strip()] = v.strip().strip('"')
    except OSError:
        pass
    return info.get("ID", ""), info.get("VERSION_ID", "")


def asset_score(name, sysname, arch):
    """Score how well a release asset name matches the current platform.
    Return an int preference score, or None if it does not match at all."""
    n = name.lower()
    if not n.startswith("libmilvus-"):
        return None
    if sysname == "linux":
        if "ubuntu" not in n and "fedora" not in n:
            return None
        if arch in ("x86_64", "amd64"):
            if "x86_64" not in n and "amd64" not in n:
                return None
        elif arch in ("aarch64", "arm64"):
            if "aarch64" not in n and "arm64" not in n:
                return None
        else:
            return None
        distro_id, ver_id = linux_distro()
        score = 10
        if distro_id == "ubuntu" and "ubuntu" in n:
            score += 20
            if ver_id and ver_id in n:  # e.g. "22.04" inside "ubuntu_22.04.deb"
                score += 30
        elif distro_id == "fedora" and "fedora" in n:
            score += 20
        return score
    if sysname == "darwin":
        if "macos" not in n:
            return None
        if arch in ("x86_64",):
            if "x86_64" not in n:
                return None
        elif arch in ("arm64", "aarch64"):
            if "arm64" not in n and "aarch64" not in n:
                return None
        else:
            return None
        return 10
    if sysname == "windows":
        if "windows" not in n:
            return None
        if arch in ("x86_64", "amd64"):
            if "amd64" not in n and "x86_64" not in n:
                return None
        return 10
    return None


def _extract_deb(pkg, dest):
    if not shutil.which("dpkg-deb"):
        return None
    r = subprocess.run(["dpkg-deb", "-x", pkg, dest], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    inc = os.path.join(dest, "usr", "include")
    lib = os.path.join(dest, "usr", "lib")
    return (inc, lib) if os.path.isdir(inc) else None


def _extract_rpm(pkg, dest):
    if not shutil.which("rpm2cpio") or not shutil.which("cpio"):
        return None
    pipe = subprocess.run(["rpm2cpio", pkg], capture_output=True)
    if pipe.returncode != 0:
        return None
    r = subprocess.run(["cpio", "-idmv", "-D", dest], input=pipe.stdout,
                       capture_output=True, text=False)
    if r.returncode != 0:
        return None
    inc = os.path.join(dest, "usr", "include")
    lib = os.path.join(dest, "usr", "lib64") or os.path.join(dest, "usr", "lib")
    for cand in (os.path.join(dest, "usr", "lib64"), os.path.join(dest, "usr", "lib")):
        if os.path.isdir(cand):
            lib = cand
            break
    return (inc, lib) if os.path.isdir(inc) else None


def _extract_targz(pkg, dest):
    r = subprocess.run(["tar", "-xzf", pkg, "-C", dest], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    top = next((d for d in os.listdir(dest) if os.path.isdir(os.path.join(dest, d))), None)
    if not top:
        return None
    base = os.path.join(dest, top)
    inc = os.path.join(base, "include")
    lib = None
    for cand in (os.path.join(base, "lib"), os.path.join(base, "bin")):
        if os.path.isdir(cand):
            lib = cand
            break
    return (inc, lib) if (os.path.isdir(inc) and lib) else None


def install_github_release(version):
    """Download and extract the platform-matching binary from GitHub releases.
    Return (include_dir, lib_dir) on success, else None."""
    try:
        assets = github_assets(version)
    except Exception as e:
        print(f"cpp: could not query GitHub release assets for v{version} ({e})")
        return None
    if not assets:
        print(f"cpp: GitHub release v{version} has no assets")
        return None

    sysname = platform.system().lower()
    arch = platform.machine().lower()
    scored = sorted(((asset_score(n, sysname, arch) or 0, n) for n in assets),
                    key=lambda x: -x[0])
    usable = [(s, n) for s, n in scored if s > 0]
    if not usable:
        print(f"cpp: no GitHub release asset for this platform ({sysname}/{arch}) "
              f"among: {assets}")
        return None

    shutil.rmtree(GH_DEPLOY, ignore_errors=True)
    os.makedirs(GH_DEPLOY, exist_ok=True)
    for _score, name in usable:
        url = f"{GH_DL_BASE}/v{version}/{name}"
        local = os.path.join(GH_DEPLOY, name)
        print(f"cpp: downloading {url}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": GH_UA})
            with urllib.request.urlopen(req, timeout=120) as resp, open(local, "wb") as f:
                shutil.copyfileobj(resp, f)
        except Exception as e:
            print(f"cpp: download failed for {name} ({e})")
            continue
        dest = os.path.join(GH_DEPLOY, "pkg")
        shutil.rmtree(dest, ignore_errors=True)
        os.makedirs(dest, exist_ok=True)
        extracted = None
        if name.endswith(".deb"):
            extracted = _extract_deb(local, dest)
        elif name.endswith(".rpm"):
            extracted = _extract_rpm(local, dest)
        elif name.endswith(".tar.gz"):
            extracted = _extract_targz(local, dest)
        if extracted:
            return extracted
        print(f"cpp: could not extract {name} (missing extractor or bad layout)")
    return None


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--api-index", default="")
    ap.add_argument("--sdk-tag", default="")
    args, rest = ap.parse_known_args(sys.argv[1:])
    page = rest[0]

    version = args.sdk_tag.partition("@")[2].lstrip("v") if args.sdk_tag else \
        (rest[1] if len(rest) > 1 else None)
    if not version:
        if shutil.which("conan"):
            version = latest_remote_version()
        if not version:
            try:
                version = latest_github_version()
            except Exception as e:
                print(f"cpp: could not resolve milvus-sdk-cpp version from Conan "
                      f"or GitHub ({e}) — SKIPPING cpp verification")
                sys.exit(0)
    if not version:
        print("cpp: no milvus-sdk-cpp version available — SKIPPING cpp verification")
        sys.exit(0)

    inc = lib = None
    src_note = ""
    if shutil.which("conan") and install_prebuilt(version):
        inc = os.path.join(DEPLOY, "include")
        lib = os.path.join(DEPLOY, "lib")
        src_note = f"prebuilt milvus-sdk-cpp/{version} from {REMOTE}"
    else:
        gh = install_github_release(version)
        if gh:
            inc, lib = gh
            src_note = f"milvus-sdk-cpp/{version} from GitHub releases"

    if not (inc and os.path.isdir(inc)):
        print(f"cpp: no prebuilt milvus-sdk-cpp/{version} binary on {REMOTE} or "
              f"GitHub releases for this system — SKIPPING cpp verification")
        sys.exit(0)
    print(f"cpp: using {src_note}")

    md = open(page).read()
    blocks = re.findall(r"```cpp\n(.*?)```", md, re.S)

    # API-existence pre-check (soft)
    if args.api_index and args.sdk_tag:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import api_index as ai
        sdk, _, tag = args.sdk_tag.partition("@")
        idx = ai.resolve_index(sdk, tag, args.api_index)
        if idx:
            print(f"cpp: API index {idx}")
            for i, b in enumerate(blocks):
                unknown = ai.check_code(idx, "cpp", b, sdk)
                if unknown:
                    print(f"cpp: block {i}: {len(unknown)} unknown SDK call(s)")
                    for expr, sym in unknown[:10]:
                        print(f"      {sym}  (from {expr!r})")
        else:
            print(f"cpp: WARN no API index for {sdk}@{tag} — skipping API pre-check")

    # assemble: hoist includes, strip per-block client init, wrap block bodies
    # in scoped braces, and create one shared client in main() so blocks that
    # each start with `auto client = MilvusClientV2::Create();` do not clash.
    includes = []
    bodies = []
    for b in blocks:
        kept = []
        for line in b.split("\n"):
            if line.strip().startswith("#include"):
                includes.append(line.strip())
                continue
            kept.append(line)
        bodies.append("\n".join(kept))
    includes = list(dict.fromkeys(includes))
    cleaned = []
    for b in bodies:
        b = re.sub(
            r"auto\s+client\s*=\s*(?:milvus::)?MilvusClientV2::Create\(\s*\);",
            "", b)
        b = re.sub(
            r"util::CheckStatus\(\s*client->Connect\(\s*ConnectParam\([^)]*\)\.WithToken\([^)]*\)\s*\)\s*\)\s*;",
            "", b, flags=re.S)
        cleaned.append(b)
    bodies = cleaned
    prog = "\n".join(includes) + "\n\nint main() {\n"
    prog += '    auto client = milvus::MilvusClientV2::Create();\n'
    prog += '    auto status = client->Connect(milvus::ConnectParam("http://localhost:19530").WithToken("root:Milvus"));\n'
    prog += '    if (!status.IsOk()) { return 1; }\n'
    for i, b in enumerate(bodies):
        prog += f"    // === block {i} ===\n    {{\n"
        prog += "\n".join("        " + ln for ln in b.split("\n")) + "\n"
        prog += "    }\n"
    prog += "    return 0;\n}\n"

    os.makedirs(PROJ, exist_ok=True)
    src = os.path.join(PROJ, "run_page.cpp")
    out = os.path.join(PROJ, "a.out")
    with open(src, "w") as f:
        f.write(prog)

    # link against the deployed library (find the milvus .so/.dylib/.a)
    if not shutil.which("g++"):
        print("cpp: g++ not installed — SKIPPING cpp verification")
        sys.exit(0)
    if not os.path.isdir(lib):
        print("cpp: deployed package has no lib/ dir — skipping cpp verification")
        sys.exit(0)
    libs = [f for f in os.listdir(lib)
            if re.match(r"libmilvus.*\.(so|dylib|a)(\.\d+)*$", f)]
    if not libs:
        print(f"cpp: no libmilvus* library found in {lib} — skipping cpp verification")
        sys.exit(0)
    m = re.match(r"lib(.+?)\.(so|dylib|a)", libs[0])
    link = f"-L{lib} -l{m.group(1)}" if m else ""
    print(f"cpp blocks: {len(blocks)}")
    c = subprocess.run(["g++", "-std=c++14", "-o", out, src, f"-I{inc}"] + (link.split() if link else []),
                       capture_output=True, text=True, cwd=PROJ)
    if c.returncode != 0:
        sys.stderr.write(c.stderr[-3000:])
        print(f"\n=== {page} === cpp compile FAILED ({len(blocks)} blocks)")
        sys.exit(1)
    env = dict(os.environ)
    # make the shared library findable at run time (so for unix, dylib for macOS)
    for var in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        env[var] = lib + (os.pathsep + env[var] if env.get(var) else "")
    r = subprocess.run([out], capture_output=True, text=True, env=env)
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr[-3000:] if r.returncode else "")
    print(f"\n=== {page} === cpp run {'OK' if r.returncode == 0 else 'FAILED'} ({len(blocks)} blocks)")
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
