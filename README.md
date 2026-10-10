![Agentic Data Lab](assets/header.svg)

# Agentic Data Lab

**Python · MCP · SQLite · SQL · Analyse de données**

Prototype de serveur MCP destiné à fournir à un client agentique des outils d’analyse d’un CSV : chargement, inspection du schéma, requêtes SQL et statistiques descriptives.

[Outils](#outils-exposés) · [Parcours](#parcours-danalyse) · [État](#état-du-dépôt) · [Fichiers](#fichiers)

## Outils exposés

Les fonctions suivantes sont définies dans [server.py](server.py).

| Outil | Fonction |
| --- | --- |
| `load_csv` | Charger un CSV dans une table SQLite via un module auxiliaire |
| `describe_schema` | Décrire les tables et les types de colonnes |
| `list_tables` | Lister les tables et leurs nombres de lignes |
| `preview_table` | Afficher un extrait de table |
| `run_query` | Exécuter une requête SELECT avec filtrage de mots-clés |
| `get_statistics` | Calculer compte, minimum, maximum, moyenne et valeurs nulles |

Deux ressources complètent les outils : `db://schema` et `db://query-history`. Le prompt `expert-data-analysis` guide la préparation, l’analyse de revenu, la comparaison des volumes et la synthèse.

## Parcours d’analyse

Le fichier [sample_data.csv](sample_data.csv) contient quatre lignes de démonstration : nom, région, catégorie, prix et quantité.

1. Charger ce fichier sous le nom de table `sales`.
2. Inspecter le schéma puis les premières lignes.
3. Demander une agrégation par région.
4. Compléter l’analyse par les statistiques de quantité.
5. Citer les outils utilisés et consulter l’historique de session.

Exemple de requête destinée à `run_query` :

```sql
SELECT region, SUM(price * quantity) AS revenue
FROM sales
GROUP BY region
ORDER BY revenue DESC
```

Le code conserve la base et l’historique en mémoire pendant la session. Le serveur fournit des outils ; aucun modèle de langage ni client agentique n’est intégré au dépôt.

## État du dépôt

**Prototype incomplet : le lancement est actuellement bloqué.** `server.py` importe `create_db` et `load_csv_to_table` depuis `sqlite_helper.py`, qui n’est pas présent dans ce dépôt.

Avant une démonstration exécutable, il reste à fournir ce module, définir les dépendances, puis tester le chargement CSV et les outils. Aucun résultat d’exécution n’est revendiqué ici.

Le filtrage SQL par expression régulière constitue un contrôle pédagogique, pas une isolation de sécurité complète. Le code doit aussi renforcer la validation des identifiants SQL, les limites de résultats et les chemins de fichiers avant un usage avec des données externes.

## Fichiers

| Fichier | Rôle |
| --- | --- |
| [server.py](server.py) | Définition du serveur, outils, ressources et prompt |
| [sample_data.csv](sample_data.csv) | Petit jeu de données de démonstration |
| [projet.docx](projet.docx) | Document du projet |

---

[Profil de Malika Fofana](https://github.com/malikafofana) · [Telco Signal](https://github.com/malikafofana/telco-signal) · [Evidence Search](https://github.com/malikafofana/evidence-search) · [Alzheimer MRI Study](https://github.com/malikafofana/alzheimer-mri-study)
