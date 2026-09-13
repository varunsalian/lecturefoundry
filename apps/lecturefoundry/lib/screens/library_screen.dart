import 'package:flutter/material.dart';

import '../models/library_models.dart';
import '../models/webdav_settings.dart';
import '../services/library_repository.dart';
import '../services/webdav_client.dart';
import '../widgets/content_shell.dart';
import '../widgets/library_card.dart';
import 'course_screen.dart';

class LibraryScreen extends StatefulWidget {
  const LibraryScreen({
    required this.settings,
    required this.onDisconnect,
    super.key,
  });

  final WebDavSettings settings;
  final Future<void> Function() onDisconnect;

  @override
  State<LibraryScreen> createState() => _LibraryScreenState();
}

class _LibraryScreenState extends State<LibraryScreen> {
  late final WebDavClient _client;
  late final LibraryRepository _repository;
  late Future<List<CourseRef>> _courses;

  @override
  void initState() {
    super.initState();
    _client = WebDavClient(widget.settings);
    _repository = LibraryRepository(
      source: _client,
      rootPath: widget.settings.rootPath,
      cacheNamespace: widget.settings.cacheNamespace,
    );
    _refresh();
  }

  void _refresh() {
    setState(() {
      _courses = _repository.listCourses();
    });
  }

  @override
  void dispose() {
    _client.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('LectureFoundry'),
        actions: [
          IconButton(
            onPressed: _refresh,
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh',
          ),
          PopupMenuButton<String>(
            onSelected: (value) {
              if (value == 'disconnect') widget.onDisconnect();
            },
            itemBuilder: (_) => const [
              PopupMenuItem(
                value: 'disconnect',
                child: Text('Disconnect WebDAV'),
              ),
            ],
          ),
        ],
      ),
      body: AsyncPane<List<CourseRef>>(
        future: _courses,
        onRetry: _refresh,
        builder: (context, courses) {
          if (courses.isEmpty) {
            return const EmptyLibrary(
              message:
                  'No course folders were found. Add a course inside your configured library root.',
            );
          }
          return ContentShell(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(28),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [
                        Theme.of(context).colorScheme.primaryContainer,
                        Theme.of(context).colorScheme.tertiaryContainer,
                      ],
                    ),
                    borderRadius: BorderRadius.circular(24),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Your courses',
                        style: Theme.of(context).textTheme.headlineMedium,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '${courses.length} ${courses.length == 1 ? 'course' : 'courses'} synced from WebDAV',
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),
                ...courses.map(
                  (course) => Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: LibraryCard(
                      title: course.name,
                      subtitle: 'Open modules and lectures',
                      icon: Icons.school_outlined,
                      onTap: () => Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => CourseScreen(
                            repository: _repository,
                            course: course,
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
}
