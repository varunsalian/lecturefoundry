import 'package:flutter/material.dart';

import '../models/library_models.dart';
import '../services/library_repository.dart';
import '../widgets/content_shell.dart';
import '../widgets/library_card.dart';
import 'reader_screen.dart';

class LectureScreen extends StatefulWidget {
  const LectureScreen({
    required this.repository,
    required this.lecture,
    super.key,
  });

  final LibraryRepository repository;
  final LectureRef lecture;

  @override
  State<LectureScreen> createState() => _LectureScreenState();
}

class _LectureScreenState extends State<LectureScreen> {
  late Future<List<StudyPatternRef>> _patterns;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  void _refresh() {
    setState(() {
      _patterns = widget.repository.listPatterns(widget.lecture);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.lecture.name)),
      body: AsyncPane<List<StudyPatternRef>>(
        future: _patterns,
        onRetry: _refresh,
        builder: (context, patterns) {
          if (patterns.isEmpty) {
            return const EmptyLibrary(
              message:
                  'No generated study patterns were found for this lecture.',
            );
          }
          return ContentShell(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'How do you want to study?',
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
                const SizedBox(height: 8),
                Text(
                  'Switch between formats at any time.',
                  style: Theme.of(context).textTheme.bodyLarge,
                ),
                const SizedBox(height: 22),
                ...patterns.map(
                  (pattern) => Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: LibraryCard(
                      title: pattern.name,
                      subtitle: _description(pattern.key),
                      icon: _icon(pattern.key),
                      color: _color(pattern.key),
                      onTap: () => Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => ReaderScreen(
                            repository: widget.repository,
                            lecture: widget.lecture,
                            patterns: patterns,
                            initialPattern: pattern,
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  String _description(String key) => switch (key) {
    'revision' => 'Fast summary and key takeaways',
    'deep-dive' => 'Full explanations and examples',
    'active-recall' => 'Questions that test your memory',
    'concept-map' => 'See how the ideas connect',
    _ => 'Open study notes',
  };

  IconData _icon(String key) => switch (key) {
    'revision' => Icons.bolt_rounded,
    'deep-dive' => Icons.scuba_diving_rounded,
    'active-recall' => Icons.psychology_alt_rounded,
    'concept-map' => Icons.account_tree_rounded,
    _ => Icons.article_outlined,
  };

  Color _color(String key) => switch (key) {
    'revision' => const Color(0xFFF59E0B),
    'deep-dive' => const Color(0xFF2563EB),
    'active-recall' => const Color(0xFF059669),
    'concept-map' => const Color(0xFFDB2777),
    _ => Theme.of(context).colorScheme.primary,
  };
}
