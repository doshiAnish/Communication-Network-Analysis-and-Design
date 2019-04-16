# Copyright 2016 Greg M. Bernstein
"""

This application will only work with tree topology Mininet networks with hosts 
assigned to VLANs. On the Mininet VM I create my VLAN network from a JSON file with
the command:
sudo python NetRunnerNS.py -f ./exampleNets/MultiSwitchVLANNet3.json -ip 192.168.1.213

where the IP address above is the address of the computer running this code

To launch the application just use:
    python MultipleSwitchVLANlrn.py --netfile=./exampleNets/MultiSwitchVLANNet3.json

"""
from builtins import hex
from collections import defaultdict, namedtuple
import json
from networkx.readwrite import json_graph
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import set_ev_cls
from ryu.cmd import manager # For directly starting Ryu
from ryu.lib.packet.packet import Packet # For packet parsing
import ryu.lib.packet.ethernet
import ryu.lib.packet.ipv4
import ryu.lib.packet.udp
import sys  # For getting command line arguments and passing to Ryu
import eventlet
from eventlet import backdoor  # For telnet python access
from ryu.ofproto import ofproto_v1_0 # This code is OpenFlow 1.0 specific

# Will use this to track the VLAN info associated with each switch
SwitchVLAN = namedtuple("SwitchVLAN", ['vid2local', 'port2vid', 'taggedPorts'])

if __name__ == "__main__": # Stuff to set additional command line options
    from ryu import cfg
    CONF = cfg.CONF
    CONF.register_cli_opts([
        cfg.StrOpt('netfile', default=None, help='network json file'),
        cfg.BoolOpt('notelnet', default=False,
                    help='Telnet based debugger.')
    ])


