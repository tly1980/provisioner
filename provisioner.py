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


logging.basicConfig(level=logging.INFO,
        format='%(asctime)-18s %(name)-6s %(levelname)-6s %(message)s',
        datefmt='%Y-%m-%d %H:%M')

logger = logging.getLogger("sync")


def sh_call(cmd, shell=True, verbose=True, rd_stderr=False):
    try:
        logger.info("sh_call: %s" % cmd)
        if not rd_stderr:
            txt = subprocess.check_output(cmd, shell=shell)
        else:
            txt = subprocess.check_output(cmd,
                shell=shell, stderr=subprocess.STDOUT)
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

def main(args):
    src = args.cloud_src
    dst = os.path.abspath(args.dst)

    if dst.startswith("s3://") or dst.startswith("gs://"):
        sys.exit("dst has to be local.", -1)

    if not os.path.exists(dst):
        os.makedirs(dst, 0700)

    rd_stderr=False
    if src.startswith("s3://"):
        sync_cmd="aws s3 sync {src} {dst}  --delete".format(
            src=src, dst=dst)

    elif src.startswith("gs://"):
        rd_stderr=True
        sync_cmd="gsutil rsync -d {src} {dst}".format(
            src=src, dst=dst)
    else:
        sys.exit("cloud_src has to be either s3 or gs", -1)

    i = 0
    while True:
        i += 1
        logger.info("syncing start")

        txt, retcode = sh_call(sync_cmd, rd_stderr=rd_stderr)
        if retcode != 0:
            logger.warn("remote sync failed")
            # test if it is last run, and fail fast
            if not args.forever:
                sys.exit(retcode)
        if txt:
            if has_change(txt):
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
                sh_call("chmod u+x %s" % cmd)
                txt, retcode = sh_call(cmd)
                if retcode != 0:
                    all_good = False
    # change back
    os.chdir(current_dir)
    return all_good

if __name__ == "__main__":
    main(AP.parse_args())
