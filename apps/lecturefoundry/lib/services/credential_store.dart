import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../models/webdav_settings.dart';

class CredentialStore {
  CredentialStore({FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();

  static const _endpointKey = 'webdav_endpoint';
  static const _usernameKey = 'webdav_username';
  static const _passwordKey = 'webdav_password';
  static const _rootPathKey = 'webdav_root_path';

  final FlutterSecureStorage _storage;

  Future<WebDavSettings?> read() async {
    final values = await _storage.readAll();
    final endpoint = values[_endpointKey];
    final username = values[_usernameKey];
    final password = values[_passwordKey];
    final rootPath = values[_rootPathKey];
    if (endpoint == null ||
        username == null ||
        password == null ||
        rootPath == null) {
      return null;
    }
    return WebDavSettings(
      endpoint: endpoint,
      username: username,
      password: password,
      rootPath: rootPath,
    ).normalized();
  }

  Future<void> save(WebDavSettings settings) async {
    final value = settings.normalized();
    await Future.wait([
      _storage.write(key: _endpointKey, value: value.endpoint),
      _storage.write(key: _usernameKey, value: value.username),
      _storage.write(key: _passwordKey, value: value.password),
      _storage.write(key: _rootPathKey, value: value.rootPath),
    ]);
  }

  Future<void> clear() => _storage.deleteAll();
}
