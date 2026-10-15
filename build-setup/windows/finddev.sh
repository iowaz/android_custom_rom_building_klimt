#!/bin/bash
# print the unformatted 200 GiB disk (the new evox.vhdx)
lsblk -dbno NAME,SIZE,FSTYPE | awk '$2==214748364800 && $3=="" {print $1}'
