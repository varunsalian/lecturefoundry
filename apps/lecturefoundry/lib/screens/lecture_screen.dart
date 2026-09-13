import 'package:flutter/material.dart';

import '../models/library_models.dart';
import '../services/library_repository.dart';
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
    return FutureBuilder<List<StudyPatternRef>>(
      future: _patterns,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return _LoadingLecture(title: widget.lecture.name);
        }
        if (snapshot.hasError) {
          return _LectureLoadError(
            title: widget.lecture.name,
            error: snapshot.error.toString(),
            onRetry: _refresh,
          );
        }

        final patterns = snapshot.data!;
        if (patterns.isEmpty) {
          return Scaffold(
            appBar: AppBar(title: Text(widget.lecture.name)),
            body: const Center(
              child: Padding(
                padding: EdgeInsets.all(40),
                child: Text(
                  'No generated study patterns were found for this lecture.',
                  textAlign: TextAlign.center,
                ),
              ),
            ),
          );
        }

        final initialPattern = patterns.firstWhere(
          (pattern) => pattern.key == 'revision',
          orElse: () => patterns.first,
        );
        return ReaderScreen(
          repository: widget.repository,
          lecture: widget.lecture,
          patterns: patterns,
          initialPattern: initialPattern,
        );
      },
    );
  }
}

class _LoadingLecture extends StatelessWidget {
  const _LoadingLecture({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(title)),
    body: const Center(child: CircularProgressIndicator()),
  );
}

class _LectureLoadError extends StatelessWidget {
  const _LectureLoadError({
    required this.title,
    required this.error,
    required this.onRetry,
  });

  final String title;
  final String error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(title)),
    body: Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.cloud_off_rounded,
              size: 48,
              color: Theme.of(context).colorScheme.error,
            ),
            const SizedBox(height: 16),
            Text(
              error,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 18),
            FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('Try again'),
            ),
          ],
        ),
      ),
    ),
  );
}
