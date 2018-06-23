#!/bin/sh
BASEDIR=$(dirname "$0")
. ${BASEDIR}/utils.sh
python_version=$(python2 -V)
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
    if ! [ -x '/usr/bin/pip' ]; then 
        action pip "for ${green}${python_version}${reset_color} not found, so installing from ${brown}apt${reset_color}"
        apt-get -y install python-pip | tee ${log_dir}/bootstrap.log
    else
        skip pip install
    fi

    if [ -x '/usr/bin/pip' ] && ! pip show pipenv | grep [V]ersion;then
        action pipenv "installing using ${brown}pip${reset_color}"
        pip install --user pipenv | tee ${log_dir}/bootstrap.log
    else
        skip pipenv install
    fi
}

clean()
{
    if [ -x '/usr/bin/git' ] || pip show pipenv | grep [V]ersion || [ -d '/opt/ycmt' ];then     ## check if git exist if not install it
        if [ -x '/usr/bin/git' ]; then
            apt-get -y remove git 1>>${log_dir}/bootstrap.log
            [ $? -eq 0 ] && action git 'removed using apt-get -y autoremove git command'
        fi

        ## UnInstall/Remove pip for v2.7
        if pip show pipenv | grep [V]ersion; then 
            pip -y uninstall pipenv 1>>${log_dir}/bootstrap.log
            [ $? -eq 0 ] && action pipenv "uninstalled using ${brown}pip${reset_color}"
            if [ $? -eq 0 ]; then
                apt-get -y remove python-pip
                [ $? -eq 0 ] && action pip "for ${green}${python_version}${reset_color} will be removed"
            fi
        fi

        ## finally removing ycmt project folder
        if [ -d '/opt/ycmt' ] || [ -d '/tmp/ycmt' ];then 
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
