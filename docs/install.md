# Installation

!!! note

   ``latency-monitor`` requires Python 3.11+

The tool is available on PyPI and can be installed using ``pip``:

```bash
$ pip install latency-monitor
```

Or using [``uv``](https://docs.astral.sh/uv/) to install it under a virtual environment:

```bash
$ uv venv
Using CPython 3.13.5
Creating virtual environment at: .venv
Activate with: source .venv/bin/activate

$ uv pip install latency-monitor
Resolved 1 package in 251ms
Prepared 1 package in 16ms
Installed 1 package in 3ms
 + latency-monitor==0.1.0b2
```

Depending on the backend of your choice, you may require additional packages. See the documentation of every backend to 
understand what's required and how the dependencies can be installed.
