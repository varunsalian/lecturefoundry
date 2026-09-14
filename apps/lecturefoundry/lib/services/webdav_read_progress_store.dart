import 'dart:convert';

import '../models/webdav_settings.dart';
import 'read_progress_store.dart';
import 'webdav_client.dart';

/// Synchronizes reading progress through one hidden JSON file in each course.
/// Local timestamped records remain the offline fallback and outbox.
class WebDavReadProgressStore
    implements ReadProgressStorage, RefreshableReadProgressStorage {
  WebDavReadProgressStore({
    required this.source,
    required this.destination,
    required this.local,
  });

  static const fileName = '.lecturefoundry-progress.json';

  static const _conflictRetries = 3;

  final WebDavVersionedDataSource source;
  final WebDavWritableDataSource destination;
  final TimestampedReadProgressStorage local;
  final Map<String, _CourseProgress> _courseCache = {};
  final Set<String> _unavailableCourses = {};
  Future<void> _queue = Future.value();

  @override
  void invalidate(String lecturePath) {
    final coursePath = _location(lecturePath).coursePath;
    _courseCache.remove(coursePath);
    _unavailableCourses.remove(coursePath);
  }

  @override
  Future<bool> isRead(String lecturePath) => _serialized(() async {
    final localRecord = await local.readRecord(lecturePath);
    final location = _location(lecturePath);
    try {
      final synced = await _synchronize(
        lecturePath,
        location,
        localRecord,
        forceLocal: localRecord?.pendingSync == true,
      );
      return synced?.isRead ?? false;
    } catch (_) {
      // Progress sync is optional; cached progress keeps the library usable.
      return localRecord?.isRead ?? false;
    }
  });

  @override
  Future<void> setRead(String lecturePath, {required bool isRead}) async {
    await local.setRead(lecturePath, isRead: isRead);
    await _serialized(() async {
      final location = _location(lecturePath);
      final localRecord = (await local.readRecord(lecturePath))!;
      try {
        await _synchronize(
          lecturePath,
          location,
          localRecord,
          forceLocal: true,
          fresh: true,
        );
      } catch (_) {
        // Leave the timestamped local record pending for the next online sync.
        _courseCache.remove(location.coursePath);
      }
    });
  }

  Future<ReadProgressRecord?> _synchronize(
    String lecturePath,
    _ProgressLocation location,
    ReadProgressRecord? localRecord, {
    required bool forceLocal,
    bool fresh = false,
  }) async {
    var candidate = localRecord;
    for (var attempt = 0; attempt < _conflictRetries; attempt++) {
      final course = await _loadCourse(
        location.coursePath,
        fresh: fresh || attempt > 0,
      );
      final remoteRecord = course.records[location.lectureKey];
      final localWins =
          candidate != null &&
          (forceLocal ||
              remoteRecord == null ||
              candidate.updatedAt.isAfter(remoteRecord.updatedAt));
      if (!localWins) {
        if (remoteRecord != null && !_sameRecord(candidate, remoteRecord)) {
          await local.writeRecord(lecturePath, remoteRecord);
        }
        return remoteRecord;
      }

      var winner = candidate;
      if (forceLocal &&
          remoteRecord != null &&
          !winner.updatedAt.isAfter(remoteRecord.updatedAt)) {
        winner = winner.copyWith(
          updatedAt: remoteRecord.updatedAt.add(
            const Duration(microseconds: 1),
          ),
        );
        candidate = winner;
        await local.writeRecord(lecturePath, winner);
      }

      final acknowledged = winner.copyWith(pendingSync: false);
      if (_sameRecord(acknowledged, remoteRecord)) {
        if (!_sameRecord(localRecord, acknowledged)) {
          await local.writeRecord(lecturePath, acknowledged);
        }
        return acknowledged;
      }

      course.records[location.lectureKey] = acknowledged;
      try {
        await _upload(location.coursePath, course);
        await local.writeRecord(lecturePath, acknowledged);
        return acknowledged;
      } on WebDavConflictException {
        _courseCache.remove(location.coursePath);
      }
    }
    throw const WebDavConflictException(
      'Reading progress kept changing on another device.',
    );
  }

  Future<T> _serialized<T>(Future<T> Function() action) {
    final operation = _queue.then((_) => action(), onError: (_) => action());
    _queue = operation.then<void>((_) {}, onError: (_) {});
    return operation;
  }

  Future<_CourseProgress> _loadCourse(
    String coursePath, {
    bool fresh = false,
  }) async {
    if (!fresh) {
      final cached = _courseCache[coursePath];
      if (cached != null) return cached;
      if (_unavailableCourses.contains(coursePath)) {
        throw const WebDavException('Reading progress is temporarily offline.');
      }
    }
    final path = joinRemotePath(coursePath, fileName);
    try {
      final resource = await source.downloadTextResource(path);
      final progress = _CourseProgress.decode(
        resource.contents,
        etag: resource.etag,
      );
      _courseCache[coursePath] = progress;
      _unavailableCourses.remove(coursePath);
      return progress;
    } on WebDavNotFoundException {
      final progress = _CourseProgress();
      _courseCache[coursePath] = progress;
      _unavailableCourses.remove(coursePath);
      return progress;
    } catch (_) {
      _courseCache.remove(coursePath);
      _unavailableCourses.add(coursePath);
      rethrow;
    }
  }

  Future<void> _upload(String coursePath, _CourseProgress progress) async {
    if (progress.exists && progress.etag == null) {
      throw const WebDavException(
        'The WebDAV server did not provide an ETag for reading progress.',
      );
    }
    final etag = await destination.uploadText(
      joinRemotePath(coursePath, fileName),
      progress.encode(),
      ifMatch: progress.exists ? progress.etag : null,
      createOnly: !progress.exists,
    );
    progress
      ..exists = true
      ..etag = etag;
    _unavailableCourses.remove(coursePath);
    if (etag == null) {
      // Force a fresh GET before the next conditional update.
      _courseCache.remove(coursePath);
    } else {
      _courseCache[coursePath] = progress;
    }
  }
}

