import 'dart:convert';
import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:lecturefoundry/models/webdav_settings.dart';
import 'package:lecturefoundry/services/webdav_client.dart';

void main() {
  test('parses a WebDAV multistatus listing and ignores the parent', () {
    const xml = '''<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:">
  <d:response>
    <d:href>/dav/Our%20Project/</d:href>
    <d:propstat><d:prop><d:displayname>Our Project</d:displayname>
      <d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat>
  </d:response>
  <d:response>
    <d:href>/dav/Our%20Project/the-science-of-well-being/</d:href>
    <d:propstat><d:prop><d:displayname>The Science of Well-being</d:displayname>
      <d:resourcetype><d:collection/></d:resourcetype>
      <d:getetag>"abc"</d:getetag></d:prop></d:propstat>
  </d:response>
  <d:response>
    <d:href>/dav/Our%20Project/readme.txt</d:href>
    <d:propstat><d:prop><d:displayname>readme.txt</d:displayname>
      <d:resourcetype/><d:getcontentlength>42</d:getcontentlength></d:prop></d:propstat>
  </d:response>
</d:multistatus>''';

    final entries = parseMultiStatus(
      xml,
      requestedPath: '/Our Project/',
      requestedUriPath: '/dav/Our%20Project/',
    );

    expect(entries, hasLength(2));
    final readme = entries.singleWhere(
      (entry) => entry.displayName == 'readme.txt',
    );
    final course = entries.singleWhere((entry) => entry.isCollection);
    expect(readme.contentLength, 42);
    expect(course.displayName, 'The Science of Well-being');
    expect(course.path, '/Our Project/the-science-of-well-being/');
  });

  test('rejects invalid multistatus XML with a safe error', () {
    expect(
      () => parseMultiStatus(
        'not xml',
        requestedPath: '/',
        requestedUriPath: '/dav/',
      ),
      throwsA(isA<WebDavException>()),
    );
  });

  test('sends an authenticated Depth 1 PROPFIND to an encoded path', () async {
    late http.Request captured;
    final transport = MockClient((request) async {
      captured = request;
      return http.Response(
        '<d:multistatus xmlns:d="DAV:"></d:multistatus>',
        207,
      );
    });
    final client = WebDavClient(
      const WebDavSettings(
        endpoint: 'https://cloud.example/dav/',
        username: 'demo',
        password: 'test-password',
        rootPath: '/Our Project/',
      ),
      client: transport,
    );

    await client.list('/Our Project/');

    expect(captured.method, 'PROPFIND');
    expect(captured.url.toString(), 'https://cloud.example/dav/Our%20Project/');
    expect(captured.headers['Depth'], '1');
    expect(
      captured.headers['Authorization'],
      'Basic ${base64Encode(utf8.encode('demo:test-password'))}',
    );
    client.close();
  });

  test('times out when a PROPFIND body stalls after its headers', () async {
    final transport = _StallingClient();
    final client = WebDavClient(
      const WebDavSettings(
        endpoint: 'https://cloud.example/dav/',
        username: 'demo',
        password: 'test-password',
        rootPath: '/',
      ),
      client: transport,
      requestTimeout: const Duration(milliseconds: 10),
    );

    await expectLater(
      client.list('/'),
      throwsA(
        isA<WebDavException>().having(
          (error) => error.message,
          'message',
          contains('too long to send'),
        ),
      ),
    );
    client.close();
  });

  test('uploads UTF-8 JSON to an encoded WebDAV path', () async {
    late http.Request captured;
    final transport = MockClient((request) async {
      captured = request;
      return http.Response('', 204, headers: {'etag': '"next"'});
    });
    final client = WebDavClient(
      const WebDavSettings(
        endpoint: 'https://cloud.example/dav/',
        username: 'demo',
        password: 'test-password',
        rootPath: '/Our Project/',
      ),
      client: transport,
    );

    final etag = await client.uploadText(
      '/Our Project/My Course/.lecturefoundry-progress.json',
      '{"title":"Café"}\n',
      ifMatch: '"current"',
    );

    expect(captured.method, 'PUT');
    expect(
      captured.url.toString(),
      'https://cloud.example/dav/Our%20Project/My%20Course/.lecturefoundry-progress.json',
    );
    expect(captured.headers['Content-Type'], contains('application/json'));
    expect(captured.headers['If-Match'], '"current"');
    expect(utf8.decode(captured.bodyBytes), '{"title":"Café"}\n');
    expect(etag, '"next"');
    client.close();
  });

  test('returns an ETag with downloaded text', () async {
    final client = WebDavClient(
      const WebDavSettings(
        endpoint: 'https://cloud.example/dav/',
        username: 'demo',
        password: 'test-password',
        rootPath: '/',
      ),
      client: MockClient(
        (_) async =>
            http.Response('{"version":1}', 200, headers: {'etag': '"current"'}),
      ),
    );

    final resource = await client.downloadTextResource('/progress.json');

    expect(resource.contents, '{"version":1}');
    expect(resource.etag, '"current"');
    client.close();
  });

  test('reports a conditional upload conflict', () async {
    final client = WebDavClient(
      const WebDavSettings(
        endpoint: 'https://cloud.example/dav/',
        username: 'demo',
        password: 'test-password',
        rootPath: '/',
      ),
      client: MockClient((_) async => http.Response('', 412)),
    );

    await expectLater(
      client.uploadText('/progress.json', '{}', ifMatch: '"old"'),
      throwsA(isA<WebDavConflictException>()),
    );
    client.close();
  });
}

class _StallingClient extends http.BaseClient {
  final StreamController<List<int>> _controller = StreamController();

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async =>
      http.StreamedResponse(_controller.stream, 207);

  @override
  void close() {
    _controller.close();
    super.close();
  }
}
