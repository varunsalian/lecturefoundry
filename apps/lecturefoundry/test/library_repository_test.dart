import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:lecturefoundry/models/library_models.dart';
import 'package:lecturefoundry/services/lesson_cache.dart';
import 'package:lecturefoundry/services/library_repository.dart';
import 'package:lecturefoundry/services/webdav_client.dart';

void main() {
  test('parses numbered module and lecture folder names', () {
    final module = parseNumberedFolder('05-stuff-that-really-makes-us-happy');
    expect(module.number, 5);
    expect(module.title, 'Stuff That Really Makes Us Happy');
  });

  test(
    'discovers and sorts modules while ignoring non-numbered folders',
    () async {
      final source = _FakeSource({
        '/Our Project/course/': const [
          WebDavEntry(
            displayName: '10-last-module',
            path: '/Our Project/course/10-last-module/',
            isCollection: true,
          ),
          WebDavEntry(
            displayName: '02-first-module',
            path: '/Our Project/course/02-first-module/',
            isCollection: true,
          ),
          WebDavEntry(
            displayName: 'assets',
            path: '/Our Project/course/assets/',
            isCollection: true,
          ),
        ],
      });
      final repository = LibraryRepository(
        source: source,
        rootPath: '/Our Project/',
        cacheNamespace: 'server-a\nuser-a',
      );

      final modules = await repository.listModules(
        const CourseRef(name: 'Course', path: '/Our Project/course/'),
      );

      expect(modules.map((module) => module.number), [2, 10]);
    },
  );

  test('does not read cached lessons belonging to another account', () async {
    const lessonPath =
        '/Our Project/course/01-module/01-lecture/revision/lesson.json';
    final source = _FakeSource(
      const {},
      downloadError: const WebDavException('offline'),
    );
    final cache = _FakeCache()
      ..values['server-a\nuser-a|$lessonPath'] = _validLessonJson;
    final repository = LibraryRepository(
      source: source,
      rootPath: '/Our Project/',
      cacheNamespace: 'server-b\nuser-b',
      cache: cache,
    );

    await expectLater(
      repository.loadLesson(_revisionPattern),
      throwsA(isA<WebDavException>()),
    );
  });

  test('keeps the last valid cache when the cloud JSON is malformed', () async {
    const lessonPath =
        '/Our Project/course/01-module/01-lecture/revision/lesson.json';
    final source = _FakeSource(
      const {},
      downloads: const {lessonPath: '{broken'},
    );
    final cache = _FakeCache()
      ..values['server-a\nuser-a|$lessonPath'] = _validLessonJson;
    final repository = LibraryRepository(
      source: source,
      rootPath: '/Our Project/',
      cacheNamespace: 'server-a\nuser-a',
      cache: cache,
    );

    final lesson = await repository.loadLesson(_revisionPattern);

    expect(lesson.title, 'Cached lesson');
    expect(cache.writes, isEmpty);
  });

  test('returns a valid download even when cache writing fails', () async {
    const lessonPath =
        '/Our Project/course/01-module/01-lecture/revision/lesson.json';
    final source = _FakeSource(
      const {},
      downloads: const {lessonPath: _validLessonJson},
    );
    final cache = _FakeCache(failWrites: true);
    final repository = LibraryRepository(
      source: source,
      rootPath: '/Our Project/',
      cacheNamespace: 'server-a\nuser-a',
      cache: cache,
    );

    final lesson = await repository.loadLesson(_revisionPattern);

    expect(lesson.title, 'Cached lesson');
  });
}

class _FakeSource implements WebDavDataSource {
  _FakeSource(this.listings, {this.downloads = const {}, this.downloadError});

  final Map<String, List<WebDavEntry>> listings;
  final Map<String, String> downloads;
  final Object? downloadError;

  @override
  Future<String> downloadText(String remotePath) async {
    if (downloadError case final error?) throw error;
    return downloads[remotePath] ?? (throw StateError('Missing download'));
  }

  @override
  Future<List<WebDavEntry>> list(String remotePath) async =>
      listings[remotePath] ?? const [];
}

class _FakeCache implements LessonCacheStore {
  _FakeCache({this.failWrites = false});

  final bool failWrites;
  final Map<String, String> values = {};
  final List<String> writes = [];

  String _key(String namespace, String remotePath) => '$namespace|$remotePath';

  @override
  Future<String?> read(String namespace, String remotePath) async =>
      values[_key(namespace, remotePath)];

  @override
  Future<void> write(
    String namespace,
    String remotePath,
    String contents,
  ) async {
    if (failWrites) throw const FileSystemException('cache unavailable');
    final key = _key(namespace, remotePath);
    writes.add(key);
    values[key] = contents;
  }
}

const _revisionPattern = StudyPatternRef(
  key: 'revision',
  name: 'One-page revision',
  path: '/Our Project/course/01-module/01-lecture/revision/',
);

const _validLessonJson = '''{
  "course_slug": "course",
  "module": {"number": 1, "title": "Module"},
  "lecture": {"number": 1, "title": "Lecture"},
  "pattern": {"key": "revision", "name": "One-page revision"},
  "content": {
    "title": "Cached lesson",
    "subtitle": "",
    "summary": "Summary",
    "key_idea": "Idea",
    "sections": [],
    "examples": [],
    "review_questions": [],
    "action_prompt": ""
  }
}''';
