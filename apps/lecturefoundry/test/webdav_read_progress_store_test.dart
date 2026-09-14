import 'package:flutter_test/flutter_test.dart';
import 'package:lecturefoundry/services/read_progress_store.dart';
import 'package:lecturefoundry/services/webdav_client.dart';
import 'package:lecturefoundry/services/webdav_read_progress_store.dart';

void main() {
  const lecture = '/Our Project/course/01-module/02-lecture/';
  const progressPath = '/Our Project/course/.lecturefoundry-progress.json';

  test(
    'syncs read and unread state between devices through the course file',
    () async {
      final cloud = _MemoryCloud();
      final first = WebDavReadProgressStore(
        source: cloud,
        destination: cloud,
        local: _MemoryLocalProgress(),
      );
      final second = WebDavReadProgressStore(
        source: cloud,
        destination: cloud,
        local: _MemoryLocalProgress(),
      );

      await first.setRead(lecture, isRead: true);
      expect(cloud.files[progressPath], contains('"01-module/02-lecture"'));
      expect(await second.isRead(lecture), isTrue);

      await second.setRead(lecture, isRead: false);
      first.invalidate(lecture);
      expect(await first.isRead(lecture), isFalse);
    },
  );

  test(
    'keeps offline changes locally and uploads them when online again',
    () async {
      final cloud = _MemoryCloud()..offline = true;
      final store = WebDavReadProgressStore(
        source: cloud,
        destination: cloud,
        local: _MemoryLocalProgress(),
      );

      await store.setRead(lecture, isRead: true);
      expect(await store.isRead(lecture), isTrue);
      expect(cloud.files, isEmpty);

      cloud.offline = false;
      store.invalidate(lecture);
      expect(await store.isRead(lecture), isTrue);
      expect(cloud.files, contains(progressPath));
    },
  );

  test('an offline action wins when the cloud clock is ahead', () async {
    final cloud = _MemoryCloud();
    final futureRecord = ReadProgressRecord(
      isRead: false,
      updatedAt: DateTime.utc(2099),
    );
    cloud.files[progressPath] = _progressJson(futureRecord);
    final local = _MemoryLocalProgress();
    final store = WebDavReadProgressStore(
      source: cloud,
      destination: cloud,
      local: local,
    );

    cloud.offline = true;
    await store.setRead(lecture, isRead: true);
    cloud.offline = false;
    store.invalidate(lecture);

    expect(await store.isRead(lecture), isTrue);
    expect(cloud.files[progressPath], contains('"read": true'));
    expect(local.records[lecture]!.pendingSync, isFalse);
    expect(
      local.records[lecture]!.updatedAt.isAfter(futureRecord.updatedAt),
      isTrue,
    );
  });

  test(
    'retries an ETag conflict without losing another device update',
    () async {
      const otherLectureKey = '01-module/03-other-lecture';
      final cloud = _MemoryCloud();
      cloud.files[progressPath] = '{"version":1,"lectures":{}}\n';
      cloud.conflictingUpdate = () {
        cloud.files[progressPath] =
            '''{
  "version": 1,
  "lectures": {
    "$otherLectureKey": {
      "read": true,
      "updatedAt": "2026-09-14T00:00:00.000Z"
    }
  }
}\n''';
      };
      final store = WebDavReadProgressStore(
        source: cloud,
        destination: cloud,
        local: _MemoryLocalProgress(),
      );

      await store.setRead(lecture, isRead: true);

      expect(cloud.files[progressPath], contains('"01-module/02-lecture"'));
      expect(cloud.files[progressPath], contains('"$otherLectureKey"'));
      expect(cloud.uploadAttempts, 2);
    },
  );

  test('only attempts one course download while progress is offline', () async {
    final cloud = _MemoryCloud()..offline = true;
    final store = WebDavReadProgressStore(
      source: cloud,
      destination: cloud,
      local: _MemoryLocalProgress(),
    );

    expect(await store.isRead(lecture), isFalse);
    expect(
      await store.isRead('/Our Project/course/01-module/03-lecture/'),
      isFalse,
    );
    expect(cloud.downloadAttempts, 1);
  });
}

String _progressJson(ReadProgressRecord record) =>
    '''{
  "version": 1,
  "lectures": {
    "01-module/02-lecture": {
      "read": ${record.isRead},
      "updatedAt": "${record.updatedAt.toIso8601String()}"
    }
  }
}\n''';

class _MemoryCloud
    implements
        WebDavDataSource,
        WebDavVersionedDataSource,
        WebDavWritableDataSource {
  final Map<String, String> files = {};
  bool offline = false;
  int version = 0;
  int downloadAttempts = 0;
  int uploadAttempts = 0;
  void Function()? conflictingUpdate;

  @override
  Future<String> downloadText(String remotePath) async {
    return (await downloadTextResource(remotePath)).contents;
  }

  @override
  Future<WebDavTextResource> downloadTextResource(String remotePath) async {
    downloadAttempts++;
    if (offline) throw const WebDavException('offline');
    final contents =
        files[remotePath] ??
        (throw WebDavNotFoundException('missing: $remotePath'));
    return WebDavTextResource(contents: contents, etag: '"$version"');
  }

  @override
  Future<List<WebDavEntry>> list(String remotePath) async => const [];

  @override
  Future<String?> uploadText(
    String remotePath,
    String contents, {
    String? ifMatch,
    bool createOnly = false,
  }) async {
    uploadAttempts++;
    if (offline) throw const WebDavException('offline');
    final conflict = conflictingUpdate;
    if (conflict != null) {
      conflictingUpdate = null;
      conflict();
      version++;
    }
    if (createOnly && files.containsKey(remotePath)) {
      throw const WebDavConflictException('already exists');
    }
    if (ifMatch != null && ifMatch != '"$version"') {
      throw const WebDavConflictException('etag changed');
    }
    files[remotePath] = contents;
    version++;
    return '"$version"';
  }
}

class _MemoryLocalProgress implements TimestampedReadProgressStorage {
  final Map<String, ReadProgressRecord> records = {};

  @override
  Future<bool> isRead(String lecturePath) async =>
      records[lecturePath]?.isRead ?? false;

  @override
  Future<ReadProgressRecord?> readRecord(String lecturePath) async =>
      records[lecturePath];

  @override
  Future<void> setRead(String lecturePath, {required bool isRead}) async {
    records[lecturePath] = ReadProgressRecord(
      isRead: isRead,
      updatedAt: DateTime.now().toUtc(),
      pendingSync: true,
    );
  }

  @override
  Future<void> writeRecord(
    String lecturePath,
    ReadProgressRecord record,
  ) async {
    records[lecturePath] = record;
  }
}
