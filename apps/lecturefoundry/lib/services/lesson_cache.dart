import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:path_provider/path_provider.dart';

abstract interface class LessonCacheStore {
  Future<String?> read(String namespace, String remotePath);
  Future<void> write(String namespace, String remotePath, String contents);
}

class LessonCache implements LessonCacheStore {
  Future<File> _file(String namespace, String remotePath) async {
    final root = await getApplicationSupportDirectory();
    final directory = Directory('${root.path}/lesson-cache');
    await directory.create(recursive: true);
    final key = sha256
        .convert(utf8.encode('$namespace\n$remotePath'))
        .toString();
    return File('${directory.path}/$key.json');
  }

  @override
  Future<String?> read(String namespace, String remotePath) async {
    final file = await _file(namespace, remotePath);
    return file.existsSync() ? file.readAsString() : null;
  }

  @override
  Future<void> write(
    String namespace,
    String remotePath,
    String contents,
  ) async {
    final file = await _file(namespace, remotePath);
    final temporary = File(
      '${file.path}.${DateTime.now().microsecondsSinceEpoch}.tmp',
    );
    try {
      await temporary.writeAsString(contents, flush: true);
      try {
        await temporary.rename(file.path);
      } on FileSystemException {
        // Windows does not atomically replace an existing destination during
        // rename. The content is already validated, so update the cache in
        // place without first deleting the known-good destination.
        if (!Platform.isWindows || !await file.exists()) rethrow;
        await file.writeAsString(contents, flush: true);
      }
    } finally {
      if (await temporary.exists()) await temporary.delete();
    }
  }
}
