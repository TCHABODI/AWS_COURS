# Documentation - Pipeline d'Ingestion de Donnees IoT en Temps Reel (Serverless)

**Cours :** Cloud Computing et Big Data - Master 1  
**Auteur :** stchabodi  
**Date :** Juin 2026  

---

## Structure des fichiers soumis

```
devoir_final/
├── infrastructure/`r`n│   └── template.yaml  <- Infrastructure CloudFormation (12 ressources AWS)
├── src/
│   └── index.py           <- Fonction Lambda Python 3.11 (ingestion IoT)
├── test_client.py         <- Script de test client (3 scenarios)
├── index.html             <- Page de documentation statique (S3 + CloudFront OAC)
└── DOCUMENTATION.md       <- Ce fichier (demarche + reponses theoriques)
```

---

## Architecture globale

```
Sous-systeme 1 - Pipeline d'ingestion IoT
-------------------------------------------------
[Capteur IoT]
     | HTTP POST JSON
     v
[CloudFront no.1]  ->  CDN mondial, point d'entree IoT
     | HTTPS
     v
[API Gateway]  /ingest (POST)
     | Proxy Lambda
     v
[Lambda Python 3.11]
     |-- PUT JSON -->  [S3 Data Lake]   raw-zone/year/month/
     `-- PUT Item -->  [DynamoDB]       Feature Store

Sous-systeme 2 - Documentation technique (acces securise)
-------------------------------------------------
[Navigateur / Data Scientist]
     | HTTPS
     v
[CloudFront no.2 + OAC]  -- SigV4 -->  [S3 Doc Bucket (prive)]
                                          index.html
```

---

## Etape 1 - Prerequis

### Outils necessaires
- AWS CLI installe et configure (`aws configure`)
- Compte AWS avec droits sur CloudFormation, IAM, Lambda, S3, DynamoDB, API Gateway, CloudFront
- Python 3.11 en local (pour `test_client.py`)
- Bibliotheque Python `requests` : `pip install requests`

### Verification de la configuration AWS CLI
```bash
aws sts get-caller-identity
```

---

## Etape 2 - Deploiement CloudFormation

### Via la Console AWS

1. Connectez-vous à la **Console AWS** -> service **CloudFormation**
2. Cliquez sur "Creer une pile" -> "Avec de nouvelles ressources"
3. Sélectionnez "Charger un fichier de modele" -> chargez `template.yaml`
4. Nommez la pile : `tp-final-iot-pipeline`
5. Renseignez le paramètre `Environment` avec votre identifiant (ex: `stchabodi`)
6. Acceptez la création des ressources IAM -> cochez "Je comprends qu'AWS CloudFormation peut creer des ressources IAM"
7. Cliquez sur "Creer la pile"

### Via la CLI AWS (alternative)
```bash
aws cloudformation deploy \
  --stack-name tp-final-iot-pipeline \
  --template-file infrastructure/template.yaml \
  --parameter-overrides Environment=stchabodi \
  --capabilities CAPABILITY_IAM \
  --region eu-west-3
```

### Vérification du statut
Attendez que le statut passe à CREATE_COMPLETE.

```bash
aws cloudformation describe-stacks \
  --stack-name tp-final-iot-pipeline \
  --query 'Stacks[0].StackStatus'
```

### Récupération des Outputs (URLs CloudFront)
```bash
aws cloudformation describe-stacks \
  --stack-name tp-final-iot-pipeline \
  --query 'Stacks[0].Outputs' \
  --output table
```

> Capture requise : Interface CloudFormation affichant `CREATE_COMPLETE` + onglet Outputs avec les 2 URLs CloudFront.

Les deux URLs importantes sont :
- `CloudFrontIngestionURL` -> `https://XXXXX.cloudfront.net/ingest`
- `CloudFrontDocURL` -> `https://YYYYY.cloudfront.net`

---

## Etape 3 - Code de la fonction Lambda

### Code inline vs fichier séparé

