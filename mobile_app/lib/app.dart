import 'package:flutter/material.dart';

import 'core/theme/app_theme.dart';
import 'features/auth/data/mobile_api_client.dart';
import 'features/auth/presentation/login_screen.dart';

class PersonnelMobileApp extends StatelessWidget {
  const PersonnelMobileApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Gestion du personnel',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      home: LoginScreen(apiClient: MobileApiClient()),
    );
  }
}
