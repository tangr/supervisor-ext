from supervisor.supervisorctl import ControllerPluginBase
from supervisor.options import make_namespec
from supervisor import states
import pprint
import shlex
import os

class LSBStatusExitStatuses:
    NOT_RUNNING = 3
    UNKNOWN = 4

class ExtControllerPlugin(ControllerPluginBase):
    def __init__(self, controller):
        self.ctl   = controller

    def _get_tcp_ports(self):
        FILENAMESS = ['/proc/net/tcp', '/proc/net/tcp6', '/proc/net/udp', '/proc/net/udp6']
        files = [open(i, "r") for i in FILENAMESS]
        ports = {}
        for file in files:
            local_address_pos = 1
            rem_address_pos = 2
            inode_pos = 9
            for line in file:
                rem_address_port = line.split()[rem_address_pos].split(':')[-1]
                if rem_address_port == '0000':
                    local_address_port = line.split()[local_address_pos].split(':')[-1]
                    port = int(local_address_port, 16)
                    inode = int(line.split()[inode_pos])
                    ports[inode] = port
        return ports

    def _get_listen_ports(self, pid, global_ports):
        ports = set()
        list_dir = os.walk('/proc/' + str(pid) + '/fd')
        for root, dirs, files in list_dir:
            for f in files:
                if os.path.islink(root + '/' + f):
                    socketfd = os.path.realpath(root + '/' + f).split('/')[-1]
                    if socketfd.startswith('socket'):
                        fdid = int(socketfd[8:-1])
                        port = global_ports.get(fdid)
                        if port:
                            ports.add(port)
        if ports:
            return list(ports)
        else:
            return None

    def _show_statuses(self, process_infos):
        namespecs, maxlen = [], 30
        for i, info in enumerate(process_infos):
            namespecs.append(make_namespec(info['group'], info['name']))
            if len(namespecs[i]) > maxlen:
                maxlen = len(namespecs[i])

        global_ports = self._get_tcp_ports()
        template = '%(namespec)-' + str(maxlen+3) + 's%(state)-10s%(desc)s'
        for i, info in enumerate(process_infos):
            process_pid = info['pid']
            description = info['description']
            try:
                ports = self._get_listen_ports(process_pid, global_ports)
                if ports:
                    description = description + ', ports: ' + '|'.join(str(x) for x in ports)
                else:
                    description = description + ', ports: ' + str(None)
            except Exception as e:
                description = description
            line = template % {'namespec': namespecs[i],
                               'state': info['statename'],
                               'desc': description}
            self.ctl.output(line)

    def do_extstatus(self, arg):
        # XXX In case upcheck fails, we override the exitstatus which
        # should only return 4 for do_status
        # TODO review this
        if not self.ctl.upcheck():
            self.ctl.exitstatus = LSBStatusExitStatuses.UNKNOWN
            return

        supervisor = self.ctl.get_supervisor()
        all_infos = supervisor.getAllProcessInfo()

        matching_infos = all_infos

        self._show_statuses(matching_infos)

        for info in matching_infos:
            if info['state'] in states.STOPPED_STATES:
                self.ctl.exitstatus = LSBStatusExitStatuses.NOT_RUNNING

    # def do_extstatus(self, args):
    #     if args:
    #         return self.help_cache_count()
    #     count = self.cache.getCount()
    #     self.ctl.output(str(count))

    def help_extstatus(self):
        self.ctl.output("status\t\t\tGet all process status info, with listen ports")

def make_main_controllerplugin(controller, **config):
    return ExtControllerPlugin(controller)
