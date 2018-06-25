# ycmt 
yet(another)ConfigurationManagementTool

Table of Contents
=================

* [Design Principles](#design-principles)
* [Basic Architecture](#basic-architecture)
* [In Action Video:](#in-action-video)
* [Supported Language Intrepret](#supported-language-intrepret)
* [Considerations Patterns](#considerations-patterns)
* [config files](#config-files)
* [Consumption Pattern](#consumption-pattern)
* [How to download and setup the tool](#how-to-download-and-setup-the-tool)
* [How to use the tool](#how-to-use-the-tool)
* [Standard Template](#standard-template)
    * [optional config params:](#optional-config-params)
* [Future Integrations in Plan](#future-integrations-in-plan)

TOC created by [gh-md-toc](https://github.com/ekalinin/github-markdown-toc.go)

## Design Principles

- If tool has dependencies not available on a standard Ubuntu instance you may include a [`bootstrap.sh`](https://raw.githubusercontent.com/gdv-deepakk/ycmt/master/bin/bootstrap.sh) program to resolve them
- Tool must provide an abstraction that allows specifying a file's content and metadata (owner, group, mode)
- Tool must provide an abstraction that allows installing and removing Debian packages
- Tool must provide some mechanism for restarting a service when relevant files or packages are updated
- Tool must be idempotent - it must be safe to apply your configuration over and over again

__Having worked on various configuration orchestrator's like Chef, Puppet, Ansible(new) etc.., I tried to incoorporate my learnings(from experince) of those tools in to this tool, so you may find some similarities with state names etc..__

### Basic Architecture
![Architecture](images/ycmt-arch-v01.jpeg?raw=true)


## In Action Video:
https://drive.google.com/file/d/1vqZTs-o5zhg9Sy4b8VM_dH45YJH87Thf/view?usp=sharing

### Supported Language Interpreter
- Python v3.x - as python 2.7.x will be deprecated in future, so decided to do this with Python v3 

## Considerations Patterns
### config files
- **`.ini`** - informal standard for configuration files for some platforms or software. INI files are simple text files with a basic structure composed of sections, properties, and values
- **`.json`** - JavaScript Object Notation or JSON is an open-standard file format that uses human-readable text to transmit data objects consisting of attribute–value pairs and array data types ( choosen )
- **`.yaml`** - is a human-readable data serialization language. It is commonly used for configuration files, but could be used in many applications where data is being stored or transmitted

After experementing I have choosen `.json` over `.ini` and `.yml` because I was able to define the state(policy rules) of a host in most human friendly format with `key:value ` and `array` objects. Having significant experience with `.json` notation of objects I have decided to use it for best interest of time even after spedning few hours on `.ini` and `.yml`, but if I do have future plans to do more on `.ini` (or) `.yml` based configuration for tools like this.

**BTW:** these days as part of my personal projects I am using `.yml` for defining `deployments` of Kubernetes but it also supports `.json` :-) 

### Consumption Pattern
- `default.json` - default policy rules to enforce on every host
- `<short-hostname>.json` - host specific policy rules to enforce for that host only

### How to download and setup the tool
```bash
curl -fsSL 'https://raw.githubusercontent.com/gdv-deepakk/ycmt/master/bin/bootstrap.sh' | sh -s install
```

### How to use the tool
- little help..

```bash
python3 /opt/ycmt/bin/ycmt.py -h
## WARNING ## This program is BETA v0.1, so please pay attention to your policy rules ## WARNING ##
Do you want to continue [Y/n]: Y
usage: ycmt.py [-h] [--verbose] [--conf CONF]

Yet(another)ConfigurationManagementTool - ycmt to deploy and
configure simple services

optional arguments:
  -h, --help            show this help message and exit
  --verbose, -v         increase output verbosity, for more verbosity use -vv
  --conf CONF, -c CONF  path to config file. Default: ./conf/default.json
```
- for verbose output use `-v` for detail verbosity/debug logs increase `-vvv`
```bash
python3 /opt/ycmt/bin/ycmt.py -v
## WARNING ## This program is BETA v0.1, so please pay attention to your policy rules ## WARNING ##
Do you want to continue [Y/n]: Y
## Applying Base Policies of Package Manager, Services, Configs ##
2018-06-24T14:05:53-07:00 checking compliance of package install rules of BASE on this host: host1
2018-06-24T14:05:53-07:00 Skipping..git package install as its installed and in compliance with above policy rule.
2018-06-24T14:05:53-07:00 checking compliance of manage_services rules of BASE on this host: host1
2018-06-24T14:05:53-07:00Skipping..BASE policy rule enforces service: atd state to be STOPPED and it appears all compliance for the policy rule are met.
2018-06-24T14:05:53-07:00 checking compliance of manage_configs rules of BASE on this host: host1
2018-06-24T14:05:53-07:00 Policy ENFORCED../var/www/html/index.html file deleted as per compliance with above policy rule.
```

### Standard Template
`default.json` (default/base policy)
```json
{
    "packages": {
        "update_cache": "False(future as needed)",
        "install": {
            "pkg": "<version - future release will support this currently it will install any latest rc availabe in the repo"
        },
        "remove": [
            "pkg-only"
        ]
    },
    "slack": {
        "channels": []
    },
    "services": {
        "service": "state"
    },
    "configs": {
        "files": [
            "file1",
            "file2"
        ],
        "file1": {
            "source": "files/file1.php",
            "dest": "<destination location on host>",
            "user": "<user>",
            "group": "<group",
            "mode": "< 5 digit mode - 01744>",
            "notify": "<service>:<action>",
            "action": "<create|delete>"
        },
        "file2": {
            "similar to above"
        }
    }
}
```
`<short_hostname>.json` (host specific policy)

- Valid `state` for `service{}` - `started` (or) `stopped` (or) `reloaded`, I didn't add `restarted` as it didn't made sence to add it.
- Valid `action` for `"notify":` in `configs.file[n]` - `reload`, `restart`, `stop` - I kept this native to standard `service` command actions.
- 

#### optional config params:
- `slack[]`
- `remove[]`

### Future Integrations in Plan
- Send event to SLACK ( this is easy implementation and I wanted to do it in v0.1 but as I have spend most of my time with config design I have decided to push this to next release based on interest of time) 
- Send logs to ElasticSearch directly in Structure Format
- Send Metrics to Prometheus regarding deployments stats
