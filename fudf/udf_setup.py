from pathlib import WindowsPath,PosixPath, PurePath
import sys
import warnings
from functools import cached_property
import os
import shutil
from typing import List, Tuple, Union, Callable
import configparser
from argparse import ArgumentParser
from collections import deque
import stat
import fudf.config as config
import subprocess
import logging

_PATH = PosixPath if sys.platform == 'linux' or sys.platform == 'posix' else WindowsPath
logger = logging.getLogger(str(config.LOG_FILE))

def find_fluent_dir(path: PurePath) -> PurePath:

    for p in path.iterdir():
        if 'fluent' in p.name and path.is_dir():
            return p

def validate_fluent_dir(path: PurePath) -> PurePath:

    while path.name != 'fluent':
        path = path.parent

    return path

def safe_make(path: PurePath):
    if path.exists():
        warnings.warn(f'Folder with name: {str(path)} already exists - this will overwrite the current contents')
    else:
        path.mkdir(exist_ok = True)

def safe_copy(src: str,
              target: str):

    if os.path.exists(target):
        warnings.warn(f'file: {target} exists, overwriting')
        if os.path.isdir(target):
            shutil.rmtree(target)
        else:
            os.remove(target)
    
    shutil.copy2(src,target)

class UDFLib:

    def __init__(self,name: str,
                      arch: str,
                      sim_type: str):

        self.name = name
        self.path = _PATH(name)
        self.arch = arch
        self.sim_type = sim_type
    
    @cached_property
    def src_path(self) -> PurePath:
        return self.path.joinpath('src/')
    
    @cached_property
    def arch_path(self) -> PurePath:
        return self.path.joinpath(self.arch)
    
    @cached_property
    def node_path(self) -> PurePath:
        return self.arch_path.joinpath(self.sim_type + '_node/')
    
    @cached_property
    def host_path(self) -> PurePath:
        return self.arch_path.joinpath(self.sim_type + '_host/')
    
    def make_folders(self):
        for p in [self.path,self.src_path,self.arch_path,self.node_path,self.host_path]:
            safe_make(p)

class FluentUDFPath:

    def __init__(self,name: str):

        self.home = validate_fluent_dir(_PATH(name))
        self.path = find_fluent_dir(self.home).joinpath('src','udf')

    @cached_property
    def makefile_udf2(self) -> str:
        return str(self.path.joinpath('makefile.udf2'))
    
    @cached_property
    def makefile_udf(self) -> str:
        return str(self.path.joinpath('makefile.udf'))

    @cached_property
    def user_udf(self) -> str:
        return str(self.path.joinpath('user.udf'))

def move_fluent_files(fluent_udf: FluentUDFPath,
                      udf_lib: UDFLib):
    
    #move makefile.udf2
    safe_copy(str(fluent_udf.makefile_udf),
              str(udf_lib.src_path.joinpath('makefile')))
    
    #move makefile.udf1
    safe_copy(str(fluent_udf.makefile_udf2),
              str(udf_lib.path.joinpath('makefile')))
    
    #move user.udf
    safe_copy(str(fluent_udf.user_udf),
              str(udf_lib.host_path.joinpath('user.udf')))
    
    safe_copy(str(fluent_udf.user_udf),
              str(udf_lib.node_path.joinpath('user.udf')))
    
def move_src_files(udf_lib: UDFLib,
                   src_files: List[str]):
    
    for file in src_files:
        name = _PATH(file).name
        safe_copy(file,str(udf_lib.src_path.joinpath(name)))

def keep_permissions(func: Callable):

    def wrapped(file_name: str,
                *args,
                **kwargs):
        
        mode = os.stat(file_name)[stat.ST_MODE]
        func(file_name,*args,**kwargs)
        os.chmod(file_name,mode)
    
    return wrapped

