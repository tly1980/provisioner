#!/usr/bin/env python

'''
The MIT License (MIT)

Copyright (c) [2015] [Tom Tang]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

import os
import subprocess
import logging
import argparse
import sys
import fnmatch
import time
import datetime
import json

AP = argparse.ArgumentParser("provisioner", description="""Auto-provisioning tool.
Sync a remote folder to local,
and execute the scripts in the folder.
""")
AP.add_argument("cloud_src", type=str, help="Remote URL of where you want to watch")
AP.add_argument("dst", type=str, help="Where you want to sync to")
AP.add_argument("--patterns",
    nargs="+", default=["*run*.py", "*run*.sh"], 
    help="The pattern of trigger. Supports glob format.")
AP.add_argument("--forever", default=False, action="store_true", 
    help="It will loop forever with this flag set.")
AP.add_argument("--interval", default=15, type=int, 
    help="interval between each watch. Default is 15 seconds")

AP.add_argument("--state", default="/var/run/provisioner_state.json", type=str, 
    help="location to save state")


logging.basicConfig(level=logging.INFO,
        format='%(asctime)-18s %(name)-6s %(levelname)-6s %(message)s',
        datefmt='%Y-%m-%d %H:%M')

logger = logging.getLogger("sync")

STATE = {}
STATE_PATH = ''


def sh_call(cmd, shell=True, verbose=True):
    try:
        logger.info("sh_call: %s" % cmd)
        txt = subprocess.check_output(cmd, shell=shell)
        if verbose and txt:
            print >> sys.stderr, txt
        return txt, 0
    except subprocess.CalledProcessError, e:
        logger.error("failed@ : %s" % cmd, exc_info=True)
        return None, e.returncode

def has_change(txt):
    for i in ["download:", "delete:", "Copying", "Removing"]:
        if i in txt:
            return True
    return False

def load_state(path):
    global STATE
    logger.info("loading state from %s", path)
    try:
        if os.path.exists(path):
            with open(path, "rb") as f:
                STATE = json.load(f)
    except Exception, e:
        logger.exception("Failed to load state from %s", path)
    return STATE

def persist_state(path):
    logger.info("persisting state to %s", path)
    with open(path, "wb") as f:
        json.dump(STATE, f, indent=2)

def file_checksum(path):
    txt, ret = sh_call("shasum %s" % path)
    if txt:
        return txt.split(" ")[0]
    return None

def main(args):
    global STATE_PATH
    src = args.cloud_src
    dst = os.path.abspath(args.dst)
    STATE_PATH = args.state
    load_state(STATE_PATH)

    is_s3 = True if src.startswith("s3://") else False

    if dst.startswith("s3://") or dst.startswith("gs://"):
        sys.exit("dst has to be local.", -1)

    if not os.path.exists(dst):
        os.makedirs(dst, 0700)

    if src.startswith("s3://"):
        sync_cmd="aws s3 sync {src} {dst}  --delete".format(
            src=src, dst=dst)

    elif src.startswith("gs://"):
        sync_cmd="gsutil rsync -d {src} {dst}".format(
            src=src, dst=dst)
    else:
        sys.exit("cloud_src has to be either s3 or gs", -1)

    i = 0
    while True:
        i += 1
        logger.info("syncing start")

        txt, retcode = sh_call(sync_cmd)
        if retcode != 0:
            logger.warn("remote sync failed")
            # test if it is last run, and fail fast
            if not args.forever:
                sys.exit(retcode)
        all_good = True
        if is_s3:
            if txt and has_change(txt):
                all_good = trigger(dst, args.patterns)
                if not all_good:
                    logger.warn("Error on executing triggers [location=%s]", args.dst)
        else:
            # As gs doesn't output to stdio for now
            # we just assume that it needs to run the trigger all the time
            all_good = trigger(dst, args.patterns)
            if not all_good:
                logger.warn("Error on executing triggers [location=%s]", args.dst)

        if not args.forever:
            break
        logger.info("sleep %s secs ...", args.interval)
        time.sleep(args.interval)
    logger.info("sync finished [%s => %s]" %(src, args.dst))
    sys.exit(0)

def match(fname, patterns):
    for p in patterns:
        if fnmatch.fnmatch(fname, p):
            return True
    return False

def can_run(fname, checksum):
    exe = STATE.setdefault('executed', {})

    if fname not in exe:
        return True

    if exe[fname]['checksum'] != checksum:
        return True

    return False

def set_ran(fname, checksum):
    exe = STATE.setdefault('executed', {})
    exe[fname] = {'checksum': checksum, 'timestamp': str(datetime.datetime.now())}

    persist_state(STATE_PATH)


def trigger(dst, patterns):
    current_dir = os.path.abspath(os.getcwd())
    logger.info("searching trigger on %s with pattern: %s ", 
        os.path.join(dst), patterns)
    all_good = True
    for root, dirs, files in os.walk(dst):
        files2 = sorted(files)
        # cheange the working directory 
        # to where the script exists
        if not root.startswith('/'):
            os.chdir(os.path.join(current_dir, root))
            logger.info("changed working dir to: %s", os.getcwd())

        for f in files2:
            cmd = os.path.join(current_dir, root, f)
            if match(f, patterns):
                checksum = file_checksum(f)
                if can_run(f, checksum):
                    sh_call("chmod u+x %s" % cmd)
                    # set ran regardless 
                    # the script is ran successfully or not
                    set_ran(f, checksum)
                    txt, retcode = sh_call(cmd)
                    if retcode != 0:
                        all_good = False
                else:
                    logger.info("skipping [%s] as it was already executed.", f)
    # change back
    os.chdir(current_dir)
    return all_good

if __name__ == "__main__":
    main(AP.parse_args())
