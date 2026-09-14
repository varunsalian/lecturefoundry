import 'package:flutter/material.dart';

import '../models/library_models.dart';
import '../services/library_repository.dart';
import '../widgets/content_shell.dart';

class ReaderScreen extends StatefulWidget {
  const ReaderScreen({
    required this.repository,
    required this.lecture,
    required this.patterns,
    required this.initialPattern,
    super.key,
  });

  final LibraryRepository repository;
  final LectureRef lecture;
  final List<StudyPatternRef> patterns;
  final StudyPatternRef initialPattern;

  @override
  State<ReaderScreen> createState() => _ReaderScreenState();
}

class _ReaderScreenState extends State<ReaderScreen> {
  late StudyPatternRef _selected;
  late Future<LessonDocument> _lesson;
  late bool _isRead;
  bool _savingReadState = false;

  @override
  void initState() {
    super.initState();
    _selected = widget.initialPattern;
    _isRead = widget.lecture.isRead;
    _load();
  }

  void _load() => setState(() {
    _lesson = widget.repository.loadLesson(_selected);
  });

  void _select(StudyPatternRef pattern) {
    if (pattern.key == _selected.key) return;
    _selected = pattern;
    _load();
  }

  Future<void> _toggleRead() async {
    if (_savingReadState) return;
    final previous = _isRead;
    setState(() {
      _isRead = !previous;
      _savingReadState = true;
    });
    try {
      await widget.repository.setLectureRead(widget.lecture, isRead: _isRead);
    } catch (_) {
      if (!mounted) return;
      setState(() => _isRead = previous);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not save reading progress.')),
      );
    } finally {
      if (mounted) setState(() => _savingReadState = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.lecture.name),
        actions: [
          IconButton(
            onPressed: _savingReadState ? null : _toggleRead,
            icon: Icon(
              _isRead
                  ? Icons.check_circle_rounded
                  : Icons.check_circle_outline_rounded,
            ),
            tooltip: _isRead ? 'Mark as unread' : 'Mark as read',
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: Column(
        children: [
          Material(
            color: Theme.of(context).colorScheme.surface,
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
              child: Row(
                children: widget.patterns
                    .map(
                      (pattern) => Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: ChoiceChip(
                          label: Text(pattern.name),
                          selected: pattern.key == _selected.key,
                          onSelected: (_) => _select(pattern),
                        ),
                      ),
                    )
                    .toList(growable: false),
              ),
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: FutureBuilder<LessonDocument>(
              future: _lesson,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snapshot.hasError) {
                  return _ReaderError(
                    error: snapshot.error.toString(),
                    onRetry: _load,
                  );
                }
                return ContentShell(
                  maxWidth: 820,
                  child: _LessonView(lesson: snapshot.data!),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _LessonView extends StatelessWidget {
  const _LessonView({required this.lesson});

  final LessonDocument lesson;

  @override
  Widget build(BuildContext context) {
    final activeRecall = lesson.patternKey == 'active-recall';
    final conceptMap = lesson.patternKey == 'concept-map';
    return SelectionArea(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'MODULE ${lesson.moduleNumber.toString().padLeft(2, '0')}  ·  LECTURE ${lesson.lectureNumber.toString().padLeft(2, '0')}',
            style: TextStyle(
              color: Theme.of(context).colorScheme.primary,
              fontWeight: FontWeight.w800,
              letterSpacing: 1.2,
            ),
          ),
          const SizedBox(height: 12),
          Text(lesson.title, style: Theme.of(context).textTheme.displaySmall),
          if (lesson.subtitle.isNotEmpty) ...[
            const SizedBox(height: 10),
            Text(lesson.subtitle, style: Theme.of(context).textTheme.bodyLarge),
          ],
          const SizedBox(height: 26),
          _KeyIdea(text: lesson.keyIdea),
          if (lesson.summary.isNotEmpty) ...[
            const SizedBox(height: 26),
            _SectionTitle('In a nutshell'),
            const SizedBox(height: 10),
            Text(lesson.summary, style: Theme.of(context).textTheme.bodyLarge),
          ],
          const SizedBox(height: 28),
          if (conceptMap)
            _ConceptMap(sections: lesson.sections)
          else ...[
            _SectionTitle(activeRecall ? 'Recall the lesson' : 'Lesson notes'),
            const SizedBox(height: 12),
            ...lesson.sections.map(
              (section) => Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: activeRecall
                    ? _RevealCard(section: section)
                    : _LessonSectionCard(section: section),
              ),
            ),
          ],
          if (lesson.examples.isNotEmpty) ...[
            const SizedBox(height: 16),
            _SectionTitle('Examples'),
            const SizedBox(height: 12),
            ...lesson.examples.map(
              (example) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.lightbulb_outline_rounded),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                example.title,
                                style: Theme.of(context).textTheme.titleMedium,
                              ),
                              const SizedBox(height: 7),
                              Text(example.explanation),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ],
          if (lesson.reviewQuestions.isNotEmpty) ...[
            const SizedBox(height: 18),
            _SectionTitle('Check your understanding'),
            const SizedBox(height: 12),
            ...lesson.reviewQuestions.indexed.map(
              (item) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(18),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        CircleAvatar(radius: 15, child: Text('${item.$1 + 1}')),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Text(
                            item.$2,
                            style: Theme.of(context).textTheme.bodyLarge,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ],
          if (lesson.actionPrompt.isNotEmpty) ...[
            const SizedBox(height: 18),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(22),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.secondaryContainer,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Put it into practice',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    lesson.actionPrompt,
                    style: Theme.of(context).textTheme.bodyLarge,
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _KeyIdea extends StatelessWidget {
  const _KeyIdea({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    if (text.isEmpty) return const SizedBox.shrink();
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.primaryContainer,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'KEY IDEA',
            style: TextStyle(
              color: Theme.of(context).colorScheme.primary,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 8),
          Text(text, style: Theme.of(context).textTheme.titleLarge),
        ],
      ),
    );
  }
}

class _LessonSectionCard extends StatelessWidget {
  const _LessonSectionCard({required this.section});

  final LessonSection section;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              section.heading,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            if (section.body.isNotEmpty) ...[
              const SizedBox(height: 9),
              Text(section.body, style: Theme.of(context).textTheme.bodyLarge),
            ],
            ...section.bullets.map(
              (bullet) => Padding(
                padding: const EdgeInsets.only(top: 9),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Padding(
                      padding: EdgeInsets.only(top: 3),
                      child: Icon(Icons.arrow_right_rounded, size: 20),
                    ),
                    const SizedBox(width: 7),
                    Expanded(child: Text(bullet)),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _RevealCard extends StatefulWidget {
  const _RevealCard({required this.section});

  final LessonSection section;

  @override
  State<_RevealCard> createState() => _RevealCardState();
}

class _RevealCardState extends State<_RevealCard> {
  bool _revealed = false;

  @override
  Widget build(BuildContext context) {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => setState(() => _revealed = !_revealed),
        child: Padding(
          padding: const EdgeInsets.all(22),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      widget.section.heading,
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                  ),
                  Icon(
                    _revealed
                        ? Icons.expand_less_rounded
                        : Icons.visibility_outlined,
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                _revealed ? 'Tap to hide' : 'Think first, then tap to reveal',
              ),
              if (_revealed) ...[
                const Divider(height: 28),
                if (widget.section.body.isNotEmpty) Text(widget.section.body),
                ...widget.section.bullets.map(
                  (bullet) => Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text('•  $bullet'),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _ConceptMap extends StatelessWidget {
  const _ConceptMap({required this.sections});

  final List<LessonSection> sections;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _SectionTitle('Concept flow'),
        const SizedBox(height: 12),
        ...sections.indexed.map(
          (item) => Column(
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  CircleAvatar(child: Text('${item.$1 + 1}')),
                  const SizedBox(width: 14),
                  Expanded(child: _LessonSectionCard(section: item.$2)),
                ],
              ),
              if (item.$1 < sections.length - 1)
                Container(
                  width: 2,
                  height: 22,
                  margin: const EdgeInsets.only(left: 19),
                  color: Theme.of(
                    context,
                  ).colorScheme.primary.withValues(alpha: 0.35),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);

  final String text;

  @override
  Widget build(BuildContext context) =>
      Text(text, style: Theme.of(context).textTheme.headlineMedium);
}

class _ReaderError extends StatelessWidget {
  const _ReaderError({required this.error, required this.onRetry});

  final String error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.error_outline_rounded, size: 48),
          const SizedBox(height: 12),
          Text(error, textAlign: TextAlign.center),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: const Text('Try again'),
          ),
        ],
      ),
    );
  }
}
