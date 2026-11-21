# Offline installation

Servers inside a customer's network have no internet access. This page
describes how to install the heavy benchmarks — garak, PyRIT, AgentDojo,
promptfoo — on such a machine.

The application itself, its datasets and the dashboard image need no internet.
Only these four tools do.

## How it works

You build a bundle once on a machine **with** internet, carry it over, and
install from it. Two environment facts decide what the bundle must contain:

| Fact | Why it matters |
|------|----------------|
| Target OS | Wheels for Windows will not install on Linux and vice versa |
| Python version | Wheels are built per minor version; target is **3.12** |

The bundle records both, plus a SHA256 for every file.

## Building the bundle

On a machine with internet and the repository checked out:

```bash
# Linux target
python scripts/build_offline_bundle.py --platform linux

# Windows target
python scripts/build_offline_bundle.py --platform windows

# A subset, to keep it small
python scripts/build_offline_bundle.py --platform linux --tools garak promptfoo
```

Result:

```
offline-bundle/
├── wheels/       Python wheels for the target platform
├── sources/      archives of tools installed from git (garak, pyrit, agentdojo)
├── npm/          promptfoo tarball
├── MANIFEST.json platform, versions, SHA256 per file
├── SHA256SUMS    for `sha256sum -c`
└── README.txt    short instructions to ship with it
```

Expected size: **~515 MB for Linux**, ~720 MB if you also ship the Windows
PyRIT variant. Almost all of it is `torch`, about 514 MB uncompressed.

## Installing at the customer

```bash
export CYBRA_OFFLINE_DIR=/opt/cybra/offline-bundle
cybra setup --tools garak pyrit agentdojo promptfoo
```

With `CYBRA_OFFLINE_DIR` set, installation uses `--no-index` and reads only
from the bundle. If a package is missing there, the install fails immediately
and says so, instead of hanging on a network timeout.

Before installing, verify integrity:

```bash
cd /opt/cybra/offline-bundle
sha256sum -c SHA256SUMS
```

## Requirements on the target machine

- **glibc 2.28 or newer** for Linux — Debian 10+, Ubuntu 20.04+, RHEL 8+.
  Check with `ldd --version`. Older systems are not supported: current numpy
  and torch publishes no wheels for them.
- **Python 3.12** for the host process. The bundle wheels are built for cp312.
- **Node.js 22+** if the deployment needs promptfoo.
- `uv` installed (`pip install uv`) — `cybra setup` uses it to create
  per-tool environments.

## Verifying that it really works offline

This step is not optional. A machine where the packages are already in the
pip cache will "work" without any bundle, and the check proves nothing.

1. Take a clean machine, VM or container.
2. Disable networking completely — `ip link set eth0 down`, or no interface
   at all. Not just a proxy setting.
3. Copy the bundle over, run `sha256sum -c`, then `cybra setup`.
4. Run a benchmark to the end.
5. Confirm nothing tried to reach out: `cybra setup` output and the tool logs
   should contain no connection errors.

## Known limitations

- Bundles are **per platform and per Python version**. One bundle does not
  cover both Linux and Windows; build two.
- The `sources/` archives are for tools installed from git. If a deployment
  needs newer versions, rebuild the bundle rather than patching it in place.
- Wheels are pinned by `locks/*.txt`. Changing a version means rebuilding.
- A self-hosted repository (devpi for Python, Verdaccio for npm) is a better
  fit than files if you deploy to many machines and update often. Files suit
  one-off installs.