Le fichier `template.yaml` contient déjà le code Lambda en **inline** (propriété `ZipFile`). 
Ce code est fonctionnel pour le déploiement CloudFormation.

Le fichier `src/index.py` contient la **version complète documentée** du même algorithme, 
idéale pour la lecture et la maintenance.

### Algorithme de traitement (résumé)

```python
# 1. Parse du payload JSON entrant
body = json.loads(event.get('body') or '{}')
records = body.get('records', [])

# 2. Clé S3 avec partitionnement temporel Hive-compatible
s3_key = f"raw-zone/year={now.year}/month={now.month:02d}/{request_id}.json"

# 3. Sauvegarde brute dans S3 (Data Lake)
s3_client.put_object(Bucket=bucket_name, Key=s3_key, Body=json.dumps(body))

# 4. Calcul des métriques
avg_temperature = round(sum(temperatures) / len(temperatures), 2)
error_count = sum(1 for r in records if r.get('status') == 'ERROR')

# 5. Enregistrement dans DynamoDB (Feature Store)
table.put_item(Item={
    'request_id': request_id,
    'timestamp': now.isoformat() + 'Z',
    's3_path': f"s3://{bucket_name}/{s3_key}",
    'avg_temperature': Decimal(str(avg_temperature)),
    'error_count': error_count,
    'record_count': len(records)
})
```

> Note technique : boto3 refuse les types `float` natifs pour DynamoDB. On utilise `Decimal(str(valeur))` obligatoirement.

---

## Etape 4 - Test avec test_client.py

### Configuration du script
Ouvrez `test_client.py` et remplacez la variable :
```python
CLOUDFRONT_INGESTION_URL = "https://XXXXXXXXXXXXXXXXXX.cloudfront.net/ingest"
# -> Remplacez par la valeur du Output CloudFrontIngestionURL
```

### Installation de la dépendance
```bash
pip install requests
```

### Exécution
```bash
python test_client.py
```

### Sortie attendue (Test 1 - payload valide)
```
================================================================
  TEST 1 : Payload valide (HTTP 201 attendu)
================================================================
  Statut HTTP recu : 201
  Succes - donnees ingerees correctement.
     request_id      : abc-123-def-456
     s3_path         : raw-zone/year=2026/month=06/abc-123.json
     avg_temperature : 81.4 C
     error_count     : 2
     record_count    : 4
```

> Calcul verifie : (72.5 + 89.3 + 68.1 + 95.7) / 4 = 81.4 C  |  Anomalies : 2 ERROR

---

## Etape 5 - Verification S3 (Data Lake)

```bash
# Lister les fichiers partitionnes dans le bucket
aws s3 ls s3://stchabodi-iot-datalake/raw-zone/ --recursive

# Afficher le contenu d'un fichier JSON ingere
aws s3 cp s3://stchabodi-iot-datalake/raw-zone/year=2026/month=06/<request_id>.json -
```

> Capture requise : Console S3 montrant l'arborescence `raw-zone/year=2026/month=06/`.

---

## Etape 6 - Verification DynamoDB (Feature Store)

```bash
# Scanner la table pour voir toutes les entrees
aws dynamodb scan \
  --table-name stchabodi-iot-feature-store \
  --output json
```

> Capture requise : Console DynamoDB montrant la table avec les lignes insérées (request_id, timestamp, avg_temperature, error_count).

---

## Etape 7 - Deploiement de la documentation technique

### Upload du fichier HTML dans le bucket S3 privé
```bash
aws s3 cp index.html s3://stchabodi-tech-doc/index.html \
  --content-type "text/html; charset=utf-8"
```

### Vérification de la présence du fichier
```bash
aws s3 ls s3://stchabodi-tech-doc/
```

### Test du blocage de l'accès direct S3
Tentez d'accéder via l'URL S3 directe :
```
https://stchabodi-tech-doc.s3.eu-west-3.amazonaws.com/index.html
```
Resultat attendu : HTTP 403 Access Denied - l'acces public est bloque.

