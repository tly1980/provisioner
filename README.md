Provisioner - A provision automation tool
=========================================

A simple script sync up remote a remote folder to local and exectues them automatically.

It utilizes the sync/rsync features of awscli tool (for S3) and gsutil tool (for Google Storage), so any changes on remote folder can trigger the sync up and execution.
It can be used for initial provisiong and auto-update for your server.

Example
=======

supposed you have a S3 bucket named "my_bucket" with following folder structure.

```
s3://my_bucket/
	a/
		run.sh
		run1.py
```

run.sh 
```bash
#!/bin/bash

echo "haha"
```

run1.py
```python
#!/usr/bin/env python

print "python haha"
```

And if you run

```
provisioner.py s3://my_bucket/a a
```

It would be download those files to local folder `a` and execute them in alphabetical order.
```
provisioner.py s3://my_bucket/a a
2015-10-10 17:37   sync   INFO   syncing start
2015-10-10 17:37   sync   INFO   sh_call: aws s3 sync s3://my_bucket/a /Users/me/a  --delete
download: s3://my_bucket/a/run1.py to a/run1.py
download: s3://my_bucket/a/run.sh to a/run.sh

2015-10-10 17:37   sync   INFO   searching trigger on /Users/me/a with pattern: ['*run*.py', '*run*.sh']
2015-10-10 17:37   sync   INFO   sh_call: chmod u+x /Users/me/a/run.sh
2015-10-10 17:37   sync   INFO   sh_call: /Users/me/a/run.sh
haha

2015-10-10 17:37   sync   INFO   sh_call: chmod u+x /Users/me/a/run1.py
2015-10-10 17:37   sync   INFO   sh_call: /Users/me/a/run1.py
python haha

2015-10-10 17:37   sync   INFO   sync finished [s3://my_bucket/a => a]
```

Useful options:
===============

`--forever` enables it update forever. 

`--interval` specifies the interval in seconds, aka how long does it sleeps between each sync.

`--patterns` specifies the executable patterns in glob format, and only those match the patterns would be executed.

Installation
============
Just donwload the provisioner.py and place it /usr/bin or whatever make sense to you.

Running it
==========

If you want to use it for auto-update, consider use [supervisord](http://supervisord.org) or other daemon-lize tool with it.

Security consideration
======================

It is your responsility to have your S3 / GS secret secured. If other people hack in to your cloud bucket, they can ingests trojans to your box.

Strongly suggest you go through the code and make sure that I haven't place any trojans to it.


PS: Google storage support is coming up.
