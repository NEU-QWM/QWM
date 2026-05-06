# SC-qualibrate Setup Guide

This folder is a Qualibrate project for superconducting calibration nodes and graphs. The project code lives in `SC-qualibrate`, while Qualibrate's user-level configuration lives outside the repository under:

```powershell
$env:USERPROFILE\.qualibrate\config.toml
```

Use this guide when setting up the project on a new computer.

## 1. Prerequisites

Install these first:

- Git, because this project depends on packages installed from GitHub.
- Python 3.10, 3.11, or 3.12. Python 3.11 is a good default for this project.
- `uv`, used to create and manage the Python environment.

On Windows, `uv` can be installed with:

```powershell
winget install astral-sh.uv
```

If PowerShell blocks virtual-environment activation scripts, allow local scripts for the current user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## 2. Clone The Repository

Clone the repository to the machine. The examples below assume this location:

```powershell
C:\GitHub\customer-fong-lab
```

If the repository is somewhere else, replace that path everywhere in the examples.

```powershell
cd C:\GitHub
git clone <repository-url> customer-fong-lab
cd C:\GitHub\customer-fong-lab\SC-qualibrate
```

## 3. Create The uv Environment

Create the virtual environment from inside `SC-qualibrate`, where `pyproject.toml` is located:

```powershell
cd C:\GitHub\customer-fong-lab\SC-qualibrate
uv python install 3.11
uv venv --python 3.11
uv sync
```

This installs the project dependencies, including:

- `qualibrate`
- `qm-qua`
- `quam`
- `qualang-tools`
- `quam-builder`
- `qualibration-libs`

To activate the environment manually:

```powershell
.\.venv\Scripts\Activate.ps1
```

You can also avoid manual activation by prefixing commands with `uv run`.

## 4. Configure Qualibrate

Qualibrate reads its main config from the user profile, not from this project folder. Create or edit:

```powershell
C:\Users\<your-user>\.qualibrate\config.toml
```

For this project, a typical config is:

```toml
[qualibrate]
version = 5
project = "SC_FT"
log_folder = "C:\\GitHub\\customer-fong-lab\\SC-qualibrate\\user_storage\\logs"

[qualibrate.storage]
type = "local_storage"
location = "C:\\GitHub\\customer-fong-lab\\SC-qualibrate\\user_storage"

[qualibrate.app]

[qualibrate.runner]
address = "http://127.0.0.1:8001/execution/"
timeout = 13.0

[qualibrate.composite.app]
spawn = true

[qualibrate.composite.runner]
spawn = true

[qualibrate.composite.qua_dashboards]
spawn = true

[qualibrate.calibration_library]
folder = "C:\\GitHub\\customer-fong-lab\\SC-qualibrate\\calibrations\\1Q_calibrations"
resolver = "qualibrate.QualibrationLibrary"

[quam]
state_path = "C:\\GitHub\\customer-fong-lab\\SC-qualibrate\\quam_state"
```

Important fields:

- `project`: the Qualibrate project name shown in the UI.
- `qualibrate.storage.location`: where Qualibrate stores run history and saved node data.
- `qualibrate.calibration_library.folder`: the calibration folder Qualibrate scans.
- `quam.state_path`: where `state.json` and `wiring.json` are loaded from.

The example above scans only:

```text
SC-qualibrate\calibrations\1Q_calibrations
```

To scan the CZ calibrations instead, change the folder to:

```toml
folder = "C:\\GitHub\\customer-fong-lab\\SC-qualibrate\\calibrations\\CZ_calibration_fixed_couplers"
```

Do not point `folder` at `SC-qualibrate\calibrations` unless you intentionally want Qualibrate to scan multiple subprojects and you have a resolver that supports that layout.

## 5. Check The QUAM State

The active QUAM state is expected here:

```text
SC-qualibrate\quam_state\state.json
SC-qualibrate\quam_state\wiring.json
```

If those files already match the machine, no generation step is required.

If setting up a new machine or changing wiring, edit the QUAM configuration first:

- `quam_config\generate_quam.py`
- `quam_config\populate_quam_lf_mw_fems.py`
- `quam_config\instrument_limits.py`

Then regenerate and populate the QUAM state:

```powershell
cd C:\GitHub\customer-fong-lab\SC-qualibrate
uv run python -m quam_config.generate_quam
uv run python -m quam_config.populate_quam_lf_mw_fems
```

Review `quam_config\README.md` for the detailed QUAM workflow.

## 6. Validate The Calibration Library

Before launching the web app, verify that Qualibrate can scan the selected calibration folder:

```powershell
cd C:\GitHub\customer-fong-lab\SC-qualibrate
uv run python -c "from pathlib import Path; from qualibrate import QualibrationLibrary; lib = QualibrationLibrary(Path('calibrations/1Q_calibrations')); print(len(lib.nodes), 'nodes'); print(len(lib.graphs), 'graphs:', sorted(lib.graphs.keys()))"
```

For the current `1Q_calibrations` setup, the expected result is:

```text
29 nodes
4 graphs: ['FixedFrequencyTransmon_BringUp', 'FixedFrequencyTransmon_Retuning', 'FluxTunableTransmon_BringUp', 'FluxTunableTransmon_Retuning']
```

If this fails, fix the scan error before starting the web app. The UI uses the same discovery mechanism.

## 7. Start Qualibrate

Launch Qualibrate from the project folder:

```powershell
cd C:\GitHub\customer-fong-lab\SC-qualibrate
uv run qualibrate start
```

If the environment is already activated, this is equivalent:

```powershell
qualibrate start
```

Then open the local UI in a browser:

```text
http://127.0.0.1:8001
```

Keep the terminal open while using Qualibrate. The terminal shows scan errors, run errors, and server status.

## 8. Common Issues

### Port 8001 Is Already In Use

If startup fails with:

```text
only one usage of each socket address ... 127.0.0.1:8001
```

another Qualibrate process is already running. Find the process:

```powershell
Get-NetTCPConnection -LocalPort 8001 | Select-Object LocalAddress,LocalPort,State,OwningProcess
```

Then inspect or stop it:

```powershell
Get-Process -Id <PID>
Stop-Process -Id <PID>
```

Only stop a process if you are sure it is the stale Qualibrate server.

### Nodes Appear But Graphs Do Not

Run the validation command in section 6. Graph scan errors usually mean one of:

- the graph imports an old Qualibrate API path,
- the graph refers to a node name that is not present in the selected calibration folder,
- the config is pointed at the wrong calibration folder,
- the web app needs to be restarted after a code change.

### `ModuleNotFoundError` For Project Modules

Start Qualibrate from `SC-qualibrate` with `uv run qualibrate start`, or activate the `.venv` created in that folder. Starting from another environment can miss project-local modules such as `calibration_utils` and `quam_config`.

### Wrong QUAM State Is Loaded

Check the `[quam] state_path` value in:

```powershell
$env:USERPROFILE\.qualibrate\config.toml
```

It should point at this project's `quam_state` folder unless you intentionally maintain a separate state directory.

## 9. Normal Daily Workflow

For normal use after setup:

```powershell
cd C:\GitHub\customer-fong-lab\SC-qualibrate
uv run qualibrate start
```

Open:

```text
http://127.0.0.1:8001
```

Run individual nodes or one of the discovered graphs from the UI. Calibration outputs and logs are stored under `SC-qualibrate\user_storage`.
