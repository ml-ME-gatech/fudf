from fudf.udf_setup import setup_udf_lib,compile_udflib,parse_source_files
import logging
from pathlib import Path
import os
import datetime
import fudf.config as config
from argparse import ArgumentParser,ArgumentError
import configparser

config.CWD_ = os.getcwd()
config.LOG_FILE_ = Path(config.CWD_).joinpath(config.LOG_FNAME_)
logger = logging.getLogger(str(config.LOG_FILE))


#setup logging
timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
logging.basicConfig(filename = str(config.LOG_FILE),level = logging.INFO,
                    format='%(asctime)s %(levelname)-8s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')



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

    mk = subs.add_parser('make', help='setup and compile UDF library')
    mk.add_argument('--config', type=str, help='path to .config file')
    mk.add_argument('--source_files', type=str, help='list of source files, e.g. "[a.c,b.c]"')
    mk.add_argument('--fluent_path', type=str, help='path to Fluent installation')
    mk.add_argument('--arch', type=str, help='system architecture')
    mk.add_argument('--sim_type', type=str, help='simulation type (e.g. 3ddp,2ddp)')
    mk.add_argument('--udf_path', type=str, default='libudf', help='name of the udf library')
    mk.add_argument('--gcc_path', type=str, default=None, help='path to gcc if custom')
    mk.set_defaults(func=do_make)

    mv = subs.add_parser('move', help='move files (future)')
    mv.set_defaults(func=do_move)

    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()

