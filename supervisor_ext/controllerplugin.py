from supervisor.supervisorctl import ControllerPluginBase

from supervisor.options import make_namespec
from supervisor.options import split_namespec

from supervisor import xmlrpc
from supervisor import states

import pprint
import shlex
import os
from fnmatch import fnmatch
import xmlrpclib

class LSBStatusExitStatuses:
    NOT_RUNNING = 3
    UNKNOWN = 4

class ExtControllerPlugin(ControllerPluginBase):
    def __init__(self, controller):
        self.ctl   = controller

    def _get_tcp_ports(self):
        FILENAMESS = ['/proc/net/tcp', '/proc/net/tcp6', '/proc/net/udp', '/proc/net/udp6']
        # files = [open(i, "r") for i in FILENAMESS]
        files = []
        for i in FILENAMESS:
            if os.path.isfile(i):
                files = files + [open(i, "r")]
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

        names = arg.split()
        if not names or "all" in names:
            matching_infos = all_infos
        else:
            matching_infos = []

            for name in names:
                bad_name = True
                group_name, process_name = split_namespec(name)

                for info in all_infos:
                    matched = info['group'] == group_name
                    if process_name is not None:
                        matched = matched and info['name'] == process_name
                        if group_name == process_name:
                            matched = fnmatch(info['name'], process_name)

                    if matched:
                        bad_name = False
                        matching_infos.append(info)

                if bad_name:
                    if process_name is None:
                        msg = "%s: ERROR (no such group)" % group_name
                    else:
                        msg = "%s: ERROR (no such process)" % name
                    self.ctl.output(msg)
                    self.ctl.exitstatus = LSBStatusExitStatuses.UNKNOWN

        self._show_statuses(matching_infos)

        for info in matching_infos:
            if info['state'] in states.STOPPED_STATES:
                self.ctl.exitstatus = LSBStatusExitStatuses.NOT_RUNNING

    def help_extstatus(self):
        self.ctl.output("extstatus\t\t\tGet all process status info, with listen ports")
        self.ctl.output("extstatus <name>\t\tGet status for a single process")
        self.ctl.output("extstatus <gname>:*\tGet status for all "
                        "processes in a group")
        self.ctl.output("extstatus <name> <name>\tGet status for multiple named "
                        "processes")

    def _startresult(self, result):
        name = make_namespec(result['group'], result['name'])
        code = result['status']
        template = '%s: ERROR (%s)'
        if code == xmlrpc.Faults.BAD_NAME:
            return template % (name, 'no such process')
        elif code == xmlrpc.Faults.NO_FILE:
            return template % (name, 'no such file')
        elif code == xmlrpc.Faults.NOT_EXECUTABLE:
            return template % (name, 'file is not executable')
        elif code == xmlrpc.Faults.ALREADY_STARTED:
            return template % (name, 'already started')
        elif code == xmlrpc.Faults.SPAWN_ERROR:
            return template % (name, 'spawn error')
        elif code == xmlrpc.Faults.ABNORMAL_TERMINATION:
            return template % (name, 'abnormal termination')
        elif code == xmlrpc.Faults.SUCCESS:
            return '%s: started' % name
        # assertion
        raise ValueError('Unknown result code %s for %s' % (code, name))

    def _extstart(self, arg):
        if not self.ctl.upcheck():
            return

        names = arg.split()
        supervisor = self.ctl.get_supervisor()

        if not names:
            self.ctl.output("Error: start requires a process name")
            self.help_extstart()
            return

        if 'all' in names:
            results = supervisor.startAllProcesses()
            for result in results:
                result = self._startresult(result)
                self.ctl.output(result)

        else:
            for name in names:
                group_name, process_name = split_namespec(name)
                if process_name is None:
                    try:
                        results = supervisor.startProcessGroup(group_name)
                        for result in results:
                            result = self._startresult(result)
                            self.ctl.output(result)
                    except xmlrpclib.Fault, e:
                        if e.faultCode == xmlrpc.Faults.BAD_NAME:
                            error = "%s: ERROR (no such group)" % group_name
                            self.ctl.output(error)
                        else:
                            raise
                else:
                    try:
                        result = supervisor.startProcess(name)
                    except xmlrpclib.Fault, e:
                        error = self._startresult({'status': e.faultCode,
                                                   'name': process_name,
                                                   'group': group_name,
                                                   'description': e.faultString})
                        self.ctl.output(error)
                    else:
                        name = make_namespec(group_name, process_name)
                        self.ctl.output('%s: started' % name)

    def do_extstart(self, arg):
        if not self.ctl.upcheck():
            self.ctl.exitstatus = LSBStatusExitStatuses.UNKNOWN
            return

        supervisor = self.ctl.get_supervisor()
        all_infos = supervisor.getAllProcessInfo()

        names = arg.split()
        if not names or "all" in names:
            matching_names = 'all'
        else:
            matching_names = ''

            for name in names:
                bad_name = True
                group_name, process_name = split_namespec(name)

                for info in all_infos:
                    matched = info['group'] == group_name
                    if process_name is not None:
                        matched = matched and info['name'] == process_name
                        if group_name == process_name:
                            matched = fnmatch(info['name'], process_name)

                    if matched:
                        bad_name = False
                        program_name = make_namespec(info['group'], info['name'])
                        matching_names = matching_names + ' ' + program_name

                if bad_name:
                    if process_name is None:
                        msg = "%s: ERROR (no such group)" % group_name
                    else:
                        msg = "%s: ERROR (no such process)" % name
                    self.ctl.output(msg)
                    self.ctl.exitstatus = LSBStatusExitStatuses.UNKNOWN

        if matching_names:
            self._extstart(matching_names)

    def help_extstart(self):
        self.ctl.output("extstart <name>\t\tStart a process")
        self.ctl.output("extstart <gname>:*\t\tStart all processes in a group")
        self.ctl.output("extstart <name> <name>\tStart multiple processes or groups")
        self.ctl.output("extstart all\t\tStart all processes")

    def _stopresult(self, result):
        name = make_namespec(result['group'], result['name'])
        code = result['status']
        fault_string = result['description']
        template = '%s: ERROR (%s)'
        if code == xmlrpc.Faults.BAD_NAME:
            return template % (name, 'no such process')
        elif code == xmlrpc.Faults.NOT_RUNNING:
            return template % (name, 'not running')
        elif code == xmlrpc.Faults.SUCCESS:
            return '%s: stopped' % name
        elif code == xmlrpc.Faults.FAILED:
            return fault_string
        # assertion
        raise ValueError('Unknown result code %s for %s' % (code, name))

    def _extstop(self, arg):
        if not self.ctl.upcheck():
            return

        names = arg.split()
        supervisor = self.ctl.get_supervisor()

        if not names:
            self.ctl.output('Error: stop requires a process name')
            self.help_extstop()
            return

        if 'all' in names:
            results = supervisor.stopAllProcesses()
            for result in results:
                result = self._stopresult(result)
                self.ctl.output(result)

        else:
            for name in names:
                group_name, process_name = split_namespec(name)
                if process_name is None:
                    try:
                        results = supervisor.stopProcessGroup(group_name)
                        for result in results:
                            result = self._stopresult(result)
                            self.ctl.output(result)
                    except xmlrpclib.Fault, e:
                        if e.faultCode == xmlrpc.Faults.BAD_NAME:
                            error = "%s: ERROR (no such group)" % group_name
                            self.ctl.output(error)
                        else:
                            raise
                else:
                    try:
                        result = supervisor.stopProcess(name)
                    except xmlrpclib.Fault, e:
                        error = self._stopresult({'status': e.faultCode,
                                                  'name': process_name,
                                                  'group': group_name,
                                                  'description':e.faultString})
                        self.ctl.output(error)
                    else:
                        name = make_namespec(group_name, process_name)
                        self.ctl.output('%s: stopped' % name)

    def do_extstop(self, arg):
        if not self.ctl.upcheck():
            self.ctl.exitstatus = LSBStatusExitStatuses.UNKNOWN
            return

        supervisor = self.ctl.get_supervisor()
        all_infos = supervisor.getAllProcessInfo()

        names = arg.split()
        if not names or "all" in names:
            matching_names = 'all'
        else:
            matching_names = ''

            for name in names:
                bad_name = True
                group_name, process_name = split_namespec(name)

                for info in all_infos:
                    matched = info['group'] == group_name
                    if process_name is not None:
                        matched = matched and info['name'] == process_name
                        if group_name == process_name:
                            matched = fnmatch(info['name'], process_name)

                    if matched:
                        bad_name = False
                        program_name = make_namespec(info['group'], info['name'])
                        matching_names = matching_names + ' ' + program_name

                if bad_name:
                    if process_name is None:
                        msg = "%s: ERROR (no such group)" % group_name
                    else:
                        msg = "%s: ERROR (no such process)" % name
                    self.ctl.output(msg)
                    self.ctl.exitstatus = LSBStatusExitStatuses.UNKNOWN

        if matching_names:
            self._extstop(matching_names)

    def help_extstop(self):
        self.ctl.output("extstop <name>\t\tStop a process")
        self.ctl.output("extstop <gname>:*\t\tStop all processes in a group")
        self.ctl.output("extstop <name> <name>\tStop multiple processes or groups")
        self.ctl.output("extstop all\t\tStop all processes")

def make_main_controllerplugin(controller, **config):
    return ExtControllerPlugin(controller)
