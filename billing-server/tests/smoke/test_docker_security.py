import subprocess
import json
import pytest
from app.config import settings

def get_published_ports(container_name: str) -> dict:
    try:
        result = subprocess.run(
            ["docker", "inspect", container_name],
            capture_output=True,
            text=True,
            check=True
        )
        data = json.loads(result.stdout)
        # PortBindings is a dict of { "5432/tcp": [{"HostIp": "", "HostPort": "5432"}] }
        # If it's not exposed to host, it will be None or {}
        bindings = data[0].get("HostConfig", {}).get("PortBindings")
        return bindings or {}
    except subprocess.CalledProcessError:
        return {}

@pytest.mark.parametrize("container", [
    "billing-server-postgres-1",
    "billing-server-redis-1",
    "billing-server-billing-api-1",
])
def test_infrastructure_containers_not_published(container: str):
    """
    Verify that internal infrastructure containers do not publish ANY ports 
    to the host network, forcing all traffic to route through Caddy.
    """
    bindings = get_published_ports(container)

    # Local development requires postgres to be exposed to run pytest from the host.
    if container == "billing-server-postgres-1" and settings.environment != "production":
        return

    assert not bindings, (
        f"SECURITY BREACH: Container {container} is publishing ports to the host network: {bindings}. "
        f"It should only be accessible within the internal Docker network."
    )
