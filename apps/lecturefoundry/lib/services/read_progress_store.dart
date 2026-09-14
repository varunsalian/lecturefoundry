import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:path_provider/path_provider.dart';

abstract interface class ReadProgressStorage {
  Future<bool> isRead(String lecturePath);
  Future<void> setRead(String lecturePath, {required bool isRead});
}

class ReadProgressRecord {
  const ReadProgressRecord({
    required this.isRead,
    required this.updatedAt,
    this.pendingSync = false,
  });

  final bool isRead;
  final DateTime updatedAt;
  final bool pendingSync;

  ReadProgressRecord copyWith({
    bool? isRead,
    DateTime? updatedAt,
    bool? pendingSync,
  }) => ReadProgressRecord(
    isRead: isRead ?? this.isRead,
    updatedAt: updatedAt ?? this.updatedAt,
    pendingSync: pendingSync ?? this.pendingSync,
  );
}

abstract interface class TimestampedReadProgressStorage
    implements ReadProgressStorage {
  Future<ReadProgressRecord?> readRecord(String lecturePath);
  Future<void> writeRecord(String lecturePath, ReadProgressRecord record);
}

abstract interface class RefreshableReadProgressStorage {
  void invalidate(String lecturePath);
}

typedef SupportDirectoryProvider = Future<Directory> Function();

class ReadProgressStore implements TimestampedReadProgressStorage {
  ReadProgressStore({
    required this.namespace,
    SupportDirectoryProvider? directoryProvider,
  }) : _directoryProvider =
           directoryProvider ?? (() => getApplicationSupportDirectory());

  final String namespace;
  final SupportDirectoryProvider _directoryProvider;
  Future<Map<String, ReadProgressRecord>>? _loaded;
  Future<void> _writeQueue = Future.value();

  String _key(String lecturePath) =>
      sha256.convert(utf8.encode('$namespace\n$lecturePath')).toString();

  Future<File> _file() async {
    final root = await _directoryProvider();
    final directory = Directory('${root.path}/read-progress');
    await directory.create(recursive: true);
    final library = sha256.convert(utf8.encode(namespace)).toString();
    return File('${directory.path}/$library.json');
  }

  Future<Map<String, ReadProgressRecord>> _readRecords() => _loaded ??= _load();

  Future<Map<String, ReadProgressRecord>> _load() async {
    final file = await _file();
    if (!await file.exists()) return <String, ReadProgressRecord>{};
    try {
      final data = jsonDecode(await file.readAsString());
      if (data is! Map<String, dynamic>) {
        return <String, ReadProgressRecord>{};
      }
      final records = data['records'];
      if (records is Map<String, dynamic>) {
        final result = <String, ReadProgressRecord>{};
        for (final entry in records.entries) {
          final value = entry.value;
          if (value is! Map<String, dynamic>) continue;
          final isRead = value['read'];
          final rawUpdatedAt = value['updatedAt'];
          final updatedAt = rawUpdatedAt is String
              ? DateTime.tryParse(rawUpdatedAt)
              : null;
          if (isRead is bool && updatedAt != null) {
            result[entry.key] = ReadProgressRecord(
              isRead: isRead,
              updatedAt: updatedAt.toUtc(),
              pendingSync: value['pendingSync'] == true,
            );
          }
        }
        return result;
      }

      // Migrate the original read-only format without losing existing ticks.
      final read = data['read'];
      if (read is! List<dynamic>) return <String, ReadProgressRecord>{};
      final migratedAt = (await file.lastModified()).toUtc();
      return {
        for (final key in read.whereType<String>())
          key: ReadProgressRecord(
            isRead: true,
            updatedAt: migratedAt,
            pendingSync: true,
          ),
      };
    } on FormatException {
      return <String, ReadProgressRecord>{};
    }
  }

  @override
  Future<bool> isRead(String lecturePath) async =>
      (await readRecord(lecturePath))?.isRead ?? false;

  @override
  Future<ReadProgressRecord?> readRecord(String lecturePath) async =>
      (await _readRecords())[_key(lecturePath)];

  @override
  Future<void> setRead(String lecturePath, {required bool isRead}) =>
      writeRecord(
        lecturePath,
        ReadProgressRecord(
          isRead: isRead,
          updatedAt: DateTime.now().toUtc(),
          pendingSync: true,
        ),
      );

  @override
  Future<void> writeRecord(String lecturePath, ReadProgressRecord record) {
    final operation = _writeQueue.then(
      (_) => _update(lecturePath, record),
      onError: (_) => _update(lecturePath, record),
    );
    _writeQueue = operation;
    return operation;
  }

  Future<void> _update(String lecturePath, ReadProgressRecord record) async {
    final values = Map<String, ReadProgressRecord>.of(await _readRecords());
    values[_key(lecturePath)] = record;

    final file = await _file();
    final temporary = File(
      '${file.path}.${DateTime.now().microsecondsSinceEpoch}.tmp',
    );
    try {
      await temporary.writeAsString(
        '${jsonEncode({
          'version': 2,
          'records': {
            for (final key in values.keys.toList()..sort()) key: {'read': values[key]!.isRead, 'updatedAt': values[key]!.updatedAt.toUtc().toIso8601String(), 'pendingSync': values[key]!.pendingSync},
          },
        })}\n',
        flush: true,
      );
      try {
        await temporary.rename(file.path);
      } on FileSystemException {
        if (!Platform.isWindows || !await file.exists()) rethrow;
        await file.writeAsString(await temporary.readAsString(), flush: true);
      }
      _loaded = Future.value(values);
    } finally {
      if (await temporary.exists()) await temporary.delete();
    }
  }
}