class MultipleSwitchVLANlrn(app_manager.RyuApp):
    """ Outline of a Ryu application that performs a number of tasks and
        responds to various events.
    """
    OFP_VERSIONS = [ofproto_v1_0.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        """ Define member variables here.  I do this here so that we can look at
            them via the telnet python command line.  I use the standard Python
            deque data structure with a finite length so that I only keep the
            latest few events of a given type.
        """
        super(MultipleSwitchVLANlrn, self).__init__(*args, **kwargs)
        self.switches = {}
        self.netfile = self.CONF.netfile
        self.switches = {}
        self.switch_vid_mac_port = defaultdict(lambda: defaultdict(dict))
        # Reads in the topology file and creates a NetworkX graph
        self.g = json_graph.node_link_graph(json.load(open(self.netfile)))
        # Compute information on VLANs
        switches = []
        for node in self.g.nodes():
            if self.g.node[node]["type"] == "switch":
                switches.append(node)

        self.switch_vlan_info = {}
        for sname in switches:
            neighbors = self.g.neighbors(sname)  # Get all the neighbor nodes
            # We need to know all ports associated with a particular VLAN,
            # what VLAN is associated with each port, and which are the tagged ports
            vid2local = defaultdict(list)  # Each entry gets an empty list
            port2vid = {}
            taggedPorts = []
            for nb in neighbors:
                port_num = self.g[sname][nb]["ports"][sname]
                n_type = self.g.node[nb]["type"]
                vid = 0  # 0 is not a valid VID, could use this for tagged ports...
                if n_type == "host":
                    vid = int(self.g.node[nb][
                                  "vnid"])  # Work with numbers rather than strings
                    vid2local[vid].append(port_num)
                    port2vid[port_num] = vid
                elif n_type == "switch":
                    taggedPorts.append(port_num)
            self.switch_vlan_info[sname] = SwitchVLAN(vid2local=vid2local,
                                                 port2vid=port2vid,
                                                 taggedPorts=taggedPorts)

        if not self.CONF.notelnet:
            eventlet.spawn(backdoor.backdoor_server,
                           eventlet.listen(('localhost', 3000)))

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures)
    def switch_features(self, event):
        """ This method gets called when a switch connects to the controller.
        """
        msg = event.msg
        dp = msg.datapath
        # Assumes that datapath ID represents an ascii name
        switchName = dpidDecode(dp.id)
        self.logger.info("Switch {} came up".format(switchName))
        self.logger.info("Message: {}".format(msg))
        self.switches[switchName] = dp  # Save switch information
        # Compute VLAN membership information
        self.neighbors = self.g.neighbors(switchName)
        self.vlan2Ports = defaultdict(list)  # Each entry gets an empty list
        self.port2Vlan = {}
        for nb in self.neighbors:
            port_num = self.g[switchName][nb]["ports"][switchName]
            n_type = self.g.node[nb]["type"]
            vid = 0  # 0 is not a valid VID, could use this for tagged ports...
            if n_type == "host":
                vid = int(self.g.node[nb]["vnid"])
            self.vlan2Ports[vid].append(port_num)
            self.port2Vlan[port_num] = vid
        self.setupVlanFlooding(switchName)

    def setupVlanFlooding(self, switchName):
        datapath = self.switches[switchName]
        vlan_info = self.switch_vlan_info[switchName]
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        command = ofproto.OFPFC_ADD
        # Untagged (local) port match and actions
        self.logger.info("Setting up flows for Switch {}".format(switchName))
        for port, vid in vlan_info.port2vid.items():
            match = parser.OFPMatch(in_port=port)
            outlist = [p for p in vlan_info.vid2local[vid] if p != port]
            actions = [parser.OFPActionOutput(p) for p in outlist]
            # Add in tagged actions here
            if len(vlan_info.taggedPorts) > 0:
                actions.append(parser.OFPActionVlanVid(vid))
            for tp in vlan_info.taggedPorts:
                actions.append(parser.OFPActionOutput(tp))
            # Put together the whole message here.
            self.logger.info("Input: {}, vid: {}, actions: {}".format(port, vid,
                                                                      actions))
            # Next line is for debugging purposes only
            actions.insert(0, parser.OFPActionOutput(ofproto.OFPP_CONTROLLER))
            mod = parser.OFPFlowMod(
                datapath=datapath, match=match, cookie=0,
                command=command, idle_timeout=0, hard_timeout=0,
                priority=10,
                flags=ofproto.OFPFF_SEND_FLOW_REM, actions=actions)
            datapath.send_msg(mod)
        # Tagged port matches and actions
        # Need a match for each port, vid combination
        vid_list = list(vlan_info.vid2local.keys())
        for port in vlan_info.taggedPorts:
            for vid in vid_list:
                # The following works but not if you include dl_type=0x8100
                match = parser.OFPMatch(in_port=port, dl_vlan=vid)
                # First flood out all tagged ports except this one
                actions = [parser.OFPActionOutput(p) for p in
                           vlan_info.taggedPorts if p != port]
                # Pop the VLAN tag
                actions.append(parser.OFPActionStripVlan())
                # Send to all VID related local ports
                for lp in vlan_info.vid2local[vid]:
                    actions.append(parser.OFPActionOutput(lp))
                # Next line is for debugging purposes only
                actions.insert(0,
                              parser.OFPActionOutput(ofproto.OFPP_CONTROLLER))
                # Put together and send the whole message here
                self.logger.info("Tagged port: {}, vid: {}, actions: {}".format(
                    port, vid, actions))
                mod = parser.OFPFlowMod(
                    datapath=datapath, match=match, cookie=0,
                    command=command, idle_timeout=0, hard_timeout=0,
                    priority=10,
                    flags=ofproto.OFPFF_SEND_FLOW_REM, actions=actions)
                datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn)
    def packet_in(self, event):
        """ Handles packets sent to the controller.
            Used for debugging."""
        msg = event.msg
        in_port = msg.in_port
        dp = msg.datapath
        # Assumes that datapath ID represents an ascii name
        switchName = dpidDecode(dp.id)
        packet = Packet(msg.data)
        # self.logger.info("packet: {}".format(msg))
        ether = packet.get_protocol(ryu.lib.packet.ethernet.ethernet)

        ethertype = ether.ethertype
        if ethertype == 0x86dd:  # Ignore IPv6 packets for now
            return
        in_tagged = False
        if ethertype == 0x8100:
            ethervlan = packet.get_protocol(ryu.lib.packet.vlan.vlan)
            in_tagged = True
            if ethervlan.ethertype == 0x86dd: # Ignore IPv6
                return
            self.logger.info("VID: {}".format(ethervlan.vid))
            vid = ethervlan.vid
        else:
            vid = self.switch_vlan_info[switchName].port2vid[in_port]
        # The next line maps the source mac address to its port
        self.switch_vid_mac_port[switchName][vid][ether.src] = in_port
        self.logger.info(
            " Switch {} in port {} received packet with ethertype: {}".format(
                switchName, in_port, hex(ethertype)))
        ipv4 = packet.get_protocol(ryu.lib.packet.ipv4.ipv4)
        if ipv4:
            self.logger.info("IPv4 src: {} dst: {}".format(
                ipv4.src, ipv4.dst))
        # Check to see if we can create a direct flow rule
        dst = ether.dst
        if dst in self.switch_vid_mac_port[switchName][vid]:
            datapath = self.switches[switchName]
            ofproto = datapath.ofproto
            parser = datapath.ofproto_parser
            command = ofproto.OFPFC_ADD
            out_port = self.switch_vid_mac_port[switchName][vid][dst]
            if in_port == out_port:
                return
            out_tagged = out_port in self.switch_vlan_info[switchName].taggedPorts
            self.logger.info("Creating learned flow switch {}, VID: {}, DST_MAC: {}, in port {}, out port {}, in tagged: {}, out_tagged {}".format(switchName, vid, dst, in_port, out_port, in_tagged, out_tagged))
            if in_tagged:
                match = parser.OFPMatch(in_port=in_port, dl_vlan=vid, dl_dst=dst)
                if out_tagged:
                    actions = [parser.OFPActionOutput(out_port)]
                else:
                    actions = [parser.OFPActionStripVlan(),
                               parser.OFPActionOutput(out_port)]
            else:
                match = parser.OFPMatch(in_port=in_port, dl_dst=dst)
                if out_tagged:
                    actions = [parser.OFPActionVlanVid(vid),
                               parser.OFPActionOutput(out_port)]
                else:
                    actions = [parser.OFPActionOutput(out_port)]
            mod = parser.OFPFlowMod(
                datapath=datapath, match=match, cookie=0,
                command=command, idle_timeout=0, hard_timeout=0,
                priority=20,  # Make priority higher than flood flows
                flags=ofproto.OFPFF_SEND_FLOW_REM, actions=actions)
            datapath.send_msg(mod)

def dpidDecode(aLong):
    try:
        myBytes = bytearray.fromhex('{:8x}'.format(aLong)).strip()
        return myBytes.decode()
    except ValueError:
        return str(aLong)



if __name__ == "__main__":
    manager.main(args=sys.argv)
