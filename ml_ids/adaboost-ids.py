from pox.core import core
from pox.lib.addresses import IPAddr, EthAddr
from pox.lib.util import dpidToStr
from pox.lib.revent import EventHalt
import pox.openflow.libopenflow_01 as of
import pox.lib.packet as pkt
from sklearn.externals import joblib

CLASSIFIER_FILE = '/media/sf_ids-sdn/ml_ids/adaboost-ids.pkl'

log = core.getLogger()
checker = list()
switch_number = -1
global_black_list = list()

PROTOCOLS = {
    pkt.ipv4.ICMP_PROTOCOL: 0,
    pkt.ipv4.IGMP_PROTOCOL: 1,
    pkt.ipv6.ICMP6_PROTOCOL: 2,
    pkt.ipv4.TCP_PROTOCOL: 4,
    pkt.ipv4.UDP_PROTOCOL: 5
}

TARGET_HOSTS_FILE = '/media/sf_ids-sdn/target_hosts.txt'


class PacketChecker(object):
    def __init__(self, connection):
        self.connection = connection
        connection.addListeners(self)

        self.number = switch_number
        self.attached_host = '10.0.0.' + str(self.number)
        self.enable_checker = False
        self.srcip_list = {}
        self.black_list = list()
        self.timestamp_log = list()
        self.source_ip_count_list = {}
        self.destination_ip_count_list = {}
        self.count = 0

        self.clf = joblib.load(CLASSIFIER_FILE)
        log.info('Classifier loaded')

        log.info('Switch active')
        log.info('Switch number:' + str(self.number))

        self.activate_ids()

    def activate_ids(self, filepath=TARGET_HOSTS_FILE):
        log.info('Acitvating IDS switches')

        f = open(filepath, 'r')
        for line in f:
            num = int(line[0])

            if num == self.number:
                self.set_checker(True)
                log.debug('IDS Switch %i activated' % num)

    def set_checker(self, enable):
        self.enable_checker = bool(enable)
        print 'This checker has been set to: ' + str(enable)

    def get_global_blacklist(self):
        print 'Blacklist: %s' % str(global_black_list)

    def generate_prediction_entry(self, ip, dst_ip, dst_port, packet,
                                  packet_in):
        entry = list()

        entry.append(dst_port)
        entry.append(self.destination_ip_count_list[dst_ip])
        entry.append(1)
        entry.append(packet_in.in_port)
        entry.append(self.source_ip_count_list[ip.srcip])

        protocol_one_hot = [0, 0, 0, 0, 0, 0]

        protocol_num = PROTOCOLS[ip.protocol]
        protocol_one_hot[protocol_num] = 1
        entry.extend(protocol_one_hot)

        return [entry]

    def set_block_rule(self, ip):
        msg = of.ofp_flow_mod()
        msg.priority = 30000
        msg.match.dl_type = pkt.ethernet.IP_TYPE
        msg.match.nw_dst = IPAddr(self.attached_host)
        msg.match.nw_src = ip.srcip
        msg.match.nw_proto = pkt.ipv4.ICMP_PROTOCOL
        self.connection.send(msg)

    def _handle_PacketIn(self, event):
        log.info('IDS#%s Packet In. Checker: %s' % (self.number,
                                                    str(self.enable_checker)))

        if self.enable_checker is True:
            packet = event.parsed
            packet_in = event.ofp

            self.count += 1
            log.info("Switch#" + str(self.number) + " packet# " +
                     str(self.count))

            ip = packet.find('ipv4')
            if ip is None:
                log.info("Switch# " + str(self.number) + " This isn't IP!")
            else:

                log.info("Switch#" + str(self.number) + " Source IP: " +
                         str(ip.srcip) + 'Destination IP:' + str(ip.dstip))

                # Do nothing if packet came from host
                log.debug('%s - %s' % (str(self.attached_host), str(ip.srcip)))
                if self.attached_host == ip.srcip:
                    return

                # Check if IP is already blocked
                if str(ip.srcip) in self.black_list:
                    log.info("%s BLOCKED!" % str(ip.srcip))

                    # Create openflow message to set block rule
                    self.set_block_rule(ip)
                    return EventHalt

                # Check if destination port is recorded as a table rule
                log.info(core.switch_pt.mac_to_port)
                log.info('Packet dst: %s' % packet)
                if packet.dst not in core.switch_pt.mac_to_port:
                    log.info('Skip packet. Not in mac_to_port')
                    return

                # Check and update count of destination port
                dst_port = core.switch_pt.mac_to_port[packet.dst]

                # dst_port = 1 # packet.dst
                dst_ip = IPAddr(self.attached_host)
                if dst_ip in self.destination_ip_count_list:
                    self.destination_ip_count_list[dst_ip] += 1
                else:
                    self.destination_ip_count_list[dst_ip] = 1

                # Check and update count of source IP
                if ip.srcip in self.source_ip_count_list:
                    self.source_ip_count_list[ip.srcip] += 1
                else:
                    self.source_ip_count_list[ip.srcip] = 1

                # Generate array for prediction then classify
                # entry = self.generate_prediction_entry(
                #     ip, dst_ip, dst_port, packet, packet_in)
                # pred = self.clf.predict(entry)

                # log.debug('%s - classification: %i' % (str(ip.srcip), pred))
                pred = False

                if pred:
                    log.info("Added to blacklist: %s" % str(ip.srcip))
                    self.black_list.append(str(ip.srcip))
                    global_black_list.append(str(ip.srcip))

                    # Create openflow message to set block rule
                    self.set_block_rule(ip)

                    # Log IP of anomalous host
                    core.IDSMetricLogger.log_blocked_host(ip.srcip)


# Start Component
def launch():
    def start_switch(event):
        global switch_number
        switch_number += 1
        log.debug("Controlling %s" % (event.connection, ))
        checker.append(PacketChecker(event.connection))
        core.Interactive.variables['checker'] = checker

    core.openflow.addListenerByName("ConnectionUp", start_switch)