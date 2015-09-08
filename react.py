#!/usr/bin/env python
#
# Originally created by Alexander Bernauer ( https://github.com/copton/react )
# Forked by Nick Stephens to add ability to exclude file patterns, include logging options, and daemonize
#
# example: ./react.py -p '*' -x '^.+?\.sw.+?$' /var/named/zones/ /usr/local/bin/pushCMDB.sh
# this will look for any file changes except those that match known vi swap filenames (.swpx), and then runs the pushCMDB script
#

import os
import os.path
from pyinotify import WatchManager, IN_DELETE, IN_CREATE, IN_CLOSE_WRITE, ProcessEvent, Notifier
import daemon
import subprocess
import logging
import sys
import re
import argparse
import fnmatch

class PatternAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, fnmatch.translate(values))

parser = argparse.ArgumentParser(description='Launch a script if specified files change.')
parser.add_argument('directory', help='the directory which is recursively monitored')
parser.add_argument('-x', '--exclude', required=False, dest="exclude", help='files matching this regular expression will be ignored')

group = parser.add_mutually_exclusive_group()
group.add_argument('-r', '--regex', required=False, default=".*", help='files only trigger the reaction if their name matches this regular expression')
group.add_argument('-p', '--pattern', required=False, dest="regex", action=PatternAction, help='files only trigger the reaction if their name matches this shell pattern')


parser.add_argument("script", help="the script that is executed upon reaction")

class Options:
    __slots__=["directory", "regex", "exclude", "script"]

options = Options()
args = parser.parse_args(namespace=options)

class Reload (Exception):
    pass

class Process(ProcessEvent):
    def __init__(self,  options):
        self.regex = re.compile(options.regex)
        self.exclude = re.compile(options.exclude)
        self.script = options.script

    def process_IN_CREATE(self, event):
        target = os.path.join(event.path, event.name)
        if self.regex.match(target):
            if not self.exclude.match(target):
                args = self.script.replace('$f', target).split()
                logging.info("CREATE detected at " + target + " - executing script: " + " ".join(args) )
                subprocess.call(args)

    def process_IN_DELETE(self, event):
        target = os.path.join(event.path, event.name)
        if self.regex.match(target):
            if not self.exclude.match(target):
                args = self.script.replace('$f', target).split()
                logging.info("DELETE detected at " + target + " - executing script: " + " ".join(args) )
                subprocess.call(args)
        raise Reload()

    def process_IN_CLOSE_WRITE(self, event):
        target = os.path.join(event.path, event.name)
        if self.regex.match(target):
            if not self.exclude.match(target):
                args = self.script.replace('$f', target).split()
                logging.info("CLOSE_WRITE detected at " + target + " - executing script: " + " ".join(args) )
                subprocess.call(args)


def reactor():
    logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(message)s',
                    filename= logFile,
                    filemode='w')
    while True:
        wm = WatchManager()
        process = Process(options)
        notifier = Notifier(wm, process)
        mask = IN_DELETE | IN_CREATE | IN_CLOSE_WRITE
        wdd = wm.add_watch(options.directory, mask, rec=True)
        try:
            while True:
                notifier.process_events()
                if notifier.check_events():
                    notifier.read_events()
        except Reload:
            pass
        except KeyboardInterrupt:
            notifier.stop()
            break

def run():
    with daemon.DaemonContext():
        reactor()

if __name__ == "__main__":
    logFile = '/tmp/react.log'
    run()
