# Application mobile

Ce dossier contient le socle Flutter de l'application mobile pour le projet `Gestion-Personnel-DU-CVB`.

## Etat actuel

- structure Flutter initiale creee manuellement
- ecran de connexion
- client HTTP vers l'API Django mobile
- tableau de bord de base apres connexion

## API backend attendue

Base URL par defaut :

`http://10.0.2.2:8000/api/mobile`

Endpoints deja poses cote Django :

- `POST /api/mobile/auth/login/`
- `POST /api/mobile/auth/logout/`
- `GET /api/mobile/bootstrap/`
- `GET /api/mobile/me/`
- `GET /api/mobile/dashboard/`
- `GET /api/mobile/requests/`

## Demarrage conseille

1. Installer Flutter sur la machine.
2. Depuis `mobile_app`, executer `flutter pub get`.
3. Lancer le backend Django sur le port `8000`.
4. Demarrer l'application avec une surcharge d'URL si necessaire :

```bash
flutter run --dart-define=API_BASE_URL=http://192.168.1.10:8000/api/mobile
```

## Suite recommandee

- persistance locale du token
- gestion complete des demandes
- historique de validation
- notifications push
- mode hors ligne partiel
