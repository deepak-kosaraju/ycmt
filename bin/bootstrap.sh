#!/bin/sh
BASEDIR=$(dirname "$0")

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

## log directory for bootstrap
log_dir='/var/log/ycmt'
mkdir -p ${log_dir}

date_time=$(date --iso-8601=seconds)
python_version=$(python2 -V 2>&1)
## Update apt package list

## Skip function to print any events realted to skipped prep events as they either exisit in most cases
skip()
{
    msg="${brown}${1}${reset_color} ${2}"
    echo "${date_time} ${green}Skipping..${reset_color} ${msg}" | tee -a ${log_dir}/bootstrap.log
}

## Prep function to print any events related to install/setup of dependencies
action()
{
    msg="${brown}${1}${reset_color} ${2}"
    echo "${date_time} ${green}Preping..${reset_color} ${msg}" | tee -a ${log_dir}/bootstrap.log
}
output()
{
    echo $@
}

prep()
{
     
    ## check if git exist if not install it and clone the repository to tmp and rsync it
    if ! [ -x '/usr/bin/git' ];then 
        action git 'apt install'
        ## install git
        # resynchronize the package index files from their sources
        apt-get update 1>>${log_dir}/bootstrap.log
        apt-get -y install git 
    else
        skip git install
    fi

    if ! [ -d '/opt/ycmt' ]; then
            action ycmt "cloning from ${brown}git${reset_color} source"
             ## cloning ycmt tool from SCM(https://github.com/gdv-deepak/ycmt)
            git clone https://github.com/gdv-deepakk/ycmt.git /tmp/ycmt 1>>${log_dir}/bootstrap.log
    else
        skip ycmt "source clone as it exists under /opt/ycmt"
    fi
    
    if [ -d '/tmp/ycmt' ];then
        # git pull and rsync the project
        cd /tmp/ycmt; git pull && rsync -arzC . /opt/ycmt
    fi

    ## Preparations for installing Python virtual environment using pipenv, ref: https://docs.pipenv.org
    ## Install pip for v2.7
    if ! [ -f '/usr/bin/pip' ]; then 
        action pip "for ${green}${python_version}${reset_color} not found, so installing from ${brown}apt${reset_color}"
        apt-get -y install python-pip | tee -a ${log_dir}/bootstrap.log
    else
        skip pip install
    fi

    if [ -f '/usr/bin/pip' ] && ! pip show pipenv | grep [V]ersion;then
        action pipenv "installing using ${brown}pip${reset_color}"
        pip install --user pipenv | tee -a ${log_dir}/bootstrap.log
    else
        skip pipenv install
    fi
}

clean()
{
    ## if any one of following exist remove/uninstall them from system.
    if [ -f '/usr/bin/git' ] || [ -f '/usr/bin/pip' ] || [ -d '/opt/ycmt' ];then
        if [ -f '/usr/bin/git' ]; then
            apt-get -y remove git 1>>${log_dir}/bootstrap.log
            [ $? -eq 0 ] && action git 'removed using apt-get remove'
        fi

        ## UnInstall/Remove pip for v2.7
        if pip show pipenv | grep [V]ersion; then 
            pip uninstall pipenv 1>>${log_dir}/bootstrap.log
            [ $? -eq 0 ] && action pipenv "uninstalled using ${brown}pip${reset_color}"
            if [ $? -eq 0 ]; then
                apt-get -y remove python-pip
                [ $? -eq 0 ] && action pip "for ${green}${python_version}${reset_color} will be removed"
            fi
        fi

        ## finally removing ycmt project folder
        if [ -d '/opt/ycmt' ];then 
            action ycmt "removed under /opt/ycmt and /tmp/ycmt"
            rm -rf /opt/ycmt /tmp/ycmt
        fi
    else
        output "${green}All CLEAR${reset_color}" "have a nice day.."
        exit 0
    fi
}

if [ $# -eq 1 ]; then
    if [ "${1}" = "install" ] ; then
        prep
    elif [ "${1}" = "uninstall" ] || [ "${1}" = "cleanall" ] || [ "${1}" = "remove" ] || [ "${1}" = "clean" ] ; then
        clean
    else
        echo "${red}Invalid option specificed${reset_color}, valid options are:
        \t${green}${bt}install${rst}
        \t${red}${bt}clean${rst} (or) ${red}${bt}cleanall${rst} (or) ${red}${bt}uninstall${rst} (or) ${red}${bt}remove${rst}"
    fi
else
    echo "${blue}Used one of following valid options to bootstrap:
    \t${green}${bt}install${rst}
    \t${red}${bt}clean${rst} (or) ${red}${bt}cleanall${rst} (or) ${red}${bt}uninstall${rst} (or) ${red}${bt}remove${rst}"
fi
