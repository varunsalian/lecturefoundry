import 'package:flutter/material.dart';

import '../models/library_models.dart';
import '../services/library_repository.dart';
import '../widgets/content_shell.dart';
import '../widgets/library_card.dart';
import 'module_screen.dart';

class CourseScreen extends StatefulWidget {
  const CourseScreen({
    required this.repository,
    required this.course,
    super.key,
  });

  final LibraryRepository repository;
  final CourseRef course;

  @override
  State<CourseScreen> createState() => _CourseScreenState();
}

class _CourseScreenState extends State<CourseScreen> {
  late Future<List<ModuleRef>> _modules;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  void _refresh() => setState(() {
    _modules = widget.repository.listModules(widget.course);
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.course.name)),
      body: AsyncPane<List<ModuleRef>>(
        future: _modules,
        onRetry: _refresh,
        builder: (context, modules) {
          if (modules.isEmpty) {
            return const EmptyLibrary(
              message: 'No numbered module folders were found in this course.',
            );
          }
          return ContentShell(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Modules',
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
                const SizedBox(height: 8),
                Text(
                  'Choose a module to continue.',
                  style: Theme.of(context).textTheme.bodyLarge,
                ),
                const SizedBox(height: 22),
                ...modules.map(
                  (module) => Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: LibraryCard(
                      title: module.name,
                      subtitle: 'Module ${module.number}',
                      icon: Icons.view_module_outlined,
                      number: module.number,
                      onTap: () => Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => ModuleScreen(
                            repository: widget.repository,
                            module: module,
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
