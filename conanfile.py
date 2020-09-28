import os, re
import platform
from pathlib import Path
from conans import ConanFile, CMake, tools, AutoToolsBuildEnvironment

class NginxConfig():
    def __init__(self, cc, prefix):
        self.cflags = []
        self.ldflags = []
        self.cc = cc
        self.prefix = prefix
        self.modules = []

    def add_mod(self, mod):
        for mod in mods:
            self.modules.append(f'--with-{mod}')
        #self.modules.append(f'--with-{mod}')
    
    def disable_mod(self, *mods):
        for mod in mods:
            self.modules.append(f'--without-{mod}')
        #self.modules.append(f'--without-{mod}')

    def custom_mod(self, *argv):
        for path in argv:
            self.modules.append(f'--add-module={path}')

    def cflag(self, *opts):
        self.cflags += opts

class NginxConan(ConanFile):
    name = "nginx"
    version = "1.19.2"
    license = "BSD-2-Clause"
    url = "https://github.com/arenoros/conan-nginx"
    description = "nginx server"
    settings = "os", "compiler", "build_type", "arch"
    options = {
        "shared": [True, False],
        "with_pcre": [True, False],
        "with_ssl": [True, False]
    }
    default_options = {
        "shared": False,
        "with_pcre": True,
        "with_ssl": True
    }
    generators = "compiler_args"
    _source_dir = 'src_dir'
    _prefix = 'out'

    requires = "zlib/1.2.11", "openssl/1.1.1f"

    def build_requirements(self):
        if tools.os_info.is_windows and not tools.get_env("CONAN_BASH_PATH"):
            self.build_requires("msys2/20200517")
        # if platform.system() == "Windows":
        #     #self.build_requires("mingw_installer/1.0@conan/stable")
        #     self.build_requires("msys2/20190524")
            pass

    def requirements(self):
        if self.options.with_pcre:
            self.requires.add("pcre/[>=8.41]")
        if self.settings.os == 'Android' and int(f'{self.settings.os.api_level}') < 28:
            self.requires.add("ndk-libc-fix/[>=0.2]")

    def linux_build(self):
        lib_re = re.compile(r'(^-l|^-L)')
        cc_re = re.compile(r'(^-Wl,-rpath=|^-L|^-l)') #|^-std=|^-stdlib=
        params = self.all_flags.split()

        libs = ' '.join([flag for flag in params if lib_re.match(flag)])
        if tools.get_env("LDFLAGS"):
            libs = tools.get_env("LDFLAGS") + ' ' + libs


        cc_flags = ' '.join([flag for flag in params if not cc_re.match(flag)])
        if tools.get_env("CFLAGS"):
            cc_flags = tools.get_env("CFLAGS") + ' ' + cc_flags

        out_dir = Path(self._prefix).resolve()
        prefix = f'--prefix={out_dir}'
        crossbuild = f'--crossbuild={self.settings.os}::{self.settings.arch}'

        cc = '--with-cc=$CC' if tools.get_env("CC") else ''

        modules = ['--with-http_v2_module', '--with-http_ssl_module']
        if self.options.with_pcre:
            modules.append('--with-pcre')
            custom_modules = '--add-module=modules/nginx-let-module'
        else:
            modules.append('--without-http_rewrite_module')
        if self.settings.os == 'Linux':
            cc_flags += ' -pthread'
        
        cc_flags=f'--with-cc-opt="{cc_flags}"'
        ld_flags=f'--with-ld-opt="{libs}"'
        cmd = ' '.join([prefix, crossbuild, cc, custom_modules, ' '.join(modules), cc_flags, ld_flags])
        self.output.info(cmd)
        with tools.chdir(self._source_dir):
            self.run(f'./auto/configure {cmd}')
            self.run(f'make -j{tools.cpu_count()}')
            self.run('make install')

    def win_build(self):
        env_build = AutoToolsBuildEnvironment(self, win_bash=True)
        with tools.environment_append(env_build.vars):
            self.run('pwd')
            with tools.chdir(self._source_dir):
                self.run(f'./auto/configure --with-cc=cl --builddir=objs --prefix=../out', win_bash=True)
        pass

    def configure(self):
        del self.settings.compiler.libcxx
        del self.settings.compiler.cppstd

        cc = tools.get_env("CC")
        if not cc and platform.system() == 'Windows':
            cc = 'cl'

        self.ngx = NginxConfig(cc, self._prefix)
        
        if self.options.with_ssl:
            self.ngx.add_mod('http_v2_module')
            self.ngx.add_mod('http_ssl_module')

        if self.options.with_pcre:
            self.ngx.add_mod('pcre')
            self.ngx.custom_mod('modules/nginx-let-module')
        else:
            self.ngx.disable_mod('http_rewrite_module')

        if self.settings.os == 'Linux':
            cc_flags += ' -pthread'

    def source(self):
        git = tools.Git(folder=self._source_dir)
        git.clone("https://github.com/Arenoros/nginx.git", "master", shallow=True)

    def build(self):
        self.output.info(os.getcwd())
        self.all_flags = tools.load("conanbuildinfo.args")
        if platform.system() != 'Windows':
            self.linux_build()
        else:
            self.win_build()

    def package(self):
        self.copy("*", src=self._prefix, dst="nginx", keep_path=True)
    

    # def package_info(self):
    #     self.env_info.PATH.append(os.path.join(self.package_folder, "bin"))