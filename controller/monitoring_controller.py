cat > controller/monitoring_controller.py <<'PY'
"""
Member 1: Ryu SDN controller.

Responsibilities:
- OpenFlow 1.3 switch connection.
- MAC learning and packet forwarding.
- Periodic flow-statistics collection.
- Export cumulative flow counters as JSON over UDP.
- Accept explicit block/unblock commands over a separate UDP socket.

Statistics destination:
    FLOW_STATS_HOST (default 127.0.0.1)
    FLOW_STATS_PORT (default 9998)

Control destination:
    CONTROL_HOST (default 127.0.0.1)
    CONTROL_PORT (default 9999)

The statistics receiver is an integration adapter owned by the team.
It is not Member 2's host-telemetry server.
"""

import json
import os
import socket
import time
import ipaddress

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import (
    CONFIG_DISPATCHER,
    MAIN_DISPATCHER,
    DEAD_DISPATCHER,
    set_ev_cls
)
from ryu.ofproto import ofproto_v1_3
from ryu.lib import hub
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types


class MonitoringController(app_manager.RyuApp):

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    STATS_INTERVAL = 5
    BLOCK_COOKIE = 0x4D454D42455231

    def __init__(self, *args, **kwargs):
        super(MonitoringController, self).__init__(*args, **kwargs)

        self.mac_to_port = {}
        self.datapaths = {}

        self.stats_host = os.getenv(
            "FLOW_STATS_HOST", "127.0.0.1"
        )
        self.stats_port = int(os.getenv(
            "FLOW_STATS_PORT", "9998"
        ))

        self.control_host = os.getenv(
            "CONTROL_HOST", "127.0.0.1"
        )
        self.control_port = int(os.getenv(
            "CONTROL_PORT", "9999"
        ))

        self.stats_socket = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM
        )

        self.monitor_thread = hub.spawn(self._monitor)
        self.control_thread = hub.spawn(self._control_listener)

        self.logger.info("MonitoringController initialized")

    def add_flow(
        self,
        datapath,
        priority,
        match,
        actions,
        idle_timeout=0,
        hard_timeout=0,
        cookie=0
    ):
        """Install an OpenFlow rule on a switch."""

        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        instructions = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                actions
            )
        ]

        flow_mod = parser.OFPFlowMod(
            datapath=datapath,
            cookie=cookie,
            priority=priority,
            match=match,
            instructions=instructions,
            idle_timeout=idle_timeout,
            hard_timeout=hard_timeout
        )

        datapath.send_msg(flow_mod)

    @set_ev_cls(ofp_event.EventOFPStateChange,
                [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def switch_state_change(self, ev):
        """Track connected and disconnected switches."""

        datapath = ev.datapath

        if ev.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
            self.logger.info(
                "Switch connected: s%s", datapath.id
            )

        elif ev.state == DEAD_DISPATCHER:
            self.datapaths.pop(datapath.id, None)
            self.logger.info(
                "Switch disconnected: s%s", datapath.id
            )

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures,
                CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """Install the table-miss rule after switch connection."""

        datapath = ev.msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER
            )
        ]

        self.add_flow(
            datapath,
            priority=0,
            match=match,
            actions=actions
        )

        self.logger.info(
            "Installed table-miss rule on s%s", datapath.id
        )

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        """Learn source MAC addresses and forward packets."""

        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth is None:
            return

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst = eth.dst
        src = eth.src

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        # Learn the source MAC address.
        self.mac_to_port[dpid][src] = in_port

        # If destination is known, forward to its port.
        # Otherwise, flood the packet.
        out_port = self.mac_to_port[dpid].get(
            dst, ofproto.OFPP_FLOOD
        )

        actions = [
            parser.OFPActionOutput(out_port)
        ]

        # Install a forwarding rule for known destinations.
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(
                in_port=in_port,
                eth_dst=dst
            )

            self.add_flow(
                datapath,
                priority=10,
                match=match,
                actions=actions,
                idle_timeout=60
            )

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data
        )

        datapath.send_msg(out)

    def _monitor(self):
        """Request flow statistics periodically from all switches."""

        while True:
            for datapath in list(self.datapaths.values()):
                parser = datapath.ofproto_parser

                request = parser.OFPFlowStatsRequest(
                    datapath
                )

                datapath.send_msg(request)

            hub.sleep(self.STATS_INTERVAL)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply,
                MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        """Export cumulative OpenFlow counters in detector format."""

        datapath = ev.msg.datapath
        dpid = datapath.id

        for stat in ev.msg.body:

            # Ignore the table-miss rule.
            if stat.priority == 0:
                continue

            match_data = dict(stat.match)

            # Stable identifier: same switch, table, priority
            # and match produce the same flow ID.
            match_json = json.dumps(
                match_data,
                sort_keys=True,
                default=str
            )

            flow_id = (
                "s{}:{}:{}:{}".format(
                    dpid,
                    stat.table_id,
                    stat.priority,
                    match_json
                )
            )

            flow_sample = {
                "switch": "s{}".format(dpid),
                "flow_id": flow_id,
                "byte_count": int(stat.byte_count),
                "packet_count": int(stat.packet_count),
                "timestamp": time.time()
            }

            try:
                payload = json.dumps(flow_sample).encode("utf-8")

                self.stats_socket.sendto(
                    payload,
                    (self.stats_host, self.stats_port)
                )

            except OSError as exc:
                self.logger.error(
                    "Could not export flow statistics: %s", exc
                )

    def _control_listener(self):
        """
        Receive explicit JSON commands on the control UDP port.

        Example:
            {"action": "block_ip", "ip": "10.0.0.1"}

        This listener is bound to loopback by default.
        """

        listener = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM
        )

        listener.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
        )

        listener.bind(
            (self.control_host, self.control_port)
        )

        self.logger.info(
            "Control listener ready on %s:%s",
            self.control_host,
            self.control_port
        )

        while True:
            try:
                data, _address = listener.recvfrom(4096)
                command = json.loads(data.decode("utf-8"))

                action = command.get("action")
                ip = str(
                    ipaddress.IPv4Address(command.get("ip", ""))
                )

                if action == "block_ip":
                    self.block_ip(ip)

                elif action == "unblock_ip":
                    self.unblock_ip(ip)

                else:
                    self.logger.warning(
                        "Unknown control action: %s", action
                    )

            except (ValueError, UnicodeDecodeError) as exc:
                self.logger.warning(
                    "Invalid control command: %s", exc
                )

            except OSError as exc:
                self.logger.error(
                    "Control listener error: %s", exc
                )
                hub.sleep(1)

    def block_ip(self, ip):
        """Install a high-priority IPv4 source-address drop rule."""

        for datapath in list(self.datapaths.values()):
            parser = datapath.ofproto_parser

            match = parser.OFPMatch(
                eth_type=0x0800,
                ipv4_src=ip
            )

            self.add_flow(
                datapath,
                priority=200,
                match=match,
                actions=[],
                cookie=self.BLOCK_COOKIE
            )

        self.logger.warning("Block rule requested for %s", ip)

    def unblock_ip(self, ip):
        """Remove this controller's matching source-address drop rule."""

        for datapath in list(self.datapaths.values()):
            parser = datapath.ofproto_parser
            ofproto = datapath.ofproto

            match = parser.OFPMatch(
                eth_type=0x0800,
                ipv4_src=ip
            )

            delete_request = parser.OFPFlowMod(
                datapath=datapath,
                cookie=self.BLOCK_COOKIE,
                cookie_mask=0xFFFFFFFFFFFFFFFF,
                table_id=ofproto.OFPTT_ALL,
                command=ofproto.OFPFC_DELETE,
                out_port=ofproto.OFPP_ANY,
                out_group=ofproto.OFPG_ANY,
                match=match
            )

            datapath.send_msg(delete_request)

        self.logger.info("Unblock rule requested for %s", ip)
PY
