from fudf.udf_setup import setup_udf_lib,compile_udflib,parse_source_files
import warnings
import logging
from pathlib import Path
import os
import datetime
import fudf.config as config
try:
    import fudf.private_config as pconfig
except (ModuleNotFoundError,ImportError):
    warnings.warn("private_config.py not found. Please create one with your username and password for the cluster.")
    pconfig = None

from argparse import ArgumentParser,ArgumentError
import configparser

import shutil 
import subprocess
config.CWD_ = os.getcwd()
config.LOG_FILE = Path(config.CWD_).joinpath(config.LOG_FNAME_)

if os.path.exists(config.LOG_FILE):
    os.remove(config.LOG_FILE)

logger = logging.getLogger(str(config.LOG_FILE))

import getpass
import keyring
from keyrings.alt import file


kr = file.EncryptedKeyring()
kr.file_path = str(Path(__file__).parent.joinpath(config.KEY_FILE_))
keyring.set_keyring(kr)

#setup logging
timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
logging.basicConfig(filename = str(config.LOG_FILE),level = logging.INFO,
                    format='%(asctime)s %(levelname)-8s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

def do_interactive(args):
    # 1. Retrieve or prompt for stored password
    user = args.user
    pw = keyring.get_password('fudf', user)
    if pw is None:
        pw = getpass.getpass(f"Password for {user}@login-phoenix-rh9.pace.gatech.edu: ")
        keyring.set_password('fudf', user, pw)

    # 2. Forward all flags except 'user', 'hp', 'command', 'func' to salloc
    flags = []
    for key, val in vars(args).items():
        if key in ('command', 'func', 'user', 'hp'):
            continue
        if val is None:
            continue
        flags.append(f"--{key}={val}")
    salloc_cmd = "salloc " + " ".join(flags)

    # 3. Change to home/project directory if provided
    if args.hp:
        remote_cmd = f"cd {args.hp} && {salloc_cmd}"
    else:
        remote_cmd = salloc_cmd

    # 4. SSH into remote and run salloc
    ssh_target = f"{args.user}@login-phoenix-rh9.pace.gatech.edu"
    sshpass = shutil.which('sshpass')
    if sshpass:
        cmd = [sshpass, '-p', pw, 'ssh', '-t', ssh_target, remote_cmd]
    else:
        print("Warning: sshpass not found—falling back to manual SSH login.")
        cmd = ['ssh', '-t', ssh_target, remote_cmd]

    subprocess.run(cmd)


def do_make(args):
    # Branch on config vs CLI
    if args.config:
        # Validate config file exists and extension
        if not os.path.isfile(args.config) or not args.config.endswith('.config'):
            raise ArgumentError(None, f"Invalid config file: {args.config}")
        cp = configparser.ConfigParser()
        cp.read(args.config)
        if 'udf' not in cp:
            raise ArgumentError(None, f"Section [udf] missing in {args.config}")
        cfg = cp['udf']
        # Required keys
        missing = [k for k in ('source_files','arch','sim_type','fluent_path') if k not in cfg or not cfg[k].strip()]
        if missing:
            raise ArgumentError(None, f"Missing key(s) in config: {', '.join(missing)}")
        source_files = parse_source_files(cfg['source_files'])
        arch          = cfg['arch'].strip()
        sim_type      = cfg['sim_type'].strip()
        fluent_path   = cfg['fluent_path'].strip()
        udf_path      = cfg.get('udf_path','libudf').strip()
        gcc_path      = cfg.get('gcc_path', None)
    else:
        # Validate CLI parameters
        required = {
            'source_files': args.source_files,
            'arch': args.arch,
            'sim_type': args.sim_type,
            'fluent_path': args.fluent_path,
        }
        missing = [name for name, val in required.items() if not val]
        if missing:
            raise ArgumentError(None,
                f"Missing required parameter(s): {', '.join(missing)}. Use 'fudf make -h' for details.")
        source_files = parse_source_files(args.source_files)
        arch          = args.arch
        sim_type      = args.sim_type
        fluent_path   = args.fluent_path
        udf_path      = args.udf_path
        gcc_path      = args.gcc_path

    logger.info('source files: %s',source_files)    
    logger.info('arch: %s',arch)
    logger.info('sim_type: %s',sim_type)
    logger.info('fluent_path: %s',fluent_path)
    logger.info('udf_path: %s',udf_path)
    logger.info('gcc_path: %s',gcc_path)

    logger.info('Setting up UDF library')
    setup_udf_lib(source_files, arch, sim_type, fluent_path, udf_path, gcc_path)
    logger.info('Compiling UDF library')
    compile_udflib(udf_path, arch)


def do_move(args):
    # placeholder for future functionality
    logger.info('move subcommand called with: %s', args)


def main():
    parser = ArgumentParser(prog='fudf')
    subs = parser.add_subparsers(dest='command', required=True)

    #make
    mk = subs.add_parser('make', help='setup and compile UDF library')
    mk.add_argument('--config', type=str, help='path to .config file')
    mk.add_argument('--source_files', type=str, help='list of source files, e.g. "[a.c,b.c]"')
    mk.add_argument('--fluent_path', type=str, help='path to Fluent installation')
    mk.add_argument('--arch', type=str, help='system architecture')
    mk.add_argument('--sim_type', type=str, help='simulation type (e.g. 3ddp,2ddp)')
    mk.add_argument('--udf_path', type=str, default='libudf', help='name of the udf library')
    mk.add_argument('--gcc_path', type=str, default=None, help='path to gcc if custom')
    mk.set_defaults(func=do_make)

    #move
    mv = subs.add_parser('move', help='move files (future)')
    mv.set_defaults(func=do_move)

    #interact/interactive/int
    inter = subs.add_parser(
        'int', aliases=['interactive', 'interact'],
        help='SSH into the cluster and allocate an interactive Slurm session'
    )
    inter.add_argument('--nodes',   type=int,   required=False, help='number of nodes',default = config.NODES_)
    inter.add_argument('--ntasks',  type=int,   required=False, help='number of tasks',default = config.NTASKS_)
    inter.add_argument('--time',    type=str,   required=False, help='time limit, e.g. 8:00:00',default = config.TIME_)

    inter.add_argument('--hp',      type=str,   default=None,  help='home/project dir on remote')
    user,account,queue = None,None, None
    if pconfig:
        try:
            user = pconfig.USER_
        except AttributeError:
            pass
        
        try:
            account = pconfig.ACCOUNT_
        except AttributeError:
            pass

        try:
            queue = pconfig.QUEUE_
        except AttributeError:
            pass

        
    if account is None: 
        inter.add_argument('--account',  type=str,   required=True, help='Slurm account')
    else:
        inter.add_argument('--account',  type=str,   required=False, help='Slurm account',default = account)
    
    if user is None:
        inter.add_argument('--user',    type=str,   required=True, help='username for SSH')
    else:
        inter.add_argument('--user',    type=str,   required=False, help='username for SSH',default = user)
    

    inter.set_defaults(func=do_interactive)

    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()

