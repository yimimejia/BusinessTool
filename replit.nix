{pkgs}: {
  deps = [
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
