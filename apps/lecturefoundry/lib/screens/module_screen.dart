import 'package:flutter/material.dart';

import '../models/library_models.dart';
import '../services/library_repository.dart';
import '../widgets/content_shell.dart';
import '../widgets/library_card.dart';
import 'lecture_screen.dart';

class ModuleScreen extends StatefulWidget {
  const ModuleScreen({
    required this.repository,
    required this.module,
    super.key,
  });

  final LibraryRepository repository;
  final ModuleRef module;

  @override
  State<ModuleScreen> createState() => _ModuleScreenState();
}

class _ModuleScreenState extends State<ModuleScreen> {
  late Future<List<LectureRef>> _lectures;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  void _refresh() => setState(() {
    _lectures = widget.repository.listLectures(widget.module);
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.module.name)),
      body: AsyncPane<List<LectureRef>>(
        future: _lectures,
        onRetry: _refresh,
        builder: (context, lectures) {
          if (lectures.isEmpty) {
            return const EmptyLibrary(
              message: 'No numbered lecture folders were found in this module.',
            );
          }
          return ContentShell(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Lectures',
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
                const SizedBox(height: 22),
                ...lectures.map(
                  (lecture) => Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: LibraryCard(
                      title: lecture.name,
                      subtitle: 'Lecture ${lecture.number}',
                      icon: Icons.play_lesson_outlined,
                      number: lecture.number,
                      isRead: lecture.isRead,
                      onTap: () async {
                        await Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) => LectureScreen(
                              repository: widget.repository,
                              lecture: lecture,
                            ),
                          ),
                        );
                        if (mounted) _refresh();
                      },
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
}
