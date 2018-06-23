#!/bin/sh

## 
# handy color vars for pretty prompts
blue="\033[0;34m"
green="\033[0;32m"
cyan="\033[0;36m"
red="\033[0;31m"
purple="\033[0;35m"
brown="\033[0;33m"
yellow='\033[1;33m'
white="\033[1;37m"
reset_color="\033[0m"
bold_text="\033[1m"

bt=${bold_text}
rst=${reset_color}

log_dir='/var/log/ycmt'

mkdir -p ${log_dir}
date_time=$(date --iso-8601=seconds)