# Modèle de données Firebase (prévu)

Le guide utilise des fichiers locaux `data/` comme source de vérité MVP.
La persistance cloud prévue est **Firebase (Firestore)** pour :

- sites / monuments touristiques
- documents de knowledge base
- (plus tard) historiques de conversation et profils voyageurs

## Collections Firestore

### `tourist_sites`

Document ID = `id` du site (ex. `yaounde-monument-reunification`).

| Champ | Type | Notes |
| --- | --- | --- |
| id | string | Identifiant stable |
| name | string | Nom affiché |
| city | string | Ville |
| region | string | Région |
| category | string | monument, museum, park, beach… |
| summary_fr | string | Résumé FR |
| summary_en | string | Résumé EN |
| tips_fr | string | Conseils FR |
| tips_en | string | Tips EN |
| tags | array of string | Recherche / filtres |
| source | string | `local-seed` ou éditeur |
| updated_at | timestamp | Dernière mise à jour |

### `knowledge_documents`

Document ID = slug du fichier Markdown (ex. `monuments_heritage_guide`).

| Champ | Type | Notes |
| --- | --- | --- |
| id | string | Slug |
| title | string | Titre |
| body | string | Contenu Markdown |
| tags | array of string | |
| updated_at | timestamp | |

## Activation

```env
FIREBASE_ENABLED=true
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_CREDENTIALS_FILE=/path/to/serviceAccount.json
```

Sans credentials, l'API continue de lire uniquement `data/` en local.
