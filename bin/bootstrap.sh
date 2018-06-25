#!/bin/sh

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
log_file=${log_dir}/bootstrap.log

if du -sh ${log_file} | grep M; then
    cat /dev/null > ${log_file}
fi

echo "See ${log_file} for more details"

date_time=$(date --iso-8601=seconds)
python_version=$(python3 -V 2>&1)

## Skip function to echo any events realted to skipped prep events as they either exisit in most cases
skip()
{
    msg="${brown}${1}${reset_color} ${2}"
    echo "${date_time} ${green}Skipping..${reset_color} ${msg}"
}

## Prep function to echo any events related to install/setup of dependencies
action()
{
    msg="${brown}${1}${reset_color} ${2}"
    echo "${date_time} ${green}Preping..${reset_color} ${msg}"
}
output()
{
    echo $@
}

## Do all the Bootstrp Setup
prep()
{
     
    ## check if git exist if not install it and clone the repository to tmp and rsync it
    if ! [ -x '/usr/bin/git' ];then 
        action git 'apt install'
        ## install git
        # resynchronize the package index files from their sources
        apt-get update >>$log_file 2>&1
        apt-get -y install git >>$log_file 2>&1
    else
        skip git install
    fi

    if ! [ -d '/opt/ycmt' ]; then
            action ycmt "cloning from ${brown}git${reset_color} source"
             ## cloning ycmt tool from SCM(https://github.com/gdv-deepak/ycmt)
            git clone https://github.com/gdv-deepakk/ycmt.git /tmp/ycmt >>$log_file 2>&1
    else
        skip ycmt "source clone as it exists under /opt/ycmt"
    fi
    
    if [ -d '/tmp/ycmt' ];then
        # git pull and rsync the project
        cd /tmp/ycmt; git pull && rsync -arzC . /opt/ycmt
    fi

    ## Preparations for installing Python virtual environment using pipenv, ref: https://docs.pipenv.org
    ## Install pip for v3.4
    if ! [ -f '/usr/bin/pip3' ]; then 
        action pip3 "for ${green}${python_version}${reset_color} not found, so installing from ${brown}apt${reset_color}"
        apt-get -y install python3-pip python3-dev >>$log_file 2>&1
    else
        skip pip install
    fi

    if [ -f '/usr/bin/pip3' ] && ! pip3 show pipenv | grep [V]ersion &> /dev/null;then
        action pipenv "installing using ${brown}pip${reset_color}"
        pip3 install --user pipenv=='11.10.3' >>$log_file 2>&1
        if [ $? -eq 0 ]; then
            cd /opt/ycmt
            /root/.local/bin/pipenv lock
            /root/.local/bin/pipenv sync
            /root/.local/bin/pipenv shell
        fi
    else
        skip pipenv install
    fi
}

## To remove all configuration done through bootstrap process
clean()
{
    ## if any one of following exist remove/uninstall them from system.
    if [ -f '/usr/bin/git' ] || [ -f '/usr/bin/pip3' ] || [ -d '/opt/ycmt' ];then
        if [ -f '/usr/bin/git' ]; then
            apt-get -y remove git >> $log_file 2>&1
            [ $? -eq 0 ] && action git 'removed using apt-get remove'
        fi

        ## UnInstall/Remove pip for v2.7
        if [ -f '/usr/bin/pip3' ] && pip3 show pipenv | grep [V]ersion &>/dev/null ; then 
            pip3 uninstall -y pipenv >>$log_file 2>&1
            [ $? -eq 0 ] && action pipenv "uninstalled using ${brown}pip3${reset_color}"
        fi
        if [ -f '/usr/bin/pip3' ]; then
            apt-get -y remove python-pip python-dev-all >>${log_file} 2>&1
            [ $? -eq 0 ] && action pip3 "for ${green}${python_version}${reset_color} will be removed"
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

## check if argument is passed
if [ $# -eq 1 ]; then
    # to bootstrap either use install (or) setup
    if [ "${1}" = "install" ] || [ "${1}" = 'setup' ] ; then
        prep
    # to remove all bootstrp trace use any of following options
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
