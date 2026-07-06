# TAGI Companion App

## Overview

The Companion App is built with **PyQt5** and **Qt Designer**, and is supported on **Windows 11** and **Ubuntu** (up to 26.04).

---

## Getting Started

### Running the App

Make sure you have **uv** installed, as it will handle all Python dependencies automatically.

**Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then, inside the `app/` folder, simply run:
```bash
uv run src/app.py
```

> **Note:** `build.sh` is only needed if you want to generate a standalone distributable.

## Connecting to TAGI

The Companion App automatically discovers TAGI robots on the local network using **UDP broadcast**.

Once your TAGI is found:
1. Click the **Connect** button to establish a connection.
2. Use the app to explore and test different robot functionalities.

> **Tip:** Take note of the robot's IP address — you'll likely want to **SSH into it** for development purposes.

---

### Prebuilt Version

If you'd prefer not to build from source, you can **request a prebuilt version by email**.

---

## Communication

The app communicates with TAGI via a **REST API**, which is also a convenient way to control the robot directly, independently of the app.