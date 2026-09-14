import 'dart:convert';

import '../models/library_models.dart';
import '../models/webdav_settings.dart';
import 'lesson_cache.dart';
import 'read_progress_store.dart';
import 'webdav_client.dart';
import 'webdav_read_progress_store.dart';

class LibraryRepository {
  LibraryRepository({
    required this.source,
    required this.rootPath,
    required this.cacheNamespace,
    LessonCacheStore? cache,
    ReadProgressStorage? readProgress,
  }) : cache = cache ?? LessonCache(),
       readProgress =
           readProgress ?? _defaultReadProgress(source, cacheNamespace);

  final WebDavDataSource source;
  final String rootPath;
  final String cacheNamespace;
  final LessonCacheStore cache;
  final ReadProgressStorage readProgress;

  static const patternNames = <String, String>{
    'revision': 'One-page revision',
    'deep-dive': 'Deep dive',
    'active-recall': 'Active recall',
    'concept-map': 'Concept map',
  };

  Future<List<CourseRef>> listCourses() async {
    final entries = await source.list(rootPath);
    return entries
        .where(_visibleCollection)
        .map(
          (entry) => CourseRef(
            name: prettifySlug(entry.displayName),
            path: entry.path,
          ),
        )
        .toList(growable: false);
  }

  Future<List<ModuleRef>> listModules(CourseRef course) async {
    final entries = await source.list(course.path);
    final modules = entries
        .where(_visibleCollection)
        .map((entry) {
          final parsed = parseNumberedFolder(entry.displayName);
          return ModuleRef(
            number: parsed.number,
            name: parsed.title,
            path: entry.path,
          );
        })
        .where((module) => module.number > 0)
        .toList();
    modules.sort((a, b) => a.number.compareTo(b.number));
    return modules;
  }

  Future<List<LectureRef>> listLectures(ModuleRef module) async {
    final entries = await source.list(module.path);
    final lectures = entries
        .where(_visibleCollection)
        .map((entry) {
          final parsed = parseNumberedFolder(entry.displayName);
          return LectureRef(
            number: parsed.number,
            name: parsed.title,
            path: entry.path,
          );
        })
        .where((lecture) => lecture.number > 0)
        .toList();
    lectures.sort((a, b) => a.number.compareTo(b.number));
    if (lectures.isNotEmpty && readProgress is RefreshableReadProgressStorage) {
      (readProgress as RefreshableReadProgressStorage).invalidate(
        lectures.first.path,
      );
    }
    return Future.wait(
      lectures.map(
        (lecture) async =>
            lecture.copyWith(isRead: await _readStatus(lecture.path)),
      ),
    );
  }

  Future<bool> isLectureRead(LectureRef lecture) =>
      readProgress.isRead(lecture.path);

  Future<void> setLectureRead(LectureRef lecture, {required bool isRead}) =>
      readProgress.setRead(lecture.path, isRead: isRead);

  Future<bool> _readStatus(String path) async {
    try {
      return await readProgress.isRead(path);
    } catch (_) {
      // Progress is optional metadata and must not hide cloud lectures.
      return false;
    }
  }

  Future<List<StudyPatternRef>> listPatterns(LectureRef lecture) async {
    final entries = await source.list(lecture.path);
    final byName = {
      for (final entry in entries.where(_visibleCollection))
        entry.displayName: entry,
    };
    return patternNames.entries
        .where((pattern) => byName.containsKey(pattern.key))
        .map(
          (pattern) => StudyPatternRef(
            key: pattern.key,
            name: pattern.value,
            path: byName[pattern.key]!.path,
          ),
        )
        .toList(growable: false);
  }

  Future<LessonDocument> loadLesson(StudyPatternRef pattern) async {
    final path = joinRemotePath(pattern.path, 'lesson.json');
    late final String contents;
    try {
      contents = await source.downloadText(path);
    } catch (error, stackTrace) {
      return _loadCached(path, error, stackTrace);
    }

    late final LessonDocument lesson;
    try {
      lesson = _decodeLesson(contents);
    } on WebDavException catch (error, stackTrace) {
      return _loadCached(path, error, stackTrace);
    }

    // A cache failure must never make successfully downloaded notes unreadable.
    try {
      await cache.write(cacheNamespace, path, contents);
    } catch (_) {
      // The cache is an optional optimization; the validated lesson is usable.
    }
    return lesson;
  }

  Future<LessonDocument> _loadCached(
    String path,
    Object originalError,
    StackTrace originalStackTrace,
  ) async {
    final cached = await cache.read(cacheNamespace, path);
    if (cached == null) {
      Error.throwWithStackTrace(originalError, originalStackTrace);
    }
    return _decodeLesson(cached);
  }

  LessonDocument _decodeLesson(String contents) {
    try {
      return LessonDocument.fromJson(
        jsonDecode(contents) as Map<String, dynamic>,
      );
    } on FormatException {
      throw const WebDavException('This lesson.json file is not valid JSON.');
    } on TypeError {
      throw const WebDavException(
        'This lesson.json file has an unsupported structure.',
      );
    }
  }

  bool _visibleCollection(WebDavEntry entry) =>
      entry.isCollection && !entry.displayName.startsWith('.');
}

ReadProgressStorage _defaultReadProgress(
  WebDavDataSource source,
  String namespace,
) {
  final local = ReadProgressStore(namespace: namespace);
  if (source is WebDavWritableDataSource &&
      source is WebDavVersionedDataSource) {
    return WebDavReadProgressStore(
      source: source as WebDavVersionedDataSource,
      destination: source as WebDavWritableDataSource,
      local: local,
    );
  }
  return local;
}

class NumberedFolder {
  const NumberedFolder(this.number, this.title);

  final int number;
  final String title;
}

NumberedFolder parseNumberedFolder(String value) {
  final match = RegExp(r'^(\d+)[-_ ]+(.+)$').firstMatch(value);
  if (match == null) return NumberedFolder(0, prettifySlug(value));
  return NumberedFolder(
    int.tryParse(match.group(1)!) ?? 0,
    prettifySlug(match.group(2)!),
  );
}

String prettifySlug(String value) => value
    .replaceAll(RegExp(r'[-_]+'), ' ')
    .trim()
    .split(RegExp(r'\s+'))
    .where((word) => word.isNotEmpty)
    .map((word) => word[0].toUpperCase() + word.substring(1))
    .join(' ');
