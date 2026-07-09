import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/config/app_config.dart';

class MobileSession {
  const MobileSession({
    required this.token,
    required this.portalRole,
    required this.profile,
    required this.branding,
  });

  final String token;
  final String portalRole;
  final Map<String, dynamic> profile;
  final Map<String, dynamic> branding;

  String get displayName => (profile['display_name'] as String?) ?? 'Utilisateur';

  String get siteName => (branding['site_name'] as String?) ?? 'Gestion du personnel';
}

class DashboardSnapshot {
  const DashboardSnapshot({
    required this.portal,
    required this.summary,
    required this.recentRequests,
  });

  final String portal;
  final Map<String, dynamic> summary;
  final List<Map<String, dynamic>> recentRequests;
}

class MobileApiClient {
  Uri _uri(String path, [Map<String, String>? queryParameters]) {
    return Uri.parse('${AppConfig.apiBaseUrl}$path').replace(
      queryParameters: queryParameters,
    );
  }

  Future<MobileSession> login({
    required String username,
    required String password,
    required String role,
  }) async {
    final response = await http.post(
      _uri('/auth/login/'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(
        {
          'username': username,
          'password': password,
          'role': role,
        },
      ),
    );

    final payload = _decodeResponse(response);
    final bootstrap = Map<String, dynamic>.from(payload['bootstrap'] as Map);
    return MobileSession(
      token: payload['token'] as String,
      portalRole: payload['portal_role'] as String? ?? 'employee',
      profile: Map<String, dynamic>.from(bootstrap['profile'] as Map),
      branding: Map<String, dynamic>.from(bootstrap['branding'] as Map),
    );
  }

  Future<DashboardSnapshot> fetchDashboard({
    required String token,
    required String portal,
  }) async {
    final response = await http.get(
      _uri('/dashboard/', {'portal': portal}),
      headers: {'Authorization': 'Bearer $token'},
    );
    final payload = _decodeResponse(response);
    return DashboardSnapshot(
      portal: payload['portal'] as String? ?? portal,
      summary: Map<String, dynamic>.from((payload['summary'] as Map?) ?? {}),
      recentRequests: List<Map<String, dynamic>>.from(
        ((payload['recent_requests'] as List?) ?? []).map(
          (item) => Map<String, dynamic>.from(item as Map),
        ),
      ),
    );
  }

  Future<void> logout({required String token}) async {
    final response = await http.post(
      _uri('/auth/logout/'),
      headers: {'Authorization': 'Bearer $token'},
    );
    _decodeResponse(response);
  }

  Map<String, dynamic> _decodeResponse(http.Response response) {
    final Map<String, dynamic> payload = response.body.isEmpty
        ? <String, dynamic>{}
        : Map<String, dynamic>.from(jsonDecode(response.body) as Map);

    if (response.statusCode >= 400) {
      throw Exception(payload['message'] ?? 'Erreur reseau.');
    }
    if (payload['ok'] == false) {
      throw Exception(payload['message'] ?? 'Operation impossible.');
    }
    return payload;
  }
}
