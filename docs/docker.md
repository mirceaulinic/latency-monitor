# Docker images and usage

There are Docker images published on the following events:

- Pull Request merged into the ``main`` or ``develop`` branches.
- A new ``latency-monitor`` version is released.

On PR merge, the Docker image will be tagged using the targeted branch name, i.e., ``main`` or ``develop``.

When a new version is released, there will be a git tag being pushed to the repository, and the Dockage image will 
inherit that tag, e.g., ``v0.0.1``.

The Dockage images are available at both Docker Hub and GitHub Container Registry, whichever you prefer:

- [https://hub.docker.com/r/mirceaulinic/latency-monitor/tags](https://hub.docker.com/r/mirceaulinic/latency-monitor/tags)
- [https://github.com/mirceaulinic/latency-monitor/pkgs/container/latency-monitor](https://github.com/mirceaulinic/latency-monitor/pkgs/container/latency-monitor)

Tip: both Docker images have all the possible dependencies installed, so you can use the backends you require without 
worrying about additional requirements.

Example:

```bash
$ docker run -ti mirceaulinic/latency-monitor
      Built latency-monitor @ file:///opt/latency-monitor
Uninstalled 1 package in 1ms
Installed 1 package in 2ms
Unable to read the config file from /opt/latency-monitor/latency.toml
[2026-01-11 18:54:02,924] [INFO] Starting the metrics worker
[2026-01-11 18:54:02,928] [INFO] Starting the UDP server
[2026-01-11 18:54:02,930] [INFO] Starting the TCP server
```

You may need the ``-p`` option for port mapping, but of course that largely depends on your use case and setup. As for 
the configuration file, you can mount it as a volume and use the ``-c`` flag after the Docker image tag, as well as 
other CLI arguments you may require, e.g.,

```bash
$ docker run  -p 8000:8000 -p 8001:8001/udp -v ./latency.toml:/path/to/latency.toml -ti mirceaulinic/latency-monitor -c /path/to/latency.toml --no-rtt --no-tcp
      Built latency-monitor @ file:///opt/latency-monitor
Uninstalled 1 package in 1ms
Installed 1 package in 4ms
[2026-01-11 18:59:57,434] [INFO] Starting the metrics worker
[2026-01-11 18:59:57,436] [INFO] Starting the UDP server
```
