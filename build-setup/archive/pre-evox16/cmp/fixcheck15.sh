#!/bin/bash
# All existing policy/image checks plus the controlled evox15 additions.
bash /mnt/c/XiaomiBuilds/build-setup/evox/cmp/fixcheck14.sh
python3 -B /mnt/c/XiaomiBuilds/build-setup/evox/fix15/check-image.py
