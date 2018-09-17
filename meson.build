
project('blueberry',
  version: '3.14',
  meson_version: '>=0.45.0',
)

gettext_package = 'blueberry'


subdir('po')

install_subdir('etc/xdg/autostart',
  install_dir: join_paths(get_option('sysconfdir'), 'xdg', 'autostart'),
  strip_directory: true,
)
install_subdir('usr/bin',
  install_dir: get_option('bindir'),
  strip_directory: true,
)
install_subdir('usr/lib',
  install_dir: get_option('libdir'),
  strip_directory: true,
)
install_subdir('usr/share',
  install_dir: get_option('datadir'),
  strip_directory: true,
)
