import 'package:flutter/material.dart';

import '../../auth/data/mobile_api_client.dart';
import '../../auth/presentation/login_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({
    super.key,
    required this.apiClient,
    required this.session,
  });

  final MobileApiClient apiClient;
  final MobileSession session;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  DashboardSnapshot? _dashboard;
  bool _isLoading = true;
  bool _isLoggingOut = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadDashboard();
  }

  Future<void> _loadDashboard() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final snapshot = await widget.apiClient.fetchDashboard(
        token: widget.session.token,
        portal: widget.session.portalRole,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _dashboard = snapshot;
      });
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _errorMessage = error.toString().replaceFirst('Exception: ', '');
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _logout() async {
    setState(() {
      _isLoggingOut = true;
    });

    try {
      await widget.apiClient.logout(token: widget.session.token);
    } catch (_) {
      // En mobile, on laisse sortir l'utilisateur meme si le backend a deja expire le jeton.
    }

    if (!mounted) {
      return;
    }

    await Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(
        builder: (_) => LoginScreen(apiClient: widget.apiClient),
      ),
      (route) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final summary = _dashboard?.summary ?? <String, dynamic>{};
    final recentRequests = _dashboard?.recentRequests ?? const <Map<String, dynamic>>[];

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.session.siteName),
        actions: [
          IconButton(
            onPressed: _isLoggingOut ? null : _logout,
            icon: _isLoggingOut
                ? const SizedBox(
                    height: 18,
                    width: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.logout),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _loadDashboard,
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Bonjour ${widget.session.displayName}',
                      style: theme.textTheme.headlineMedium,
                    ),
                    const SizedBox(height: 10),
                    Text(
                      'Portail actif : ${widget.session.portalRole == 'admin' ? 'Administration' : 'Employe'}',
                      style: theme.textTheme.bodyMedium,
                    ),
                    const SizedBox(height: 6),
                    Text(
                      (widget.session.branding['subtitle'] as String?) ?? '',
                      style: theme.textTheme.bodyMedium,
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            if (_errorMessage != null)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(18),
                  child: Text(
                    _errorMessage!,
                    style: const TextStyle(
                      color: Color(0xFF8A2E2E),
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ),
            if (_isLoading)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 32),
                child: Center(child: CircularProgressIndicator()),
              )
            else ...[
              Wrap(
                spacing: 12,
                runSpacing: 12,
                children: summary.entries
                    .map(
                      (entry) => _SummaryCard(
                        label: _formatLabel(entry.key),
                        value: '${entry.value}',
                      ),
                    )
                    .toList(),
              ),
              const SizedBox(height: 18),
              Text(
                'Demandes recentes',
                style: theme.textTheme.titleLarge,
              ),
              const SizedBox(height: 12),
              if (recentRequests.isEmpty)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(18),
                    child: Text(
                      'Aucune demande recente a afficher pour le moment.',
                      style: theme.textTheme.bodyMedium,
                    ),
                  ),
                )
              else
                ...recentRequests.map(
                  (item) => Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Card(
                      child: ListTile(
                        title: Text(item['request_type_label'] as String? ?? '-'),
                        subtitle: Text(item['period_label'] as String? ?? '-'),
                        trailing: Text(item['simple_status_label'] as String? ?? '-'),
                      ),
                    ),
                  ),
                ),
            ],
          ],
        ),
      ),
    );
  }

  String _formatLabel(String value) {
    return value
        .split('_')
        .map((part) => part.isEmpty ? part : '${part[0].toUpperCase()}${part.substring(1)}')
        .join(' ');
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 160,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                value,
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              Text(label),
            ],
          ),
        ),
      ),
    );
  }
}
