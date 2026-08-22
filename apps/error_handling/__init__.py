"""
Gestion professionnelle des erreurs de l'application.

Architecture :
- middleware pour capturer les exceptions globales
- identifiant d'erreur unique
- journalisation structurée (log)
- rendu de pages HTML propres
- notifications IT en option (erreurs critiques uniquement)
"""