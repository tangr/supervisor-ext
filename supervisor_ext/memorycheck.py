import argparse
import sys
import os
import mmap

from supervisor import childutils

def _get_meminfo():
    meminfo_file = open('/proc/meminfo')
    for line in meminfo_file:
        if line.startswith('MemTotal:'):
            mem_total = int(line.split()[1])
            break
    return mem_total

class MemCheck(object):
    """docstring for MemCheck"""
    def __init__(self, process_name, mem_total, mem_maxrate, rpc=None):
        super(MemCheck, self).__init__()
        self.process_name = process_name
        self.rpc = rpc
        self.mem_total = mem_total
        self.mem_maxrate = mem_maxrate
        self.stdin = sys.stdin
        self.stdout = sys.stdout
        self.stderr = sys.stderr

    def runforever(self):
        while True:
            headers, payload = childutils.listener.wait(self.stdin, self.stdout)

            if not headers['eventname'].startswith('TICK'):
                childutils.listener.ok(self.stdout)
                continue

            info = self.rpc.supervisor.getProcessInfo(self.process_name)
            pid = info['pid']
            if not pid:
                childutils.listener.ok(self.stdout)
                continue
            rss = self._get_process_rss(pid)
            if rss >= self.mem_maxrate:
                self.restart(self.process_name)
                childutils.listener.ok(self.stdout)
                continue
            childutils.listener.ok(self.stdout)

    def restart(self, name):
        self.rpc.supervisor.stopProcess(name)
        self.rpc.supervisor.startProcess(name)

    def _get_process_rss(self, ppid):
        """Get cumulative RSS used by process and all its children.
        """
        mem_total = self.mem_total
        mem_res_sum = 0
        pids = list(self._get_pids(ppid))
        for pid in pids:
            stat = open('/proc/' + str(pid) + '/stat').read().split()
            comm = stat[1][1:-1]
            rss = int(stat[23])
            mem_res = rss * (mmap.PAGESIZE/1024)
            mem_res_sum = mem_res_sum + mem_res

        mem_usage = round(100 * (mem_res_sum / mem_total), 2)
        return mem_usage

    def _get_pids(self, ppid, pids=()):
        # get all children pids
        pid = ppid
        children_path = '/proc/' + str(pid) + '/task/' + str(pid) + '/children'
        if not pids:
            pids = (ppid,)
            if not os.path.isfile(children_path) or open(children_path).read() == '':
                return pids
        children_pids = open(children_path).read().split()
        for pid in children_pids:
            pids = pids + (pid,)
            pids = _get_pids(pid, pids)
        return pids


def _make_argument_parser():
    parser = argparse.ArgumentParser(
        description='Run memory check program.')

    parser.add_argument('-g', '--process-group', dest='process_group',
                        type=str, default=None,
                        help='Supervisor process group name.')
    parser.add_argument('-n', '--process-name', dest='process_name',
                        type=str, required=True, default=None,
                        help='Supervisor process name. Process group argument is ignored if this ' +
                             'is passed in')
    parser.add_argument('-maxpercent', '--maxpercent', dest='maxpercent',
                        type=int, required=True, default=None,
                        help='Max memory usage percent, 0-100.')

    return parser

def main():
    arg_parser = _make_argument_parser()
    args = arg_parser.parse_args()

    mem_total = _get_meminfo()
    process_name = args.process_name
    mem_maxrate = args.maxpercent
    memcheck = MemCheck(process_name=process_name,
                    mem_total=mem_total,
                    mem_maxrate=mem_maxrate)

    memcheck.rpc = childutils.getRPCInterface(os.environ)
    memcheck.runforever()

if __name__ == '__main__':
    main()