### Accès via CloudFront OAC (sécurisé)
Ouvrez l'URL du Output `CloudFrontDocURL` dans votre navigateur :
```
https://YYYYY.cloudfront.net
```
Resultat attendu : La page HTML de documentation s'affiche correctement.

> Captures requises :
> - Erreur 403 via l'URL S3 directe
> - Page HTML affichée correctement via CloudFront

---

## Etape 8 - Monitoring avec Amazon CloudWatch

### Localiser les logs Lambda
1. Console AWS -> **CloudWatch** -> **Groupes de journaux**
2. Cherchez : /aws/lambda/stchabodi-iot-ingestion

### Identifier une exécution réussie
Cherchez dans les logs la séquence :
```
[START] Execution Lambda - request_id=...
[PARSE] 4 enregistrement(s) recu(s)
[S3] Fichier sauvegarde : s3://...
[DYNAMODB] Rapport enregistre : request_id=...
[END] Succes - HTTP 201
```

### Identifier une exécution en échec (Test 3 du client)
Exécutez `test_client.py` (Test 3 - JSON mal formé). Dans CloudWatch, vous verrez :
```
[ERROR-JSON] Payload JSON invalide : Expecting value: line 1 column 42
Traceback (most recent call last):
  File "/var/task/index.py", line XX, in lambda_handler
    body = json.loads(raw_body)
json.decoder.JSONDecodeError: Expecting value: line 1 column 42
```

> Captures requises :
> - Log d'une exécution en **Succes** (séquence START->S3->DYNAMODB->END)
> - Log d'une exécution en **échec** (Stack Trace Python complet)

---

## Ressources CloudFormation creees

| # | Ressource | Type AWS | Rôle |
|---|-----------|----------|------|
| 1 | `S3BucketRaw` | `AWS::S3::Bucket` | Data Lake - stockage JSON brut |
| 2 | `S3BucketDoc` | `AWS::S3::Bucket` | Documentation (privé, BlockPublicAccess) |
| 3 | `DynamoDBTable` | `AWS::DynamoDB::Table` | Feature Store métriques agrégées |
| 4 | `LambdaExecutionRole` | `AWS::IAM::Role` | Permissions Lambda (S3 + DynamoDB) |
| 5 | `LambdaFunction` | `AWS::Lambda::Function` | Traitement IoT Python 3.11 |
| 6 | `RestApi` | `AWS::ApiGateway::RestApi` | Point d'entrée HTTP REST |
| 7 | `IngestResource` + `IngestMethodPOST` | `AWS::ApiGateway::*` | Route POST /ingest |
| 8 | `ApiDeployment` | `AWS::ApiGateway::Deployment` | Déploiement stage `prod` |
| 9 | `CloudFrontIngestion` | `AWS::CloudFront::Distribution` | CDN devant API Gateway |
| 10 | `CloudFrontOAC` | `AWS::CloudFront::OriginAccessControl` | Contrôle d'accès OAC SigV4 |
| 11 | `CloudFrontDoc` | `AWS::CloudFront::Distribution` | CDN documentation avec OAC |
| 12 | `DocBucketPolicy` | `AWS::S3::BucketPolicy` | Autorise uniquement CloudFront OAC |

---

## Reponses aux questions theoriques

---

### Question 1 - Infrastructure as Code (IaC) et AWS CloudFormation

**L'Infrastructure as Code (IaC)** est une approche qui consiste à décrire et gérer l'infrastructure informatique (serveurs, réseaux, bases de données, etc.) à l'aide de fichiers de configuration textuels versionnés, au lieu de la configurer manuellement via des interfaces graphiques ou des commandes ad-hoc.

`**Avantages :**
`- **Reproductibilité** : le même template déploie des environnements identiques (dev, staging, prod)
- **Versionnement** : l'infrastructure est trackée dans Git comme le code applicatif
- **Automatisation** : les déploiements sont scriptés et intégrables dans un pipeline CI/CD
- **Auditabilité** : chaque modification de l'infrastructure est documentée

