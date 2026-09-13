import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lecturefoundry/models/library_models.dart';
import 'package:lecturefoundry/screens/lecture_screen.dart';
import 'package:lecturefoundry/services/lesson_cache.dart';
import 'package:lecturefoundry/services/library_repository.dart';
import 'package:lecturefoundry/services/webdav_client.dart';

void main() {
  testWidgets('opens revision first and switches formats in the reader', (
    tester,
  ) async {
    final repository = LibraryRepository(
      source: _LectureSource(),
      rootPath: '/Our Project/',
      cacheNamespace: 'test',
      cache: _NoopCache(),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: LectureScreen(repository: repository, lecture: _lecture),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Revision title'), findsOneWidget);
    final revisionChip = tester.widget<ChoiceChip>(
      find.widgetWithText(ChoiceChip, 'One-page revision'),
    );
    expect(revisionChip.selected, isTrue);

    await tester.tap(find.text('Deep dive'));
    await tester.pumpAndSettle();

    expect(find.text('Deep dive title'), findsOneWidget);
    final deepDiveChip = tester.widget<ChoiceChip>(
      find.widgetWithText(ChoiceChip, 'Deep dive'),
    );
    expect(deepDiveChip.selected, isTrue);
  });
}

class _LectureSource implements WebDavDataSource {
  @override
  Future<List<WebDavEntry>> list(String remotePath) async => const [
    WebDavEntry(
      displayName: 'deep-dive',
      path: '/course/module/lecture/deep-dive/',
      isCollection: true,
    ),
    WebDavEntry(
      displayName: 'revision',
      path: '/course/module/lecture/revision/',
      isCollection: true,
    ),
  ];

  @override
  Future<String> downloadText(String remotePath) async {
    final deepDive = remotePath.contains('/deep-dive/');
    final key = deepDive ? 'deep-dive' : 'revision';
    final name = deepDive ? 'Deep dive' : 'One-page revision';
    final title = deepDive ? 'Deep dive title' : 'Revision title';
    return '''{
      "course_slug": "course",
      "module": {"number": 1, "title": "Module"},
      "lecture": {"number": 1, "title": "Lecture"},
      "pattern": {"key": "$key", "name": "$name"},
      "content": {
        "title": "$title",
        "subtitle": "",
        "summary": "Summary",
        "key_idea": "Idea",
        "sections": [],
        "examples": [],
        "review_questions": [],
        "action_prompt": ""
      }
    }''';
  }
}

class _NoopCache implements LessonCacheStore {
  @override
  Future<String?> read(String namespace, String remotePath) async => null;

  @override
  Future<void> write(
    String namespace,
    String remotePath,
    String contents,
  ) async {}
}

const _lecture = LectureRef(
  number: 1,
  name: 'Lecture',
  path: '/course/module/lecture/',
);
