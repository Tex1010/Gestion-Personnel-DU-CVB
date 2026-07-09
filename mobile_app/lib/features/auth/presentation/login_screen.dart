import 'package:flutter/material.dart';

import '../data/mobile_api_client.dart';
import '../../home/presentation/home_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({
    super.key,
    required this.apiClient,
  });

  final MobileApiClient apiClient;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  String _selectedRole = 'user';
  bool _isSubmitting = false;
  String? _errorMessage;

  static const _roleOptions = <DropdownMenuItem<String>>[
    DropdownMenuItem(value: 'user', child: Text('Employe')),
    DropdownMenuItem(value: 'hierarchical', child: Text('Chef hierarchique')),
    DropdownMenuItem(value: 'admin', child: Text('Administration')),
    DropdownMenuItem(value: 'direction', child: Text('Direction')),
  ];

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    FocusScope.of(context).unfocus();
    if (!_formKey.currentState!.validate()) {
      return;
    }

    setState(() {
      _isSubmitting = true;
      _errorMessage = null;
    });

    try {
      final session = await widget.apiClient.login(
        username: _usernameController.text.trim(),
        password: _passwordController.text,
        role: _selectedRole,
      );

      if (!mounted) {
        return;
      }

      await Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => HomeScreen(
            apiClient: widget.apiClient,
            session: session,
          ),
        ),
      );
    } catch (error) {
      setState(() {
        _errorMessage = error.toString().replaceFirst('Exception: ', '');
      });
    } finally {
      if (mounted) {
        setState(() {
          _isSubmitting = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      body: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              Color(0xFFF8FBF9),
              Color(0xFFEAF4EE),
              Color(0xFFF4F7FF),
            ],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 460),
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Form(
                      key: _formKey,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Application mobile',
                            style: theme.textTheme.bodyMedium,
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Connexion securisee',
                            style: theme.textTheme.headlineMedium,
                          ),
                          const SizedBox(height: 10),
                          Text(
                            'Connecte-toi au portail mobile CVB avec le profil adapte a ton espace.',
                            style: theme.textTheme.bodyMedium,
                          ),
                          const SizedBox(height: 24),
                          DropdownButtonFormField<String>(
                            value: _selectedRole,
                            items: _roleOptions,
                            decoration: const InputDecoration(
                              labelText: 'Profil',
                            ),
                            onChanged: _isSubmitting
                                ? null
                                : (value) {
                                    if (value == null) {
                                      return;
                                    }
                                    setState(() {
                                      _selectedRole = value;
                                    });
                                  },
                          ),
                          const SizedBox(height: 16),
                          TextFormField(
                            controller: _usernameController,
                            enabled: !_isSubmitting,
                            decoration: const InputDecoration(
                              labelText: 'Nom d utilisateur',
                            ),
                            validator: (value) {
                              if (value == null || value.trim().isEmpty) {
                                return 'Ce champ est obligatoire.';
                              }
                              return null;
                            },
                          ),
                          const SizedBox(height: 16),
                          TextFormField(
                            controller: _passwordController,
                            enabled: !_isSubmitting,
                            obscureText: true,
                            decoration: const InputDecoration(
                              labelText: 'Mot de passe',
                            ),
                            validator: (value) {
                              if (value == null || value.isEmpty) {
                                return 'Ce champ est obligatoire.';
                              }
                              return null;
                            },
                          ),
                          if (_errorMessage != null) ...[
                            const SizedBox(height: 16),
                            Container(
                              width: double.infinity,
                              padding: const EdgeInsets.all(14),
                              decoration: BoxDecoration(
                                color: const Color(0xFFFFF2F2),
                                borderRadius: BorderRadius.circular(16),
                                border: Border.all(
                                  color: const Color(0xFFFFD5D5),
                                ),
                              ),
                              child: Text(
                                _errorMessage!,
                                style: const TextStyle(
                                  color: Color(0xFF8A2E2E),
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),
                          ],
                          const SizedBox(height: 22),
                          ElevatedButton(
                            onPressed: _isSubmitting ? null : _submit,
                            child: _isSubmitting
                                ? const SizedBox(
                                    height: 20,
                                    width: 20,
                                    child: CircularProgressIndicator(strokeWidth: 2.2),
                                  )
                                : const Text('Se connecter'),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
