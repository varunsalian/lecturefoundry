import 'package:flutter_test/flutter_test.dart';
import 'package:lecturefoundry/models/library_models.dart';
import 'package:lecturefoundry/models/webdav_settings.dart';

void main() {
  test('reads the generated lesson.json schema', () {
    final lesson = LessonDocument.fromJson({
      'course_slug': 'course',
      'module': {'number': 1, 'title': 'Introduction'},
      'lecture': {'number': 4, 'title': 'The Fallacy'},
      'pattern': {'key': 'revision', 'name': 'One-page revision'},
      'content': {
        'title': 'The Fallacy',
        'subtitle': 'Revision',
        'summary': 'A summary',
        'key_idea': 'Knowing is not enough.',
        'sections': [
          {
            'heading': 'Meaning',
            'body': 'Explanation',
            'bullets': ['One'],
          },
        ],
        'examples': [
          {'title': 'Example', 'explanation': 'Explanation'},
        ],
        'review_questions': ['What changed?'],
        'action_prompt': 'Try it.',
      },
    });

    expect(lesson.moduleNumber, 1);
    expect(lesson.patternKey, 'revision');
    expect(lesson.sections.single.bullets, ['One']);
    expect(lesson.reviewQuestions, ['What changed?']);
  });

  test('cache namespaces distinguish accounts without including passwords', () {
    const first = WebDavSettings(
      endpoint: 'https://cloud.example/dav',
      username: 'first@example.com',
      password: 'password-one',
      rootPath: '/',
    );
    const second = WebDavSettings(
      endpoint: 'https://cloud.example/dav',
      username: 'second@example.com',
      password: 'password-two',
      rootPath: '/',
    );
    const rotatedPassword = WebDavSettings(
      endpoint: 'https://cloud.example/dav/',
      username: 'first@example.com',
      password: 'new-password',
      rootPath: '/',
    );

    expect(first.cacheNamespace, isNot(second.cacheNamespace));
    expect(first.cacheNamespace, rotatedPassword.cacheNamespace);
    expect(first.cacheNamespace, isNot(contains(first.password)));
  });
}
