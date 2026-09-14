import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:xml/xml.dart';

import '../models/webdav_settings.dart';

abstract interface class WebDavDataSource {
  Future<List<WebDavEntry>> list(String remotePath);
  Future<String> downloadText(String remotePath);
}

abstract interface class WebDavWritableDataSource {
  Future<String?> uploadText(
    String remotePath,
    String contents, {
    String? ifMatch,
    bool createOnly = false,
  });
}

abstract interface class WebDavVersionedDataSource {
  Future<WebDavTextResource> downloadTextResource(String remotePath);
}

class WebDavTextResource {
  const WebDavTextResource({required this.contents, required this.etag});

  final String contents;
  final String? etag;
}

class WebDavEntry {
  const WebDavEntry({
    required this.displayName,
    required this.path,
    required this.isCollection,
    this.etag,
    this.lastModified,
    this.contentLength,
  });

  final String displayName;
  final String path;
  final bool isCollection;
  final String? etag;
  final DateTime? lastModified;
  final int? contentLength;
}

class WebDavException implements Exception {
  const WebDavException(this.message);

  final String message;

  @override
  String toString() => message;
}

class WebDavNotFoundException extends WebDavException {
  const WebDavNotFoundException(super.message);
}

class WebDavConflictException extends WebDavException {
  const WebDavConflictException(super.message);
}

class WebDavClient
    implements
        WebDavDataSource,
        WebDavWritableDataSource,
        WebDavVersionedDataSource {
  WebDavClient(
    this.settings, {
    http.Client? client,
    this.requestTimeout = const Duration(seconds: 25),
  }) : _client = client ?? http.Client();

  final WebDavSettings settings;
  final http.Client _client;
  final Duration requestTimeout;

  Future<void> testConnection() async {
    await list(settings.rootPath);
  }

  @override
  Future<List<WebDavEntry>> list(String remotePath) async {
    final uri = _buildUri(remotePath, collection: true);
    final request = http.Request('PROPFIND', uri)
      ..headers.addAll(_headers)
      ..headers['Depth'] = '1'
      ..headers['Content-Type'] = 'application/xml; charset=utf-8'
      ..body = '''<?xml version="1.0" encoding="utf-8" ?>
<d:propfind xmlns:d="DAV:"><d:prop><d:displayname/><d:resourcetype/>
<d:getetag/><d:getlastmodified/><d:getcontentlength/></d:prop></d:propfind>''';
    late final http.StreamedResponse response;
    try {
      response = await _client.send(request).timeout(requestTimeout);
    } on TimeoutException {
      throw const WebDavException(
        'The WebDAV server took too long to respond.',
      );
    } on http.ClientException {
      throw const WebDavException(
        'Could not reach the WebDAV server. Check the endpoint and network.',
      );
    }
    late final String body;
    try {
      body = await http.ByteStream(
        response.stream.timeout(requestTimeout),
      ).bytesToString();
    } on TimeoutException {
      throw const WebDavException(
        'The WebDAV server took too long to send its response.',
      );
    } on http.ClientException {
      throw const WebDavException(
        'The WebDAV connection ended before the response was complete.',
      );
    }
    _checkStatus(response.statusCode, remotePath);
    if (response.statusCode != 207) {
      throw WebDavException(
        'The server returned HTTP ${response.statusCode} instead of a WebDAV listing.',
      );
    }
    return parseMultiStatus(
      body,
      requestedPath: remotePath,
      requestedUriPath: uri.path,
    );
  }

  @override
  Future<String> downloadText(String remotePath) async =>
      (await downloadTextResource(remotePath)).contents;

  @override
  Future<WebDavTextResource> downloadTextResource(String remotePath) async {
    late final http.Response response;
    try {
      response = await _client
          .get(_buildUri(remotePath), headers: _headers)
          .timeout(requestTimeout);
    } on TimeoutException {
      throw const WebDavException(
        'The WebDAV server took too long to respond.',
      );
    } on http.ClientException {
      throw const WebDavException(
        'Could not reach the WebDAV server. Check the endpoint and network.',
      );
    }
    _checkStatus(response.statusCode, remotePath);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw WebDavException(
        'Could not download this note (HTTP ${response.statusCode}).',
      );
    }
    return WebDavTextResource(
      contents: utf8.decode(response.bodyBytes),
      etag: response.headers['etag'],
    );
  }

  @override
  Future<String?> uploadText(
    String remotePath,
    String contents, {
    String? ifMatch,
    bool createOnly = false,
  }) async {
    late final http.Response response;
    try {
      response = await _client
          .put(
            _buildUri(remotePath),
            headers: {
              ..._headers,
              'Content-Type': 'application/json; charset=utf-8',
              'If-Match': ?ifMatch,
              if (createOnly) 'If-None-Match': '*',
            },
            body: utf8.encode(contents),
          )
          .timeout(requestTimeout);
    } on TimeoutException {
      throw const WebDavException(
        'The WebDAV server took too long to save reading progress.',
      );
    } on http.ClientException {
      throw const WebDavException(
        'Could not reach the WebDAV server to save reading progress.',
      );
    }
    if (response.statusCode == 409 || response.statusCode == 412) {
      throw const WebDavConflictException(
        'Reading progress changed on another device.',
      );
    }
    _checkStatus(response.statusCode, remotePath);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw WebDavException(
        'Could not save reading progress (HTTP ${response.statusCode}).',
      );
    }
    return response.headers['etag'];
  }

  void close() => _client.close();

  Map<String, String> get _headers => {
    'Authorization':
        'Basic ${base64Encode(utf8.encode('${settings.username}:${settings.password}'))}',
    'Accept': 'application/xml, application/json, text/plain, */*',
  };

  Uri _buildUri(String remotePath, {bool collection = false}) {
    final base = Uri.parse(settings.endpoint);
    final localDevelopment =
        base.host == 'localhost' || base.host == '127.0.0.1';
    if (base.scheme != 'https' &&
        !(base.scheme == 'http' && localDevelopment)) {
      throw const WebDavException(
        'Use an HTTPS WebDAV endpoint so your credentials are encrypted in transit.',
      );
    }
    final normalized = normalizeRemotePath(remotePath, collection: collection);
    final segments = <String>[
      ...base.pathSegments.where((segment) => segment.isNotEmpty),
      ...normalized.split('/').where((segment) => segment.isNotEmpty),
    ];
    if (collection) segments.add('');
    return base.replace(pathSegments: segments, query: null, fragment: null);
  }

  void _checkStatus(int status, String remotePath) {
    if (status == 401 || status == 403) {
      throw const WebDavException(
        'Sign-in failed. Check the username and WebDAV app password.',
      );
    }
    if (status == 404) {
      throw WebDavNotFoundException('Cloud item not found: $remotePath');
    }
  }
}

