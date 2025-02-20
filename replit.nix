{pkgs}: {
  deps = [
    pkgs.rustc
    pkgs.pkg-config
    pkgs.libxcrypt
    pkgs.libiconv
    pkgs.cargo
    pkgs.imagemagick
    pkgs.pango
    pkgs.harfbuzz
    pkgs.glib
    pkgs.ghostscript
    pkgs.fontconfig
    pkgs.glibcLocales
    pkgs.freetype
    pkgs.redis
    pkgs.postgresql
    pkgs.openssl
  ];
}