**AWS CloudFormation** est le service IaC natif d'AWS. Il permet de décrire l'ensemble d'une infrastructure dans un fichier YAML ou JSON (appelé *template*). CloudFormation gère ensuite le cycle de vie complet :
- **Création** : déploiement ordonné des ressources avec gestion des dépendances
- **Mise à jour** : calcul automatique du *change set* (différence entre l'état actuel et souhaité)
- **Suppression** : rollback automatique en cas d'erreur, suppression propre des ressources via les piles (*stacks*)

Dans ce projet, notre `template.yaml` définit 12 ressources AWS interconnectées déployées de manière atomique.

---

### Question 2 - AWS Lambda et l'approche Serverless vs EC2

**AWS Lambda** est un service de calcul serverless qui exécute du code en réponse à des événements (requête HTTP, upload S3, message SQS, etc.) sans nécessiter de provisionnement ni de gestion de serveur.

| Critère | AWS Lambda (Serverless) | Amazon EC2 (Instance virtuelle) |
|---------|------------------------|--------------------------------|
| **Provisionnement** | Aucun - AWS gère l'infrastructure | Manuel : choix du type d'instance, AMI, etc. |
| **Facturation** | À la milliseconde d'exécution | À l'heure, même si l'instance est idle |
| **Scalabilité** | Automatique et instantanée (jusqu'à 1000 concurrences) | Manuelle (Auto Scaling Groups) |
| **Maintenance** | Zéro - patches OS assurés par AWS | À la charge de l'équipe (OS, sécurité) |
| **Limites** | 15 min max, 10 Go RAM, code stateless | Aucune limite de temps, stateful possible |
| **Idéal pour** | Événements, microservices, traitements courts | Applications longues durées, bases de données |

**Avantage clé pour l'IoT :** Lambda scale à zéro quand aucune donnée n'arrive, ce qui évite de payer des ressources inutilisées - parfait pour des flux de capteurs intermittents.

---

### Question 3 - CloudFront devant API Gateway pour l'IoT

Adosser **Amazon CloudFront** devant **API Gateway** apporte plusieurs bénéfices architecturaux critiques pour une collecte IoT mondiale :

1. **Réduction de la latence (CDN)** : CloudFront possède 400+ Points of Presence (PoP) dans le monde. Les capteurs IoT se connectent au PoP géographiquement le plus proche, réduisant la latence de plusieurs dizaines à centaines de ms.

2. **Protection contre les attaques (DDoS, WAF)** : CloudFront peut être associé à **AWS Shield** et **AWS WAF** pour filtrer le trafic malveillant avant qu'il n'atteigne l'API Gateway.

3. **Réduction des coûts API Gateway** : En activant le cache CloudFront sur les routes GET, le nombre d'invocations API Gateway (et donc Lambda) diminue significativement.

4. **SSL/TLS terminaison globale** : CloudFront gère les certificats SSL et force le HTTPS, allégeant la charge de l'API.

5. **URL stable** : Le domaine CloudFront (`xxx.cloudfront.net`) reste stable même si l'endpoint API Gateway est modifié ou régénéré.

---

### Question 4 - S3 (Data Lake) + DynamoDB (Serving Layer) vs SGBDR unique

Dans un écosystème Big Data, la **séparation des couches** répond à des besoins très distincts :

**Amazon S3 - Data Lake (couche brute) :**
- Stockage illimité et peu coûteux (quelques centimes par Go/mois)
- Idéal pour les données **semi-structurées et non-structurées** (JSON, CSV, Parquet)
- Supporte des requêtes ad-hoc via **AWS Athena** (SQL sans serveur) ou **Apache Spark** (EMR)
- Immuabilité des données brutes - le "gold standard" pour la reproductibilité scientifique
- Pas adapté aux lectures à faible latence sur des clés précises

**Amazon DynamoDB - Serving Layer (Feature Store) :**
- Latence **< 10 ms** sur des lectures par clé primaire - adapté aux API temps réel
- Scalabilité horizontale automatique (milliards de requêtes/seconde)
- Modèle NoSQL - parfait pour des agrégats simples (métriques par request_id)
- Pas adapté aux requêtes analytiques complexes (JOIN, GROUP BY massif)

**Pourquoi pas une SGBDR unique ?**
- Une base relationnelle (PostgreSQL, MySQL) serait saturée par l'ingestion massive IoT
- Elle ne scale pas horizontalement sans ingénierie complexe (sharding)
- Le coût de stockage de TBs de données brutes y serait prohibitif
- Lambda Architecture et Data Lakehouse recommandent cette séparation des responsabilités

---

### Question 5 - Modèle de Responsabilité Partagée AWS (S3)

Le **modèle de responsabilité partagée** définit la frontière entre ce qu'AWS sécurise et ce que le client doit sécuriser.

**AWS est responsable de ("Security OF the Cloud") :**
- La sécurité physique des datacenters
- L'infrastructure réseau (routeurs, câbles, etc.)
- Le logiciel de virtualisation et le service S3 lui-même
- La disponibilité du service (SLA 99.99%)
- Le chiffrement de fond (au repos) de l'infrastructure matérielle

**Le client (vous) est responsable de ("Security IN the Cloud") :**
- La **configuration des politiques d'accès** (Bucket Policy, ACL, IAM)
- L'activation du **chiffrement des objets** (SSE-S3, SSE-KMS, SSE-C)
- La gestion des **clés IAM** et des permissions accordées aux utilisateurs/rôles
- L'activation du **versioning** et des **logs d'accès S3**
- La désactivation du **Block Public Access** (si accidentellement activé)
- La classification et la protection des **données sensibles** (PII, données médicales)

Dans notre projet : AWS s'assure que S3 fonctionne ; c'est nous qui configurons `BlockPublicAccess: true` et la `BucketPolicy` pour restreindre l'accès au seul CloudFront OAC.

---

### Question 6 - Risques du "Static Website Hosting" public vs CloudFront OAC

**Pourquoi éviter le Static Website Hosting public pour une documentation interne ?**

1. **Exposition directe des données** : Une URL S3 publique (`s3-website.amazonaws.com`) est accessible par n'importe qui sur Internet sans authentification.
2. **Pas de contrôle d'accès granulaire** : Impossible de restreindre l'accès par IP, région géographique ou identité.
3. **Pas de HTTPS natif** : L'hébergement statique S3 utilise HTTP par défaut - données en clair en transit.
4. **Pas de protection DDoS** : Le bucket est directement exposé aux attaques par déni de service.
5. **Surface d'attaque accrue** : Des bots peuvent scanner et indexer des documents sensibles.

**Comment CloudFront + OAC améliore la sécurité ?**

- **Bucket S3 entièrement privé** : `BlockPublicAccess = true` - aucun accès direct possible (HTTP 403).
- **OAC (Origin Access Control)** : CloudFront signe ses requêtes vers S3 avec **AWS Signature V4 (SigV4)**. La Bucket Policy n'autorise que les requêtes portant l'ARN exact de la distribution CloudFront.
- **HTTPS obligatoire** : `ViewerProtocolPolicy: redirect-to-https` - toutes les connexions sont chiffrées TLS.
- **Géo-restriction possible** : CloudFront peut bloquer l'accès depuis certains pays.
- **WAF intégrable** : AWS WAF peut filtrer les requêtes malveillantes avant qu'elles atteignent S3.

---

### Question 7 - Amazon CloudWatch et le débogage Serverless

**Amazon CloudWatch** est le service de monitoring et d'observabilité d'AWS, particulièrement essentiel pour les architectures serverless où on n'a pas accès aux serveurs physiques.

**Pour une Lambda, CloudWatch fournit :**

1. **Logs automatiques** : Chaque `print()` ou `logging.info()` dans le code est automatiquement envoyé dans un groupe de logs `/aws/lambda/{function-name}`.

2. **Métriques natives** :
   - `Invocations` : nombre total d'appels
   - `Duration` : temps d'exécution en ms
   - `Errors` : nombre d'exécutions ayant échoué
   - `Throttles` : limitations de concurrence atteintes

3. **Alertes CloudWatch Alarms** : Déclenchement automatique d'une notification SNS si le taux d'erreurs dépasse un seuil.

**Que se passe-t-il si la Lambda lève une exception non gérée ?**

Quand notre Lambda `raise` une exception non interceptée (comme dans notre code pour les erreurs internes) :
- Lambda marque l'exécution comme **ERROR** et incrémente la métrique `Errors`
- CloudWatch capture le **stack trace Python complet** avec la ligne exacte de l'erreur
- Le groupe de logs contiendra : `[ERROR]`, le type d'exception, le message, et les frames de la call stack
- API Gateway reçoit une réponse HTTP **502 Bad Gateway** (la Lambda a planté)

Dans notre projet, nous utilisons `traceback.print_exc()` pour enrichir les logs même dans les erreurs gérées (HTTP 400, 422).

---

### Question 8 - Limites de Lambda avec un fichier de 50 Go et alternatives Big Data

**Pourquoi Lambda atteint ses limites avec 50 Go ?**

| Contrainte Lambda | Valeur limite | Problème avec 50 Go |
|-------------------|---------------|---------------------|
| **Durée max d'exécution** | 15 minutes | Impossible de lire/traiter 50 Go en 15 min |
| **Mémoire RAM max** | 10 Go | Chargement du fichier en mémoire impossible |
| **Taille du payload HTTP** | 6 Mo (API Gateway) | Le fichier ne peut pas être envoyé via POST |
| **Stockage /tmp** | 10 Go | Espace de travail temporaire insuffisant |

**Service recommandé pour 50 Go : AWS Glue ou Amazon EMR**

- **AWS Glue** : Service ETL serverless managé, basé sur **Apache Spark**. Idéal pour transformer des fichiers de données massifs stockés dans S3. Pas de limite de taille, facturation à la seconde de calcul.
  
- **Amazon EMR** : Cluster Apache Spark/Hadoop managé pour des traitements Big Data complexes, avec contrôle total sur les ressources.

- **Architecture recommandée** :
  ```
  [Fichier 50 Go dans S3]
       ↓ notification S3 Event
  [AWS Glue Job (Spark)]
       ├── Transformation / agrégation
       └── Écriture résultats -> S3 Parquet + DynamoDB
  ```

  Lambda reste pertinente pour des **micro-batches** (quelques Mo) ou des événements en temps réel, mais **AWS Glue** prend le relais pour le traitement de volumes massifs.

---

## Checklist de validation finale

- [ ] Pile CloudFormation créée avec statut `CREATE_COMPLETE`
- [ ] Les 2 URLs CloudFront récupérées dans les Outputs
- [ ] `test_client.py` configuré avec `CloudFrontIngestionURL`
- [ ] Test 1 (payload valide) -> HTTP 201 reçu 
- [ ] Fichier JSON visible dans S3 sous `raw-zone/year=.../month=.../`
- [ ] Entrée DynamoDB créée avec `avg_temperature` et `error_count`
- [ ] `index.html` uploadé dans le bucket `-tech-doc`
- [ ] Accès direct S3 -> HTTP 403 Access Denied 
- [ ] Accès via `CloudFrontDocURL` -> Page HTML affichée 
- [ ] CloudWatch Logs : exécution réussie visible
- [ ] CloudWatch Logs : stack trace Python visible pour payload corrompu

---

*Documentation générée dans le cadre du Devoir Final - Cloud Computing & Big Data, Master 1, Juin 2026*

