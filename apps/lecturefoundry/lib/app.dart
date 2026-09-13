import 'package:flutter/material.dart';

import 'models/webdav_settings.dart';
import 'screens/connect_screen.dart';
import 'screens/library_screen.dart';
import 'services/credential_store.dart';

class LectureFoundryApp extends StatefulWidget {
  const LectureFoundryApp({super.key});

  @override
  State<LectureFoundryApp> createState() => _LectureFoundryAppState();
}

class _LectureFoundryAppState extends State<LectureFoundryApp> {
  final CredentialStore _credentialStore = CredentialStore();
  late Future<WebDavSettings?> _savedSettings;

  @override
  void initState() {
    super.initState();
    _savedSettings = _credentialStore.read();
  }

  void _useSettings(WebDavSettings settings) {
    setState(() {
      _savedSettings = Future.value(settings);
    });
  }

  Future<void> _disconnect() async {
    await _credentialStore.clear();
    if (mounted) {
      setState(() {
        _savedSettings = Future.value();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    const seed = Color(0xFF6D28D9);
    return MaterialApp(
      title: 'LectureFoundry',
      debugShowCheckedModeBanner: false,
      themeMode: ThemeMode.system,
      theme: _theme(Brightness.light, seed),
      darkTheme: _theme(Brightness.dark, seed),
      home: FutureBuilder<WebDavSettings?>(
        future: _savedSettings,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const _StartupScreen();
          }
          final settings = snapshot.data;
          if (settings == null) {
            return ConnectScreen(
              credentialStore: _credentialStore,
              onConnected: _useSettings,
            );
          }
          return LibraryScreen(settings: settings, onDisconnect: _disconnect);
        },
      ),
    );
  }

  ThemeData _theme(Brightness brightness, Color seed) {
    final scheme = ColorScheme.fromSeed(
      seedColor: seed,
      brightness: brightness,
      surface: brightness == Brightness.light
          ? const Color(0xFFFAFAF9)
          : const Color(0xFF111113),
    );
    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: scheme.surface,
      textTheme: const TextTheme(
        displaySmall: TextStyle(fontWeight: FontWeight.w800, letterSpacing: -1),
        headlineMedium: TextStyle(
          fontWeight: FontWeight.w800,
          letterSpacing: -0.6,
        ),
        titleLarge: TextStyle(fontWeight: FontWeight.w800),
        titleMedium: TextStyle(fontWeight: FontWeight.w700),
        bodyLarge: TextStyle(height: 1.55),
        bodyMedium: TextStyle(height: 1.5),
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        margin: EdgeInsets.zero,
        color: brightness == Brightness.light
            ? Colors.white
            : const Color(0xFF1A1A1F),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: BorderSide(color: scheme.outlineVariant.withValues(alpha: 0.6)),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: scheme.surfaceContainerLow,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
      ),
    );
  }
}

class _StartupScreen extends StatelessWidget {
  const _StartupScreen();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(body: Center(child: CircularProgressIndicator()));
  }
}
