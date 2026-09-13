class WebDavSettings {
  const WebDavSettings({
    required this.endpoint,
    required this.username,
    required this.password,
    required this.rootPath,
  });

  final String endpoint;
  final String username;
  final String password;
  final String rootPath;

  /// Separates cached lessons belonging to different servers and accounts.
  /// The cache hashes this value before using it as a filename.
  String get cacheNamespace {
    final value = normalized();
    return '${value.endpoint}\n${value.username}';
  }

  WebDavSettings normalized() => WebDavSettings(
    endpoint: endpoint.trim().endsWith('/')
        ? endpoint.trim()
        : '${endpoint.trim()}/',
    username: username.trim(),
    password: password,
    rootPath: normalizeRemotePath(rootPath, collection: true),
  );
}

String normalizeRemotePath(String value, {bool collection = false}) {
  final segments = value
      .trim()
      .split('/')
      .where((segment) => segment.trim().isNotEmpty)
      .map((segment) => segment.trim())
      .toList();
  final joined = '/${segments.join('/')}';
  if (collection && joined != '/') {
    return '$joined/';
  }
  return joined;
}

String joinRemotePath(String parent, String child, {bool collection = false}) {
  final cleanParent = normalizeRemotePath(parent);
  final cleanChild = child
      .split('/')
      .where((part) => part.isNotEmpty)
      .join('/');
  return normalizeRemotePath(
    '$cleanParent/$cleanChild',
    collection: collection,
  );
}
