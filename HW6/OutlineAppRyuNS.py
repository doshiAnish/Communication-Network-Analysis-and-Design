# Copyright 2016 Greg M. Bernstein
"""
This is an outline of a general Ryu application that demonstrates a number of
OpenFlow, Ryu features, and a python inspection/debug command line. For more
information see:
http://www.grotto-networking.com/SDNfun.html#programming-switches-with-ryu

This application will only work with Mininet networks that are loop free since
it uses flooding. To launch the application just use:
    python OutlineApp.py
If you don't want to use the telnet/python backdoor:
    python OutlineApp.py --notelnet

To launch mininet using a remote controller and a topology with 3 switches and
two hosts per switch.
sudo mn --topo linear,3,2 --controller=remote,ip=192.168.56.1

To bring up our 'backdoor' python interface on the machine you are running this
program (windows or Linux) type:
telnet localhost 3000

Getting a reference to the Outline application in the 'backdoor' python shell:
```python
from ryu.base.app_manager import AppManager
am = AppManager.get_instance()
myapp = am.applications["OutlineApp"]
```
"""
from builtins import hex
from collections import deque  # Standard python queue structure
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

if __name__ == "__main__": # Stuff to set additional command line options
    from ryu import cfg
    CONF = cfg.CONF
    CONF.register_cli_opts([
        cfg.BoolOpt('notelnet', default=False,
                    help='Telnet based debugger.')
    ])


class OutlineApp(app_manager.RyuApp):
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
        super(OutlineApp, self).__init__(*args, **kwargs)
        self.switches = {}
        self.down_events = deque(maxlen=10)
        self.packet_in_events = deque(maxlen=10)
        self.port_events = deque(maxlen=10)
        # Let's see what kinds of packets get sent to the controller
        # (ARP, IPv4, IPv6).
        self.packet_in_types = {0x806: 0, 0x800: 0, 0x86DD: 0}
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
        # Might want to add code here to program switches
        self.make_dumb_hubs(doit=True)
        self.icmp_intercept(doit=True)
        
    @set_ev_cls(ofp_event.EventOFPPacketIn)
    def packet_in(self, event):
        """ Handles packets sent to the controller."""
        msg = event.msg
        packet = Packet(msg.data)
        self.packet_in_events.append(packet)
        # self.logger.info("packet: {}".format(msg))

        # Let's keep some counts on the types of packets received
        ether = packet.get_protocol(ryu.lib.packet.ethernet.ethernet)
        ipv4 = packet.get_protocol(ryu.lib.packet.ipv4.ipv4)
        udp = packet.get_protocol(ryu.lib.packet.udp.udp)
        icmp = packet.get_protocol(ryu.lib.packet.icmp.icmp)
        if not ether:
            return
        ether_type = ether.ethertype
        self.packet_in_types[ether_type] = self.packet_in_types.get(ether_type) + 1

        # Might want to add code here to extract more info from packets
        # Now let's see if we intercepted a UDP packet
        if ipv4:
            self.logger.info("Intercepted a packet from: {} to {}".format(
                ipv4.src, ipv4.dst))
        if udp:
            self.logger.info("Intercepted UDP packet with source port {} and dest port {}".format(
                udp.src_port, udp.dst_port))
        if icmp:
            self.logger.info("Intercepted ICMP packet from {} to {}".format(ipv4.src, ipv4.dst))

    @set_ev_cls(ofp_event.EventOFPPortStatus)
    def port_change(self, event):
        """Gather up some information about the event to print"""
        msg = event.msg
        dp = msg.datapath
        switch = dpidDecode(dp.id)
        port_status = msg.desc
        port = port_status.port_no
        self.logger.info("I heard a port status change from switch {} port {} ".format(switch, port))
        # self.logger.info("msg: {}".format(str(msg)))
        name = port_status.name
        if port_status.state & 1 == 0:
            state = "Up"
        else:
            state = "Down"
        self.logger.info("Port {} is {}".format(name, state))
        self.port_events.appendleft(port_status)

    def make_dumb_hubs(self, doit=True):
        """ A command to turn fancy switches into dumb hubs or remove them."""
        for switch, datapath in self.switches.items():
            ofproto = datapath.ofproto
            parser = datapath.ofproto_parser
            if doit:
                command = ofproto.OFPFC_ADD
            else:
                command = ofproto.OFPFC_DELETE
            actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
            match = parser.OFPMatch()
            mod = parser.OFPFlowMod(
                datapath=datapath, match=match, cookie=0,
                command=command, idle_timeout=0, hard_timeout=0,
                priority=10,
                flags=ofproto.OFPFF_SEND_FLOW_REM, actions=actions)
            datapath.send_msg(mod)

    def udp_intercept(self, udp_port, doit=True):
        # Set up or remove a redirect for a particular UDP port
        # Match on Ethertype = 0x0800 IP, UDP is IP protocol number 17
        self.logger.info("UDP intercept called with port {}".format(udp_port))
        for switch, datapath in self.switches.items():
            ofproto = datapath.ofproto
            parser = datapath.ofproto_parser
            if doit:
                command = ofproto.OFPFC_ADD
            else:
                command = ofproto.OFPFC_DELETE
            actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER)]
            match = parser.OFPMatch(dl_type=0x800, nw_proto=17, tp_dst=udp_port)
            mod = parser.OFPFlowMod(
                datapath=datapath, match=match, cookie=0,
                command=command, idle_timeout=0, hard_timeout=0,
                priority=20,
                flags=ofproto.OFPFF_SEND_FLOW_REM, actions=actions)
            datapath.send_msg(mod)

    def icmp_intercept(self, doit=True):
        # Fill in code here for ICMP interception
        self.logger.info("ICMP intercept called")
        for switch, datapath in self.switches.items():
            ofproto = datapath.ofproto
            parser = datapath.ofproto_parser
            if doit:
                command = ofproto.OFPFC_ADD
            else:
                command = ofproto.OFPFC_DELETE
            actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER)]
            match = parser.OFPMatch(dl_type=0x800, nw_proto=1)
            mod = parser.OFPFlowMod(
                datapath=datapath, match=match, cookie=0,
                command=command, idle_timeout=0, hard_timeout=0,
                priority=20,
                flags=ofproto.OFPFF_SEND_FLOW_REM, actions=actions)
            datapath.send_msg(mod)

    def lldp_intercept(self, doit=True):
        # Fill in code here for LLDP interception
        pass

def dpidDecode(aLong):
    try:
        myBytes = bytearray.fromhex('{:8x}'.format(aLong)).strip()
        return myBytes.decode()
    except ValueError:
        return str(aLong)

if __name__ == "__main__":
    manager.main(args=sys.argv)
