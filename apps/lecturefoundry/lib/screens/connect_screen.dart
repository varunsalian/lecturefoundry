import 'package:flutter/material.dart';

import '../models/webdav_settings.dart';
import '../services/credential_store.dart';
import '../services/webdav_client.dart';
import '../widgets/content_shell.dart';

class ConnectScreen extends StatefulWidget {
  const ConnectScreen({
    required this.credentialStore,
    required this.onConnected,
    super.key,
  });

  final CredentialStore credentialStore;
  final ValueChanged<WebDavSettings> onConnected;

  @override
  State<ConnectScreen> createState() => _ConnectScreenState();
}

class _ConnectScreenState extends State<ConnectScreen> {
  final _formKey = GlobalKey<FormState>();
  final _endpoint = TextEditingController(
    text: 'https://app.koofr.net/dav/Koofr/',
  );
  final _username = TextEditingController();
  final _password = TextEditingController();
  final _root = TextEditingController(text: '/Our Project/');
  bool _obscurePassword = true;
  bool _connecting = false;
  String? _error;

  @override
  void dispose() {
    _endpoint.dispose();
    _username.dispose();
    _password.dispose();
    _root.dispose();
    super.dispose();
  }

  Future<void> _connect() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _connecting = true;
      _error = null;
    });
    final settings = WebDavSettings(
      endpoint: _endpoint.text,
      username: _username.text,
      password: _password.text,
      rootPath: _root.text,
    ).normalized();
    final client = WebDavClient(settings);
    try {
      await client.testConnection();
      await widget.credentialStore.save(settings);
      if (mounted) widget.onConnected(settings);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      client.close();
      if (mounted) setState(() => _connecting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: ContentShell(
        maxWidth: 620,
        child: Padding(
          padding: const EdgeInsets.only(top: 36),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Align(
                  alignment: Alignment.centerLeft,
                  child: Container(
                    width: 62,
                    height: 62,
                    decoration: BoxDecoration(
                      color: Theme.of(context).colorScheme.primaryContainer,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Icon(
                      Icons.auto_stories_rounded,
                      color: Theme.of(context).colorScheme.primary,
                      size: 32,
                    ),
                  ),
                ),
                const SizedBox(height: 28),
                Text(
                  'Your learning library, anywhere.',
                  style: Theme.of(context).textTheme.displaySmall,
                ),
                const SizedBox(height: 12),
                Text(
                  'Connect directly to the WebDAV folder that contains your generated LectureFoundry notes.',
                  style: Theme.of(context).textTheme.bodyLarge,
                ),
                const SizedBox(height: 30),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(22),
                    child: Column(
                      children: [
                        _field(
                          controller: _endpoint,
                          label: 'WebDAV endpoint',
                          icon: Icons.cloud_outlined,
                          keyboardType: TextInputType.url,
                          validateHttps: true,
                        ),
                        const SizedBox(height: 14),
                        _field(
                          controller: _username,
                          label: 'Username',
                          icon: Icons.person_outline_rounded,
                          keyboardType: TextInputType.emailAddress,
                        ),
                        const SizedBox(height: 14),
                        TextFormField(
                          controller: _password,
                          obscureText: _obscurePassword,
                          autofillHints: const [AutofillHints.password],
                          decoration: InputDecoration(
                            labelText: 'WebDAV app password',
                            prefixIcon: const Icon(Icons.key_rounded),
                            suffixIcon: IconButton(
                              onPressed: () => setState(
                                () => _obscurePassword = !_obscurePassword,
                              ),
                              icon: Icon(
                                _obscurePassword
                                    ? Icons.visibility_rounded
                                    : Icons.visibility_off_rounded,
                              ),
                              tooltip: _obscurePassword
                                  ? 'Show password'
                                  : 'Hide password',
                            ),
                          ),
                          validator: _required,
                          onFieldSubmitted: (_) => _connect(),
                        ),
                        const SizedBox(height: 14),
                        _field(
                          controller: _root,
                          label: 'Library root folder',
                          icon: Icons.folder_outlined,
                        ),
                      ],
                    ),
                  ),
                ),
                if (_error != null) ...[
                  const SizedBox(height: 16),
                  Text(
                    _error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ],
                const SizedBox(height: 20),
                FilledButton.icon(
                  onPressed: _connecting ? null : _connect,
                  icon: _connecting
                      ? const SizedBox.square(
                          dimension: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.link_rounded),
                  label: Text(_connecting ? 'Connecting…' : 'Connect library'),
                  style: FilledButton.styleFrom(
                    minimumSize: const Size.fromHeight(54),
                  ),
                ),
                const SizedBox(height: 14),
                const Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.lock_outline_rounded, size: 18),
                    SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Credentials are saved in this device’s secure credential store. Notes travel directly between this app and your WebDAV provider.',
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  TextFormField _field({
    required TextEditingController controller,
    required String label,
    required IconData icon,
    TextInputType? keyboardType,
    bool validateHttps = false,
  }) {
    return TextFormField(
      controller: controller,
      keyboardType: keyboardType,
      autocorrect: false,
      decoration: InputDecoration(labelText: label, prefixIcon: Icon(icon)),
      validator: (value) {
        final requiredError = _required(value);
        if (requiredError != null) return requiredError;
        if (validateHttps) {
          final uri = Uri.tryParse(value!.trim());
          final localDevelopment =
              uri?.host == 'localhost' || uri?.host == '127.0.0.1';
          if (uri == null ||
              (uri.scheme != 'https' &&
                  !(uri.scheme == 'http' && localDevelopment))) {
            return 'Enter an HTTPS endpoint (or localhost for development).';
          }
        }
        return null;
      },
    );
  }

  String? _required(String? value) =>
      value == null || value.trim().isEmpty ? 'This field is required.' : null;
}
