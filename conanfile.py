import os, re
import platform
from pathlib import Path
from conans import ConanFile, CMake, tools, AutoToolsBuildEnvironment
import json

class NginxConfig():
    def __init__(self, cc, prefix, cross):
        self._cflags = []
        self._ldflags = []
        self._cc = cc
        self._cross = cross
        self.prefix = prefix
        self._modules = []
        self._d_modules = []
        self.cc_args = ''

    def add_mod(self, *mods):
        for mod in mods:
            self._modules.append(f'--with-{mod}')
    
    def disable_mod(self, *mods):
        for mod in mods:
            self._modules.append(f'--without-{mod}')

    def custom_mod(self, *argv):
        for path in argv:
            self._modules.append(f'--add-module={path}')

    def add_cflags(self, *opts):
        self._cflags += opts
    
    def add_ldflags(self, *opts):
        self._ldflags += opts

    def set_args(self, args):
        link = re.compile(r'^(-l|-L|-link|/link|-LIBPATH|.*\.lib|.*\.so|.*\.a$)')
        
        for arg in args:
            if link.search(arg):
                self.add_ldflags(arg)
            else:
                self.add_cflags(arg)
        

    @property
    def cflags(self):
        return '--with-cc-opt="' + ' '.join(self._cflags) + '"'

    @property
    def ldflags(self):
        return f'--with-ld-opt="{" ".join(self._ldflags)}"'

    @property
    def modules(self):
        return ' '.join(self._modules)

    @property
    def cross(self):
        return f'--crossbuild={self._cross}'

    @property
    def cc(self):
        return f'--with-cc={self._cc}'

    def cmd(self):
        return ' '.join([f'--conan --prefix={self.prefix}', self.cross, self.cc, self.modules, self.cflags, self.ldflags])


class NginxConan(ConanFile):
    name = "nginx"
    version = "1.19.2"
    license = "BSD-2-Clause"
    url = "https://github.com/arenoros/conan-nginx"
    description = "nginx server"
    settings = "os", "compiler", "build_type", "arch"
    options = {
        "shared": [True, False],
        "with_ssl": [True, False],
        "with_threads": [True, False],
        "with_aio": [True, False]
    }
    default_options = {
        "shared": False,
        "with_ssl": True,
        "with_threads": False,
        "with_aio": False
    }
    generators = "compiler_args"
    _source_dir = 'src_dir'
    _prefix = 'out'
    exports_sources = ["0001-fix-win32-build.patch", "Makefile"]
    requires = "zlib/1.2.11", 'pcre/[>=8.41]'

    def build_requirements(self):
        if tools.os_info.is_windows and not tools.get_env("CONAN_BASH_PATH"):
            self.build_requires("msys2/20200517")

    def requirements(self):
        if self.settings.os == 'Android' and int(f'{self.settings.os.api_level}') < 28:
            self.requires.add("ndk-libc-fix/[>=0.2]")
        if self.options.with_ssl:
            self.requires.add("openssl/1.1.1f")

    def linux_build(self):
        cmd = self.ngx.cmd()
        self.output.info(cmd)
        with tools.chdir(self._source_dir):
            self.run(f'./auto/configure {cmd}')
            self.run(f'make -j{tools.cpu_count()}')
            self.run('make install')

    def win_build(self):
        cmd = self.ngx.cmd()
        self.output.info(cmd)
        env_build = AutoToolsBuildEnvironment(self, win_bash=True)
        with tools.vcvars(self.settings):
            with tools.environment_append(env_build.vars):
                with tools.chdir(self._source_dir):
                    self.run(f'./auto/configure {cmd}', win_bash=True)
                    self.output.info(Path.cwd())
                    self.run(f'nmake')
                    self.run('nmake install')
        pass

    def configure(self):
        del self.settings.compiler.libcxx
        del self.settings.compiler.cppstd
        
        cc = tools.get_env("CC")
        if not cc and platform.system() == 'Windows':
            cc = 'cl'

        self.ngx = NginxConfig(cc, self._prefix, f'{self.settings.os}::{self.settings.arch}')
        if self.options.with_threads:
            self.ngx.add_mod('threads')
        if self.options.with_aio:
            self.ngx.add_mod('file-aio')
        self.ngx.add_mod('http_gunzip_module')
        self.ngx.custom_mod('modules/nginx-let-module')
        if self.options.with_ssl:
            self.ngx.add_mod('http_v2_module')
            self.ngx.add_mod('http_ssl_module')

        if self.settings.os == 'Linux':
            self.ngx.add_cflags('-pthread')
        if self.settings.os == 'Neutrino':
            self.ngx.add_ldflags('-lsocket')

    def source(self):
        git = tools.Git(folder=self._source_dir)
        git.clone("https://github.com/Arenoros/nginx.git", "master", shallow=True)

    def build(self):
        self.output.info(os.getcwd())

        args = tools.load("conanbuildinfo.args").replace('\\', '/').split()

        self.ngx.set_args(args)
        if platform.system() != 'Windows':
            self.linux_build()
        else:
            self.win_build()

    def package(self):
        out_dir = Path(self._source_dir) / self._prefix
        self.copy("*", src=out_dir, dst="nginx", keep_path=True)
    