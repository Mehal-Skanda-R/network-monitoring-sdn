cat > mininet/topology.py <<'PY'
#!/usr/bin/env python3

"""
Member 1: Mininet topology for the Network Monitoring SDN project.

Topology:
    h1 ----\
            s1 -------- s2
    h2 ----/              \---- h3
                            \--- h4

The remote Ryu controller listens on TCP port 6653.
"""

from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI


class OpenFlow13Switch(OVSSwitch):
    """Configure OVS switches to use OpenFlow 1.3."""

    def __init__(self, name, **params):
        params["protocols"] = "OpenFlow13"
        super().__init__(name, **params)


class MonitoringTopology(Topo):
    """Two-switch, four-host monitoring topology."""

    def build(self):
        h1 = self.addHost("h1", ip="10.0.0.1/24")
        h2 = self.addHost("h2", ip="10.0.0.2/24")
        h3 = self.addHost("h3", ip="10.0.0.3/24")
        h4 = self.addHost("h4", ip="10.0.0.4/24")

        s1 = self.addSwitch("s1", dpid="0000000000000001")
        s2 = self.addSwitch("s2", dpid="0000000000000002")

        self.addLink(h1, s1)
        self.addLink(h2, s1)
        self.addLink(h3, s2)
        self.addLink(h4, s2)

        # Inter-switch link: 10 Mbps, 5 ms delay.
        self.addLink(s1, s2, cls=TCLink, bw=10, delay="5ms")


def run_network():
    topology = MonitoringTopology()

    net = Mininet(
        topo=topology,
        controller=None,
        switch=OpenFlow13Switch,
        link=TCLink,
        autoSetMacs=True
    )

    controller = RemoteController(
        "c0",
        ip="127.0.0.1",
        port=6653
    )
    net.addController(controller)

    try:
        print("Starting Network Monitoring SDN topology...")
        net.start()

        print("Topology started.")
        print("Hosts: h1, h2, h3, h4")
        print("Switches: s1, s2")
        print("Controller: Ryu at 127.0.0.1:6653")
        print("OpenFlow version: 1.3")

        CLI(net)

    finally:
        net.stop()
        print("Mininet topology stopped.")


if __name__ == "__main__":
    run_network()
PY