class _ProgressLocation {
  const _ProgressLocation({required this.coursePath, required this.lectureKey});

  final String coursePath;
  final String lectureKey;
}

_ProgressLocation _location(String lecturePath) {
  final segments = normalizeRemotePath(
    lecturePath,
    collection: true,
  ).split('/').where((segment) => segment.isNotEmpty).toList(growable: false);
  if (segments.length < 3) {
    throw ArgumentError.value(lecturePath, 'lecturePath', 'Invalid path');
  }
  final courseSegments = segments.sublist(0, segments.length - 2);
  return _ProgressLocation(
    coursePath: '/${courseSegments.join('/')}/',
    lectureKey: segments.sublist(segments.length - 2).join('/'),
  );
}

bool _sameRecord(ReadProgressRecord? left, ReadProgressRecord? right) =>
    left?.isRead == right?.isRead &&
    left?.updatedAt == right?.updatedAt &&
    left?.pendingSync == right?.pendingSync;

class _CourseProgress {
  _CourseProgress({
    Map<String, ReadProgressRecord>? records,
    this.exists = false,
    this.etag,
  }) : records = records ?? {};

  final Map<String, ReadProgressRecord> records;
  bool exists;
  String? etag;

  factory _CourseProgress.decode(String contents, {required String? etag}) {
    try {
      final data = jsonDecode(contents);
      if (data is! Map<String, dynamic> ||
          data['lectures'] is! Map<String, dynamic>) {
        throw const FormatException();
      }
      final result = <String, ReadProgressRecord>{};
      for (final entry in (data['lectures'] as Map<String, dynamic>).entries) {
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
          );
        }
      }
      return _CourseProgress(records: result, exists: true, etag: etag);
    } on FormatException {
      throw const WebDavException(
        'The course reading-progress file is not valid JSON.',
      );
    } on TypeError {
      throw const WebDavException(
        'The course reading-progress file has an unsupported structure.',
      );
    }
  }

  String encode() {
    final sortedKeys = records.keys.toList()..sort();
    return '${const JsonEncoder.withIndent('  ').convert({
      'version': 1,
      'lectures': {
        for (final key in sortedKeys) key: {'read': records[key]!.isRead, 'updatedAt': records[key]!.updatedAt.toUtc().toIso8601String()},
      },
    })}\n';
  }
}
