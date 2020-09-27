import os, re
from pathlib import Path
from conans import ConanFile, CMake, tools

class NginxConan(ConanFile):
    name = "nginx"
    version = "1.19.2"
    license = "BSD-2-Clause"
    url = "https://github.com/arenoros/conan-nginx"
    description = "nginx server"
    settings = "os", "compiler", "build_type", "arch"
    options = {
        "shared": [True, False],
        "with_pcre": [True, False]
    }
    default_options = {
        "shared": False,
        "with_pcre": True
    }
    generators = "compiler_args"
    _source_dir = 'src_dir'
    _install_dir = 'out'

    requires = "zlib/1.2.11", "openssl/1.1.1f"

    def build_requirements(self):
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

        out_dir = Path(self._install_dir).resolve()
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

    def configure(self):
        del self.settings.compiler.libcxx
        del self.settings.compiler.cppstd   

    def source(self):
        git = tools.Git(folder=self._source_dir)
        git.clone("https://github.com/Arenoros/nginx.git", "master", shallow=True)

    def build(self):
        self.output.info(os.getcwd())
        self.all_flags = tools.load("conanbuildinfo.args")
        self.linux_build()

    def package(self):
        self.copy("*", src=self._install_dir, dst="nginx", keep_path=True)
    

    # def package_info(self):
    #     self.env_info.PATH.append(os.path.join(self.package_folder, "bin"))