@keep_permissions
def modify_user_udf(file_name: str,
                    cfiles: List[str],
                    hfiles: List[str],
                    fluent_path: FluentUDFPath):

    with open(file_name,'r') as file:
        text = deque(file.readlines())
    
    new_text = []
    while text:
        line = text.popleft()
        if 'CSOURCES' in line:
            line = 'CSOURCES=' + ' '.join(cfiles) if cfiles else '' + '\n'
        if 'HSOURCES' in line:
            line = 'HSOURCES=' + ' '.join(hfiles) if hfiles else '' + '\n'
        if 'FLUENT_INC' in line:
            line = 'FLUENT_INC=' + str(fluent_path.home) + '\n'

        new_text.append(line)
    
    with open(file_name,'w') as file:
        file.write(''.join(new_text))
    
@keep_permissions
def modify_make2(file_name: str,
                 gcc_path: str):
    
    with open(file_name,'r') as file:
        text = deque(file.readlines())
    
    new_text = []
    while text:
        line = text.popleft()
        if 'all:' == line.strip()[:4]:
            new_text.append('CXX=' + gcc_path + '\n')
            new_text.append('export CXX\n')
            new_text.append('\n')
        
        new_text.append(line)
    
    with open(file_name,'w') as file:
        file.write(''.join(new_text))

@keep_permissions
def modify_make1(file_name: str):
    with open(file_name,'r') as file:
        text = deque(file.readlines())
    
    new_text = []
    while text:
        line = text.popleft()
        if line.strip() == 'CC=cc':
            line = 'CC?=cc\n'
        
        new_text.append(line)
    
    with open(file_name,'w') as file:
        file.write(''.join(new_text))

def modify_files(udf_lib: UDFLib,
                 fluent_path: FluentUDFPath,
                 src_files: List[str],
                 gcc_path: Union[str,None]):
    
    cfiles = [file for file in src_files if os.path.splitext(file)[1] == '.c']
    hfiles = [file for file in src_files if os.path.splitext(file)[1] == '.h']
    modify_user_udf(str(udf_lib.host_path.joinpath('user.udf')),cfiles,hfiles,fluent_path)
    modify_user_udf(str(udf_lib.node_path.joinpath('user.udf')),cfiles,hfiles,fluent_path)
    if gcc_path:
        modify_make2(str(udf_lib.path.joinpath('makefile')),gcc_path)
    
    modify_make1(str(udf_lib.src_path.joinpath('makefile')))


def parse_source_files(src_string: str) -> List[str]:
    src_string = src_string.strip()
    # strip brackets if present
    if src_string.startswith('[') and src_string.endswith(']'):
        content = src_string[1:-1].strip()
    else:
        content = src_string.strip()
    # split on commas, strip whitespace, ignore empty
    files = [item.strip().strip("'").strip('"') for item in content.split(',') if item.strip()]
    return files

def is_config_creation() -> bool:
    """
    check if the first argument exists and is a file with .config extension
    to determine if we are creating the udflibdf from a config file
    """
    parser = ArgumentParser()
    
    parser.add_argument('config')
    args = parser.parse_args()

    return os.path.exists(args.config) and os.path.isfile(args.config) and os.path.splitext(args.config)[1] == '.config'

def setup_udf_lib(source_files: List[str],
                 arch: str,
                 sim_type: str,
                 fluent_path: str,
                 udf_path: str,
                 gcc_path: str) -> None:

    fudfp = FluentUDFPath(fluent_path)
    udflib = UDFLib(udf_path,arch,sim_type)

    #1. make folders
    udflib.make_folders()

    #2. move files
    move_fluent_files(fudfp,udflib)
    move_src_files(udflib,source_files)

    #3. modify files
    #   a. chance Cc=cc -> CC?=cc in makefile
    #   b. set headers and source files in make files
    #   c. set CXX = gcc_path in makefile and export
    #   d. Set FLUENT_INC_PATH

    modify_files(udflib,fudfp,source_files,gcc_path)


def compile_udflib(udf_path: str, arch: str):
    try:
        result = subprocess.run(
            ["make", f"FLUENT_ARCH={arch}"],
            cwd=udf_path,
            stdout=config.LOG_FILE.open("a"),
            stderr=subprocess.STDOUT,
            check=True
        )
    except subprocess.CalledProcessError as e:
        logger.error("`make` failed (exit %d). See %s for details.", e.returncode, config.LOG_FILE)
        raise
    else:
        logger.info("`make` completed successfully; output appended to %s", config.LOG_FILE)






    
