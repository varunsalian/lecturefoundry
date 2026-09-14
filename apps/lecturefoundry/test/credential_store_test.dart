import 'package:flutter_test/flutter_test.dart';
import 'package:lecturefoundry/services/credential_store.dart';

void main() {
  test('migrates complete credentials from the legacy keychain', () async {
    final primary = _MemoryCredentialBackend();
    final legacy = _MemoryCredentialBackend({
      'webdav_endpoint': 'https://cloud.example/dav',
      'webdav_username': 'reader@example.com',
      'webdav_password': 'app-password',
      'webdav_root_path': 'Notes',
    });
    final store = CredentialStore.withBackends(
      primary: primary,
      legacy: legacy,
    );

    final settings = await store.read();

    expect(settings?.endpoint, 'https://cloud.example/dav/');
    expect(settings?.username, 'reader@example.com');
    expect(settings?.password, 'app-password');
    expect(settings?.rootPath, '/Notes/');
    expect(primary.values['webdav_password'], 'app-password');
    expect(legacy.values, isEmpty);
  });

  test('disconnect clears both active and legacy credentials', () async {
    final primary = _MemoryCredentialBackend({'key': 'active'});
    final legacy = _MemoryCredentialBackend({'key': 'legacy'});
    final store = CredentialStore.withBackends(
      primary: primary,
      legacy: legacy,
    );

    await store.clear();

    expect(primary.values, isEmpty);
    expect(legacy.values, isEmpty);
  });
}

class _MemoryCredentialBackend implements CredentialStorageBackend {
  _MemoryCredentialBackend([Map<String, String>? values])
    : values = {...?values};

  final Map<String, String> values;

  @override
  Future<void> deleteAll() async => values.clear();

  @override
  Future<Map<String, String>> readAll() async => Map.of(values);

  @override
  Future<void> write({required String key, required String? value}) async {
    if (value == null) {
      values.remove(key);
    } else {
      values[key] = value;
    }
  }
}
