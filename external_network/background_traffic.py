class BackgroundTraffic(object):

    def create_background_generator(self, net, total_hosts, offset, SWITCHES,
                                    BACKGROUND_HOSTS, TEST_SWITCHES):

        for i in range(0, total_hosts):
            BACKGROUND_HOSTS.append(net.addHost('h' + str(i + offset - 1)))
            TEST_SWITCHES.append(net.addSwitch('s' + str(i + offset)))

            net.addLink(SWITCHES[0], TEST_SWITCHES[i], bw=10, delay='10ms')
            net.addLink(BACKGROUND_HOSTS[i], TEST_SWITCHES[i], bw=10, delay='10ms')