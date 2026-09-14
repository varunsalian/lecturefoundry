import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lecturefoundry/widgets/library_card.dart';

void main() {
  testWidgets('shows a completion tick for a read lecture', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: LibraryCard(
            title: 'Lecture',
            subtitle: 'Lecture 1',
            icon: Icons.play_lesson_outlined,
            isRead: true,
            onTap: () {},
          ),
        ),
      ),
    );

    final tick = tester.widget<Icon>(find.byIcon(Icons.check_circle_rounded));
    expect(tick.semanticLabel, 'Read');
  });
}
