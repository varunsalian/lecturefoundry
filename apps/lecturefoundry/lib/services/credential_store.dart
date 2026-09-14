import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../models/webdav_settings.dart';

abstract interface class CredentialStorageBackend {
  Future<Map<String, String>> readAll();
  Future<void> write({required String key, required String? value});
  Future<void> deleteAll();
}

class FlutterCredentialStorageBackend implements CredentialStorageBackend {
  const FlutterCredentialStorageBackend(this.storage);

  final FlutterSecureStorage storage;

  @override
  Future<Map<String, String>> readAll() => storage.readAll();

  @override
  Future<void> write({required String key, required String? value}) =>
      storage.write(key: key, value: value);

  @override
  Future<void> deleteAll() => storage.deleteAll();
}

class CredentialStore {
  factory CredentialStore({FlutterSecureStorage? storage}) {
    final primary =
        storage ??
        // This remains encrypted in macOS Keychain while allowing local,
        // ad-hoc-signed builds that have no Apple provisioning profile.
        const FlutterSecureStorage(
          mOptions: MacOsOptions(usesDataProtectionKeychain: false),
        );
    return CredentialStore.withBackends(
      primary: FlutterCredentialStorageBackend(primary),
      // Earlier macOS builds used the data-protection keychain by default.
      // A signed upgrade can read it once and move the values to the classic
      // keychain. Ad-hoc builds may be denied access, which is safely ignored.
      legacy: storage == null && Platform.isMacOS
          ? const FlutterCredentialStorageBackend(
              FlutterSecureStorage(
                mOptions: MacOsOptions(usesDataProtectionKeychain: true),
              ),
            )
          : null,
    );
  }

  CredentialStore.withBackends({
    required CredentialStorageBackend primary,
    CredentialStorageBackend? legacy,
  }) : _storage = primary,
       _legacyStorage = legacy;

  static const _endpointKey = 'webdav_endpoint';
  static const _usernameKey = 'webdav_username';
  static const _passwordKey = 'webdav_password';
  static const _rootPathKey = 'webdav_root_path';

  final CredentialStorageBackend _storage;
  final CredentialStorageBackend? _legacyStorage;

  Future<WebDavSettings?> read() async {
    Map<String, String> primaryValues;
    try {
      primaryValues = await _storage.readAll();
    } catch (_) {
      primaryValues = const {};
    }
    final primarySettings = _settingsFrom(primaryValues);
    if (primarySettings != null) return primarySettings;

    final legacy = _legacyStorage;
    if (legacy == null) return null;
    try {
      final legacyValues = await legacy.readAll();
      final legacySettings = _settingsFrom(legacyValues);
      if (legacySettings == null) return null;
      try {
        await _write(legacySettings);
        await legacy.deleteAll();
      } catch (_) {
        // The recovered credentials still work for this session. Migration
        // can be retried on the next launch if the new keychain write failed.
      }
      return legacySettings;
    } catch (_) {
      return null;
    }
  }

  WebDavSettings? _settingsFrom(Map<String, String> values) {
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
    await _write(value);
    try {
      await _legacyStorage?.deleteAll();
    } catch (_) {
      // Saving to the active backend succeeded; inaccessible legacy data is
      // harmless and must not make the connection fail.
    }
  }

  Future<void> _write(WebDavSettings value) async {
    await Future.wait([
      _storage.write(key: _endpointKey, value: value.endpoint),
      _storage.write(key: _usernameKey, value: value.username),
      _storage.write(key: _passwordKey, value: value.password),
      _storage.write(key: _rootPathKey, value: value.rootPath),
    ]);
  }

  Future<void> clear() async {
    await _storage.deleteAll();
    try {
      await _legacyStorage?.deleteAll();
    } catch (_) {
      // The old macOS keychain can be unavailable to an ad-hoc build.
    }
  }
}
