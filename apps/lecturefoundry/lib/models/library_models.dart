class CourseRef {
  const CourseRef({required this.name, required this.path});

  final String name;
  final String path;
}

class ModuleRef {
  const ModuleRef({
    required this.number,
    required this.name,
    required this.path,
  });

  final int number;
  final String name;
  final String path;
}

class LectureRef {
  const LectureRef({
    required this.number,
    required this.name,
    required this.path,
  });

  final int number;
  final String name;
  final String path;
}

class StudyPatternRef {
  const StudyPatternRef({
    required this.key,
    required this.name,
    required this.path,
  });

  final String key;
  final String name;
  final String path;
}

class LessonSection {
  const LessonSection({
    required this.heading,
    required this.body,
    required this.bullets,
  });

  final String heading;
  final String body;
  final List<String> bullets;

  factory LessonSection.fromJson(Map<String, dynamic> json) => LessonSection(
    heading: json['heading'] as String? ?? 'Section',
    body: json['body'] as String? ?? '',
    bullets: (json['bullets'] as List<dynamic>? ?? const [])
        .whereType<String>()
        .toList(growable: false),
  );
}

class LessonExample {
  const LessonExample({required this.title, required this.explanation});

  final String title;
  final String explanation;

  factory LessonExample.fromJson(Map<String, dynamic> json) => LessonExample(
    title: json['title'] as String? ?? 'Example',
    explanation: json['explanation'] as String? ?? '',
  );
}

class LessonDocument {
  const LessonDocument({
    required this.courseSlug,
    required this.moduleNumber,
    required this.moduleTitle,
    required this.lectureNumber,
    required this.lectureTitle,
    required this.patternKey,
    required this.patternName,
    required this.title,
    required this.subtitle,
    required this.summary,
    required this.keyIdea,
    required this.sections,
    required this.examples,
    required this.reviewQuestions,
    required this.actionPrompt,
  });

  final String courseSlug;
  final int moduleNumber;
  final String moduleTitle;
  final int lectureNumber;
  final String lectureTitle;
  final String patternKey;
  final String patternName;
  final String title;
  final String subtitle;
  final String summary;
  final String keyIdea;
  final List<LessonSection> sections;
  final List<LessonExample> examples;
  final List<String> reviewQuestions;
  final String actionPrompt;

  factory LessonDocument.fromJson(Map<String, dynamic> json) {
    final module = json['module'] as Map<String, dynamic>? ?? const {};
    final lecture = json['lecture'] as Map<String, dynamic>? ?? const {};
    final pattern = json['pattern'] as Map<String, dynamic>? ?? const {};
    final content = json['content'] as Map<String, dynamic>? ?? const {};
    return LessonDocument(
      courseSlug: json['course_slug'] as String? ?? '',
      moduleNumber: (module['number'] as num?)?.toInt() ?? 0,
      moduleTitle: module['title'] as String? ?? '',
      lectureNumber: (lecture['number'] as num?)?.toInt() ?? 0,
      lectureTitle: lecture['title'] as String? ?? '',
      patternKey: pattern['key'] as String? ?? '',
      patternName: pattern['name'] as String? ?? '',
      title: content['title'] as String? ?? lecture['title'] as String? ?? '',
      subtitle: content['subtitle'] as String? ?? '',
      summary: content['summary'] as String? ?? '',
      keyIdea: content['key_idea'] as String? ?? '',
      sections: (content['sections'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(LessonSection.fromJson)
          .toList(growable: false),
      examples: (content['examples'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(LessonExample.fromJson)
          .toList(growable: false),
      reviewQuestions:
          (content['review_questions'] as List<dynamic>? ?? const [])
              .whereType<String>()
              .toList(growable: false),
      actionPrompt: content['action_prompt'] as String? ?? '',
    );
  }
}
