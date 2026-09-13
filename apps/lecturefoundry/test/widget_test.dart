import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lecturefoundry/app.dart';

void main() {
  testWidgets('shows the WebDAV connection form on first launch', (
    tester,
  ) async {
    FlutterSecureStorage.setMockInitialValues({});
    await tester.pumpWidget(const LectureFoundryApp());
    await tester.pumpAndSettle();

    expect(find.text('Your learning library, anywhere.'), findsOneWidget);
    expect(find.text('WebDAV endpoint'), findsOneWidget);
    expect(find.text('Connect library'), findsOneWidget);
  });
}
