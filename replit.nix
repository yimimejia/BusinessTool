{pkgs}: {
  deps = [
    pkgs.glibcLocales
    pkgs.freetype
    pkgs.redis
    pkgs.postgresql
    pkgs.openssl
  ];
}
