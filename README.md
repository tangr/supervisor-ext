# supervisor-ext
supervisor rpcinterface & ctlplugin extensions to get ext options.

A simple [supervisord](http://supervisord.org/) rpcinterface to get
supervisor ext(environment, directory) options.

A simple [supervisord](http://supervisord.org/) ctlplugin to get
supervisor ext(listen ports) infos.


## Installation

Just install via pip or add to your requirements.txt:

    pip install supervisor-ext

## Usage

An example supervisord.conf:

    [rpcinterface:supervisor_ext]
    supervisor.rpcinterface_factory = supervisor_ext.rpcinterface:make_main_rpcinterface

    [ctlplugin:supervisor_ext]
    supervisor.ctl_factory = supervisor_ext.controllerplugin:make_main_controllerplugin