List<WebDavEntry> parseMultiStatus(
  String source, {
  required String requestedPath,
  required String requestedUriPath,
}) {
  late final XmlDocument document;
  try {
    document = XmlDocument.parse(source);
  } on XmlParserException {
    throw const WebDavException('The server returned invalid WebDAV XML.');
  }

  final entries = <WebDavEntry>[];
  for (final response in document.descendants.whereType<XmlElement>().where(
    (node) => node.name.local == 'response',
  )) {
    String? textOf(String name) {
      final matches = response.descendants.whereType<XmlElement>().where(
        (node) => node.name.local == name,
      );
      return matches.isEmpty ? null : matches.first.innerText.trim();
    }

    final href = textOf('href') ?? '';
    final hrefPath = Uri.tryParse(href)?.path ?? href;
    if (_sameCollection(hrefPath, requestedUriPath)) continue;

    final rawName = textOf('displayname');
    final fallback = Uri.decodeComponent(
      hrefPath.split('/').where((part) => part.isNotEmpty).lastOrNull ?? '',
    );
    final name = (rawName == null || rawName.isEmpty) ? fallback : rawName;
    if (name.isEmpty) continue;
    // displayname is a label and is not guaranteed to be the URL segment.
    final pathName = fallback.isEmpty ? name : fallback;

    final resourceType = response.descendants.whereType<XmlElement>().where(
      (node) => node.name.local == 'resourcetype',
    );
    final isCollection = resourceType.any(
      (node) => node.descendants.whereType<XmlElement>().any(
        (child) => child.name.local == 'collection',
      ),
    );
    entries.add(
      WebDavEntry(
        displayName: name,
        path: joinRemotePath(requestedPath, pathName, collection: isCollection),
        isCollection: isCollection,
        etag: textOf('getetag'),
        lastModified: DateTime.tryParse(textOf('getlastmodified') ?? ''),
        contentLength: int.tryParse(textOf('getcontentlength') ?? ''),
      ),
    );
  }
  entries.sort((a, b) => a.displayName.compareTo(b.displayName));
  return entries;
}

bool _sameCollection(String left, String right) {
  String clean(String value) {
    final decoded = Uri.decodeComponent(value);
    return decoded.length > 1 && decoded.endsWith('/')
        ? decoded.substring(0, decoded.length - 1)
        : decoded;
  }

  return clean(left) == clean(right);
}
