from supervisor.states import SupervisorStates
from supervisor.xmlrpc import Faults
from supervisor.xmlrpc import RPCError
from supervisor.options import make_namespec
from supervisor.options import split_namespec
from supervisor.states import getProcessStateDescription
from supervisor.states import ProcessStates
from supervisor.options import VERSION

import time
import datetime

API_VERSION = '3.0'

class ExtNamespaceRPCInterface:
    """ A Supervisor RPC interface that provides the ability
    to cache abritrary data in the Supervisor instance as key/value pairs.
    """

    def __init__(self, supervisord):
        self.supervisord = supervisord

    def _update(self, text):
        self.update_text = text # for unit tests, mainly
        if ( isinstance(self.supervisord.options.mood, int) and
             self.supervisord.options.mood < SupervisorStates.RUNNING ):
            raise RPCError(Faults.SHUTDOWN_STATE)

    # RPC API methods

    def getAPIVersion(self):
        """ Return the version of the RPC API used by supervisord

        @return string version version id
        """
        self._update('getAPIVersion')
        return API_VERSION

    getVersion = getAPIVersion # b/w compatibility with releases before 3.0

    def getSupervisorVersion(self):
        """ Return the version of the supervisor package in use by supervisord

        @return string version version id
        """
        self._update('getSupervisorVersion')
        return VERSION

    def _getGroupAndProcess(self, name):
        # get process to start from name
        group_name, process_name = split_namespec(name)

        group = self.supervisord.process_groups.get(group_name)
        if group is None:
            raise RPCError(Faults.BAD_NAME, name)

        if process_name is None:
            return group, None

        process = group.processes.get(process_name)
        if process is None:
            raise RPCError(Faults.BAD_NAME, name)

        return group, process

    def _interpretProcessInfo(self, info):
        state = info['state']

        if state == ProcessStates.RUNNING:
            start = info['start']
            now = info['now']
            start_dt = datetime.datetime(*time.gmtime(start)[:6])
            now_dt = datetime.datetime(*time.gmtime(now)[:6])
            uptime = now_dt - start_dt
            desc = 'pid %s, uptime %s' % (info['pid'], uptime)

        elif state in (ProcessStates.FATAL, ProcessStates.BACKOFF):
            desc = info['spawnerr']
            if not desc:
                desc = 'unknown error (try "tail %s")' % info['name']

        elif state in (ProcessStates.STOPPED, ProcessStates.EXITED):
            if info['start']:
                stop = info['stop']
                stop_dt = datetime.datetime(*time.localtime(stop)[:7])
                desc = stop_dt.strftime('%b %d %I:%M %p')
            else:
                desc = 'Not started'

        else:
            desc = ''

        return desc

    def getProcessInfo(self, name):
        """ Get info about a process named name

        @param string name The name of the process (or 'group:name')
        @return struct result     A structure containing data about the process
        """
        self._update('getProcessInfo')

        group, process = self._getGroupAndProcess(name)

        if process is None:
            raise RPCError(Faults.BAD_NAME, name)

        start = int(process.laststart)
        stop = int(process.laststop)
        now = int(time.time())

        state = process.get_state()
        spawnerr = process.spawnerr or ''
        exitstatus = process.exitstatus or 0
        stdout_logfile = process.config.stdout_logfile or ''
        stderr_logfile = process.config.stderr_logfile or ''

        info = {
            'name':process.config.name,
            'group':group.config.name,
            'start':start,
            'stop':stop,
            'now':now,
            'state':state,
            'statename':getProcessStateDescription(state),
            'spawnerr':spawnerr,
            'exitstatus':exitstatus,
            'logfile':stdout_logfile, # b/c alias
            'stdout_logfile':stdout_logfile,
            'stderr_logfile':stderr_logfile,
            'pid':process.pid,
            }

        description = self._interpretProcessInfo(info)
        info['description'] = description
        info['directory'] = process.config.directory
        info['environment'] = process.config.environment
        return info

    def getAllProcessInfo(self):
        """ Get info about all processes

        @return array result  An array of process status results
        """
        self._update('getAllProcessInfo')

        all_processes = self._getAllProcesses(lexical=True)

        output = []
        for group, process in all_processes:
            name = make_namespec(group.config.name, process.config.name)
            output.append(self.getProcessInfo(name))
        return output

    def _getAllProcesses(self, lexical=False):
        # if lexical is true, return processes sorted in lexical order,
        # otherwise, sort in priority order
        all_processes = []

        if lexical:
            group_names = self.supervisord.process_groups.keys()
            group_names.sort()
            for group_name in group_names:
                group = self.supervisord.process_groups[group_name]
                process_names = group.processes.keys()
                process_names.sort()
                for process_name in process_names:
                    process = group.processes[process_name]
                    all_processes.append((group, process))
        else:
            groups = self.supervisord.process_groups.values()
            groups.sort() # asc by priority

            for group in groups:
                processes = group.processes.values()
                processes.sort() # asc by priority
                for process in processes:
                    all_processes.append((group, process))

        return all_processes

def make_main_rpcinterface(supervisord, **config):
    return ExtNamespaceRPCInterface(supervisord)
