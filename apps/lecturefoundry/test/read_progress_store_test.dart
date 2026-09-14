import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:lecturefoundry/services/read_progress_store.dart';

void main() {
  test('persists read state and isolates WebDAV accounts', () async {
    final temporary = await Directory.systemTemp.createTemp(
      'lecturefoundry-read-progress-',
    );
    addTearDown(() => temporary.delete(recursive: true));
    Future<Directory> directoryProvider() async => temporary;

    final first = ReadProgressStore(
      namespace: 'server-a\nuser-a',
      directoryProvider: directoryProvider,
    );
    const lecture = '/course/01-module/01-lecture/';

    expect(await first.isRead(lecture), isFalse);
    await first.setRead(lecture, isRead: true);

    final reloaded = ReadProgressStore(
      namespace: 'server-a\nuser-a',
      directoryProvider: directoryProvider,
    );
    final otherAccount = ReadProgressStore(
      namespace: 'server-a\nuser-b',
      directoryProvider: directoryProvider,
    );
    expect(await reloaded.isRead(lecture), isTrue);
    expect(await otherAccount.isRead(lecture), isFalse);

    await reloaded.setRead(lecture, isRead: false);
    final cleared = ReadProgressStore(
      namespace: 'server-a\nuser-a',
      directoryProvider: directoryProvider,
    );
    expect(await cleared.isRead(lecture), isFalse);
  });

  test('recovers from malformed local progress data', () async {
    final temporary = await Directory.systemTemp.createTemp(
      'lecturefoundry-read-progress-',
    );
    addTearDown(() => temporary.delete(recursive: true));
    Future<Directory> directoryProvider() async => temporary;
    const lecture = '/course/01-module/01-lecture/';
    final initial = ReadProgressStore(
      namespace: 'server\nuser',
      directoryProvider: directoryProvider,
    );
    await initial.setRead(lecture, isRead: true);
    final file = Directory(
      '${temporary.path}/read-progress',
    ).listSync().whereType<File>().single;
    await file.writeAsString('{"read":"not-a-list"}');

    final recovered = ReadProgressStore(
      namespace: 'server\nuser',
      directoryProvider: directoryProvider,
    );
    expect(await recovered.isRead(lecture), isFalse);
    await recovered.setRead(lecture, isRead: true);
    expect(await recovered.isRead(lecture), isTrue);
  });
}
