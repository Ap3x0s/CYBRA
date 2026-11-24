# Offline installation

Servers inside a customer's network have no internet access. This page
describes how to install the heavy benchmarks — garak, PyRIT, AgentDojo,
BIPIA, promptfoo — on such a machine.

The application itself, its datasets and the dashboard image need no internet.
Only these five tools do.

The *image* needs no internet, but getting it onto the box does. `docker pull`
cannot reach Docker Hub from an isolated network, so the image travels as a tar:

```bash
# on a machine with internet
docker pull ap3x0/cybra:latest
docker save ap3x0/cybra:latest -o cybra-image.tar

# on the air-gapped host
docker load -i cybra-image.tar
```

Both go on the same medium as the bundle.

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
PyRIT variant. Almost all of it is `torch`, about 514 MB uncompressed. With
every tool and the npm cache the figure reaches ~1.9 GB.

## Installing at the customer

```bash
export CYBRA_OFFLINE_DIR=/opt/cybra/offline-bundle
cybra setup --tools garak pyrit agentdojo bipia promptfoo
```

On Windows the variable is set differently — `export` is a POSIX shell builtin
and does not exist in `cmd.exe` or PowerShell:

```powershell
$env:CYBRA_OFFLINE_DIR = 'D:\cybra\offline-bundle'   # PowerShell
```

```cmd
set CYBRA_OFFLINE_DIR=D:\cybra\offline-bundle        :: cmd.exe
```

Either way it applies to the current session only. `setx` would persist it, but
it also leaks into every later process, which is rarely what you want for a
one-off install.

With `CYBRA_OFFLINE_DIR` set, no network is used:

| What | How it is installed offline |
|------|------------------------------|
| Python packages | `--no-index --find-links=<bundle>/wheels` |
| garak, PyRIT, AgentDojo | git lines in `locks/*.txt` are rewritten to the local archives in `<bundle>/sources` |
| BIPIA | 28 wheels from `locks/bipia.txt`, installed into the main environment |
| promptfoo | `npm ci --offline --cache=<bundle>/npm` |

Both spellings of the command work; the flag is the one used everywhere in
the UI and the docs:

```bash
cybra setup --tools garak pyrit    # explicit flag
cybra setup garak pyrit            # same, positional
cybra setup                        # garak, PyRIT, AgentDojo, promptfoo
```

Note the last line: a bare `cybra setup` installs four tools, **not** BIPIA.
BIPIA is the one tool that must be named explicitly:

```bash
cybra setup --tools bipia
```

Setup prints the mode before it starts, so you can see at a glance whether it
will reach the network:

```
Режим: офлайн
  bundle : /opt/cybra/offline-bundle
  колёс  : 184
  архивов: 3
  npm    : есть
  сеть не используется
```

Without `CYBRA_OFFLINE_DIR` it prints `Режим: онлайн (PyPI + npm)` — which is
the signal that a machine with no internet will hang on timeouts.

The second row is easy to miss and worth stating plainly. `garak` is pinned in
its lock file as a git URL:

```
garak @ git+https://github.com/NVIDIA/garak.git@93aa9cdec309...
```

`--no-index` does **not** cover this: it restricts package lookup on an index,
while a git URL is handled by a separate mechanism that clones the repository.
Without rewriting, installation on an air-gapped host fails at that line even
though `sources/garak-*.tar.gz` sits right next to it.

`cybra setup` therefore rewrites those lines into a temporary
`<tool>.offline.txt` and installs from the local archives. If an archive is
missing from the bundle, the line is left untouched and the install fails
loudly — a partially installed tool that silently skips its target would be
worse than a clear failure.

Before installing, verify integrity:

```bash
cd /opt/cybra/offline-bundle
sha256sum -c SHA256SUMS
```

## Re-running setup after a failed attempt

On Windows a half-finished `.tools/<tool>` directory cannot always be deleted:
antivirus, the search indexer or a just-finished pip process holds the `.pyd`
and `.dll` files, and deletion fails with "Access denied". `uv venv` then
refuses to work with the existing directory, so a retry is impossible.

`cybra setup` handles this: it retries deletion, and if the files are still
locked it renames the stale directory aside and creates a fresh environment.
The leftover `<tool>.stale-<timestamp>` folder can be deleted later, once the
antivirus has finished with it.

If a run fails for another reason, simply run the same command again. Setup is
per-tool, so a failure in one tool does not affect the others.

## Which benchmarks are affected

Eight benchmarks ship with the console. Only three need nothing from a bundle:

| Benchmark | How it is installed | Bundle needed |
|-----------|--------------------|---------------|
| HarmBench, JailbreakBench, Security Regression | pure Python, ships in the image | no |
| BIPIA | vendored code in `vendor/bipia` + 28 wheels from `locks/bipia.txt` | **yes** |
| garak | git + 174 wheels | **yes** |
| PyRIT | git + 108 wheels | **yes** |
| AgentDojo | git + 70 wheels | **yes** |
| promptfoo | npm package | **yes** |

BIPIA is the easy one to get wrong. `vendor/bipia` is the upstream data
builders, vendored unchanged and shipped in the image — but importing
`bipia.data` also pulls `pandas`, `jsonlines`, `nltk` and `transformers`,
which are *not* in the image. The console reports BIPIA as available, because
`scan/capabilities.py` treats it as vendored, so the gap only shows up when
the run fails at the import. Name it explicitly in `cybra setup --tools`.

So a deployment that runs only HarmBench, JailbreakBench and Security
Regression needs no bundle at all.

## Requirements on the target machine

- **glibc 2.28 or newer** for Linux — Debian 10+, Ubuntu 20.04+, RHEL 8+.
  Check with `ldd --version`. Older systems are not supported: current numpy
  and torch publishes no wheels for them.
- **Python 3.12** for the host process. The bundle wheels are built for cp312.
- **Node.js 22+** if the deployment needs promptfoo.
- `uv` — `cybra setup` uses it to create per-tool environments. **You do
  not need to install it separately when using a bundle**: a version
  built for the target platform ships inside `wheels/`, and setup
  installs it automatically if it is missing. On a machine with network
  access, `pip install uv` is enough.

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
