# Pipeline d'Ingestion de Donnees IoT en Temps Reel - Serverless
**Cours :** Introduction a AWS - Master 1
**Responsable :** M. Herve LOKOSSOU
**Auteur :** stchabodi
**Date :** Juin 2026
---
## Introduction et contexte du projet
Ce projet a pour objectif de mettre en place une architecture cloud entierement serverless
capable d'ingerer en temps reel les donnees de capteurs IoT industriels. Concretement,
des milliers de capteurs envoient des mesures de temperature, pression et humidite via
des requetes HTTP POST. Notre infrastructure doit recevoir ces donnees, les stocker brutes
pour les Data Scientists, et produire des metriques agregees exploitables immediatement.
En parallele, une documentation technique du projet est hebergee de facon securisee
pour l'equipe interne, accessible uniquement via un CDN avec controle d'acces strict.
Toute cette infrastructure est decrite dans un seul fichier CloudFormation (Infrastructure
as Code), ce qui permet de la deployer, modifier ou supprimer en une seule commande.
---
## Architecture mise en place
Le projet se compose de deux sous-systemes independants.
**Sous-systeme 1 : Pipeline d'ingestion IoT**
Les capteurs envoient leurs donnees vers une URL CloudFront. CloudFront joue le role de
point d'entree mondial (CDN) et transmet les requetes a l'API Gateway, qui declenche la
fonction Lambda. La Lambda traite les donnees, les sauvegarde brutes dans S3 et enregistre
les metriques agregees dans DynamoDB.
```
[Capteur IoT]  --HTTP POST JSON-->  [CloudFront no.1]
                                           |
                                    [API Gateway]  /ingest
                                           |
                                    [Lambda Python 3.11]
                                      |           |
                               [S3 Data Lake]  [DynamoDB]
                               raw-zone/...    metriques
```
**Sous-systeme 2 : Documentation technique (acces securise)**
Le bucket S3 de documentation est entierement prive (aucun acces public). Seul le CDN
CloudFront est autorise a lire son contenu, grace au mecanisme OAC qui signe chaque
requete avec la signature AWS SigV4.
```
[Navigateur]  -->  [CloudFront no.2 + OAC]  -- SigV4 -->  [S3 Bucket prive]
                                                               index.html
```
---
## Structure du projet
```
devoir_final/
├── infrastructure/
│   └── template.yaml       <- Le coeur du projet : toute l'infra en un fichier YAML
├── src/
│   └── index.py            <- Code Python complet de la fonction Lambda
├── test_client.py          <- Script pour tester le pipeline de bout en bout
├── index.html              <- Page de documentation statique deployee sur S3
└── DOCUMENTATION.md        <- Ce document
```
---
## Ressources AWS creees par CloudFormation
| No. | Nom dans le template | Service AWS | Ce qu'elle fait |
|-----|----------------------|-------------|-----------------|
| 1 | S3BucketRaw | Amazon S3 | Stocke les fichiers JSON bruts des capteurs (Data Lake) |
| 2 | S3BucketDoc | Amazon S3 | Heberge la documentation HTML (bucket prive) |
| 3 | DynamoDBTable | Amazon DynamoDB | Enregistre les metriques agregees par requete |
| 4 | LambdaExecutionRole | AWS IAM | Donne a la Lambda le droit d'ecrire dans S3 et DynamoDB |
| 5 | LambdaFunction | AWS Lambda | Traite les donnees IoT (Python 3.11) |
| 6 | RestApi | Amazon API Gateway | Expose le endpoint HTTP POST /ingest |
| 7 | IngestResource + IngestMethodPOST | API Gateway | Definit la route POST /ingest |
| 8 | ApiDeployment | API Gateway | Publie l'API sur le stage "prod" |
| 9 | LambdaApiGatewayPermission | AWS Lambda | Autorise API Gateway a invoquer la Lambda |
| 10 | CloudFrontIngestion | Amazon CloudFront | CDN devant l'API Gateway (point d'entree IoT) |
| 11 | CloudFrontOAC | CloudFront OAC | Signe les requetes vers S3 avec SigV4 |
| 12 | CloudFrontDoc | Amazon CloudFront | CDN devant le bucket de documentation |
| 13 | DocBucketPolicy | S3 Bucket Policy | Autorise uniquement CloudFront a lire le bucket doc |
---
## Etape 1 - Preparation de l'environnement 
Avant de deployer quoi que ce soit, il faut s'assurer que les outils necessaires sont
en place sur votre machine.
### 1.1 Verifier que l'AWS CLI est installe
L'AWS CLI est l'outil en ligne de commande qui permet d'interagir avec AWS sans passer
par la console web. Il sera utilise pour verifier le deploiement et uploader des fichiers.
```bash
aws --version
```
Si la commande retourne quelque chose comme `aws-cli/2.x.x`, vous etes pret.
Dans le cas contraire, installez-le depuis :
https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html
### 1.2 Configurer vos identifiants AWS
Si ce n'est pas deja fait, configurez vos cles d'acces AWS. Ces cles se trouvent dans
la console AWS sous "Security credentials" ou dans le fichier CSV fourni par votre
compte learnaws.
```bash
aws configure
```
Renseignez les informations suivantes :
- AWS Access Key ID : votre cle d'acces
- AWS Secret Access Key : votre cle secrete
- Default region name : eu-west-3 (Paris, recommande pour ce TP)
- Default output format : json
### 1.3 Verifier que la connexion fonctionne
Cette commande retourne l'identite du compte AWS utilise. Si elle reussit sans erreur,
tout est correctement configure.
```bash
aws sts get-caller-identity
```
Exemple de reponse attendue :
```json
{
    "UserId": "AIDA...",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/stchabodi"
}
```
### 1.4 Installer la bibliotheque Python pour les tests
Le script de test utilise la bibliotheque `requests` pour faire des requetes HTTP.
```bash
pip install requests
```
---
## Etape 2 - Deploiement de l'infrastructure avec AWS SAM CLI

> **IMPORTANT** : Le template utilise `Transform: AWS::Serverless-2016-10-31` et une
> ressource `AWS::Serverless::Function` avec `CodeUri: ../src/`. Ce template **ne peut
> pas etre deploye directement** via la console AWS ni via `aws cloudformation deploy`
> sans passer par SAM CLI au prealable. SAM est necessaire pour packager le code Python
> et transformer le template avant envoi a CloudFormation.
>
> Si vous tentez de charger `infrastructure/template.yaml` directement dans la console
> AWS CloudFormation, vous obtiendrez l'erreur :
> `Template format error: Unrecognized resource types: [AWS::Serverless::Function]`

### 2.1 Verifier les pre-requis SAM et Docker

```bash
sam --version   # SAM CLI, version 1.x.x
docker --version  # Docker est requis pour sam build (ou utiliser --use-container=false)
```

Si SAM CLI n'est pas installe :
https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html

### 2.2 Valider le template

```bash
cd devoir_final
make validate
```
Equivalent direct :
```bash
sam validate --region eu-west-3 --template infrastructure/template.yaml --lint
```
Reponse attendue : `infrastructure/template.yaml is a valid SAM Template`

### 2.3 Construire le package Lambda

```bash
make build
```
Equivalent direct :
```bash
sam build --region eu-west-3 --template infrastructure/template.yaml
```
SAM lit `infrastructure/template.yaml`, localise le code via `CodeUri: ../src/`,
installe les dependances de `src/requirements.txt` (fastapi, mangum) et genere
l'artefact deployable dans `.aws-sam/build/`.

### 2.4 Premier deploiement (mode guide interactif)

```bash
make deploy
```
Equivalent direct :
```bash
sam deploy --guided \
  --region eu-west-3 \
  --stack-name tp-final-iot-pipeline-stchabodi \
  --template-file .aws-sam/build/template.yaml \
  --no-fail-on-empty-changeset \
  --parameter-overrides Environment=stchabodi \
  --capabilities CAPABILITY_IAM
```
Repondez aux questions posees par SAM (Stack Name, Region, Environment, confirmations).
L'option `--capabilities CAPABILITY_IAM` est obligatoire car le template cree un role IAM.

### 2.5 (Ancienne methode - NE PAS UTILISER) Deploiement direct CloudFormation

> Cette methode est **incompatible** avec ce projet et produira une erreur.
> Elle n'est fournie qu'a titre informatif pour comprendre la difference entre
> `aws cloudformation deploy` (CloudFormation pur) et `sam deploy` (SAM).

```bash
# NE PAS EXECUTER - echouera avec "Unrecognized resource types: [AWS::Serverless::Function]"
aws cloudformation deploy \
  --stack-name tp-final-iot-pipeline \
  --template-file infrastructure/template.yaml \
  --parameter-overrides Environment=stchabodi \
  --capabilities CAPABILITY_IAM \
  --region eu-west-3
```
### 2.6 Suivre la progression du deploiement
Le deploiement prend environ 3 a 5 minutes. CloudFormation cree les ressources dans
un ordre precis en respectant les dependances : le role IAM d'abord, puis la Lambda
(qui a besoin du role), puis l'API Gateway (qui a besoin de la Lambda), etc.
Dans la console, cliquez sur l'onglet "Evenements" de la pile pour suivre la creation
de chaque ressource en temps reel. Vous verrez les lignes s'ajouter au fur et a mesure.
Via la CLI, vous pouvez interroger le statut :
```bash
aws cloudformation describe-stacks \
  --stack-name tp-final-iot-pipeline \
  --query 'Stacks[0].StackStatus' \
  --region eu-west-3
```
Attendez que la reponse soit "CREATE_COMPLETE". Si vous voyez "ROLLBACK_COMPLETE",
une erreur s'est produite : consultez l'onglet "Evenements" pour voir quel message
d'erreur a ete retourne et quelle ressource a cause le probleme.
**Capture d'ecran requise ici :** L'interface CloudFormation affichant le statut
CREATE_COMPLETE avec la liste des ressources creees dans l'onglet "Ressources".
### 2.7 Recuperer les URLs generees dans les Outputs
Une fois la pile deployee, CloudFormation expose les URLs importantes dans l'onglet
"Sorties". Ces URLs sont generees dynamiquement et propres a votre deploiement.
Vous en avez besoin pour toutes les etapes suivantes.
Via la console : cliquez sur la pile, puis sur l'onglet "Sorties".
Via la CLI :
```bash
aws cloudformation describe-stacks \
  --stack-name tp-final-iot-pipeline \
  --query 'Stacks[0].Outputs' \
  --output table \
  --region eu-west-3
```
Notez imperativement ces deux valeurs :
- **CloudFrontIngestionURL** : l'URL pour envoyer les donnees IoT.
  Format : https://XXXXXXXXXXXXX.cloudfront.net/ingest
- **CloudFrontDocURL** : l'URL pour acceder a la documentation.
  Format : https://YYYYYYYYYYYYY.cloudfront.net
**Capture d'ecran requise ici :** L'onglet Outputs de la pile avec les deux URLs
CloudFront clairement visibles.
---
## Etape 3 - Comprendre le code de la fonction Lambda

Le fichier `src/index.py` contient le code complet de la fonction Lambda. L'architecture
choisie est **FastAPI + Mangum** (meme approche que le TP4). FastAPI gere le routage HTTP
et la validation des donnees via Pydantic. Mangum est l'adaptateur qui permet d'executer
une application ASGI/FastAPI dans le runtime AWS Lambda, en traduisant les evenements
API Gateway en requetes ASGI et inversement.

```
[API Gateway Event] --> [Mangum adapter] --> [FastAPI app] --> [index.py handlers]
```

Le `lambda_handler` pointe sur l'instance Mangum :
```python
lambda_handler = Mangum(app, lifespan="off")
```

### 3.1 Ce que fait la Lambda, etape par etape

Quand un capteur IoT envoie une requete HTTP POST, voici ce qui se passe :

**Etape A - Validation automatique du schema par Pydantic**

Pydantic valide automatiquement le corps de la requete contre les modeles declares.
Si un champ requis (`sensor_id`, `status`) est absent ou si le type est incorrect,
FastAPI retourne HTTP 422 (Unprocessable Entity) sans meme entrer dans la fonction handler.

```python
class SensorRecord(BaseModel):
    sensor_id: str        # requis
    temperature: Optional[float] = None
    status: str           # requis
    # ...

class IoTPayload(BaseModel):
    records: List[SensorRecord]  # liste requise
```

**Etape B - Verification de la liste records**

Si `records` est une liste vide, une `ValueError` est levee explicitement :
```python
if not records:
    raise ValueError("Le champ 'records' est vide - aucun enregistrement a ingerer")
```

**Etape C - Sauvegarde brute dans S3 avec partitionnement temporel**

Le payload est serialise en JSON et sauvegarde dans S3 avec un chemin structure :
```python
s3_key = f"raw-zone/year={now.year}/month={now.month:02d}/{request_id}.json"
s3_client.put_object(Bucket=bucket_name, Key=s3_key, Body=json.dumps(payload.dict(), ...))
```

Exemple de cle S3 generee : `raw-zone/year=2026/month=06/abc123-def456.json`

**Etape D - Calcul des metriques a la volee**

```python
temperatures = [r.temperature for r in records if r.temperature is not None]
avg_temperature = round(sum(temperatures) / len(temperatures), 2) if temperatures else 0.0
error_count = sum(1 for r in records if r.status == "ERROR")
```

Note : boto3 exige `Decimal(str(valeur))` pour stocker des nombres flottants dans DynamoDB.

**Etape E - Enregistrement dans DynamoDB**

```python
table.put_item(Item={
    'request_id':      request_id,
    'timestamp':       now.isoformat() + 'Z',
    's3_path':         f"s3://{bucket_name}/{s3_key}",
    'avg_temperature': Decimal(str(avg_temperature)),
    'error_count':     error_count,
    'record_count':    len(records)
})
```

**Etape F - Reponse HTTP 201**

FastAPI retourne HTTP 201 avec le resume de l'ingestion.

### 3.2 Gestion des erreurs

| Scenario | Declencheur | Comportement | Code HTTP |
|----------|-------------|--------------|-----------|
| Schema invalide (sensor_id absent) | Pydantic ValidationError | FastAPI retourne 422 automatiquement, Lambda ne crashe pas | 422 |
| records vide `[]` | ValueError explicite dans le handler | global_exception_handler logue + releve, Mangum retourne 500 | 500 |
| Erreur AWS (S3, DynamoDB) | Exception boto3 | global_exception_handler logue + releve, Mangum retourne 500 | 500 |

> **Note** : avec Mangum, meme si une exception est relevee (raise) dans un handler
> FastAPI, Mangum l'intercepte et retourne HTTP 500 proprement. La Lambda elle-meme
> ne "crashe" pas au sens strict (la fonction retourne une reponse valide a AWS),
> mais l'erreur est bien loguee dans CloudWatch.
---
## Etape 4 - Execution des tests avec test_client.py
### 4.1 Configurer l'URL dans le script
Ouvrez `test_client.py` dans votre editeur et remplacez la variable
`CLOUDFRONT_INGESTION_URL` par l'URL recuperee dans les Outputs CloudFormation.
Avant modification :
```python
CLOUDFRONT_INGESTION_URL = "https://XXXXXXXXXXXXXXXXXX.cloudfront.net/ingest"
```
Apres modification (exemple) :
```python
CLOUDFRONT_INGESTION_URL = "https://d1abc2defghijk.cloudfront.net/ingest"
```
### 4.2 Lancer les tests
Depuis le dossier `devoir_final`, executez :
```bash
python test_client.py
```
Le script execute automatiquement trois scenarios de test dans l'ordre.
### 4.3 Test 1 - Payload valide (HTTP 201 attendu)

Ce test envoie un batch de 4 mesures capteurs bien formees. Deux capteurs sont en
statut OK et deux en statut ERROR. Les temperatures sont 72.5, 89.3, 68.1 et 95.7 C.

Calcul attendu : (72.5 + 89.3 + 68.1 + 95.7) / 4 = 81.4 C  |  Anomalies : 2

Sortie attendue dans le terminal :
```
-----------------------------------------------------------------
  Test 1 : payload valide (HTTP 201 attendu)
-----------------------------------------------------------------
  Statut HTTP recu : 201
  Succes - donnees ingerees correctement.
    request_id      : 12345678-abcd-ef01-2345-6789abcdef01
    s3_path         : raw-zone/year=2026/month=06/12345678-abcd.json
    avg_temperature : 81.4 C
    error_count     : 2
    record_count    : 4
```

Si vous obtenez HTTP 201 avec ces valeurs, le pipeline fonctionne de bout en bout.

### 4.4 Test 2 - Records vide (provoque un HTTP 500 avec stack trace dans CloudWatch)

Ce test envoie un payload avec `records: []` (liste vide). La fonction `ingest_iot_data`
detecte la liste vide et leve un `ValueError`. Le gestionnaire global FastAPI logue le
stack trace complet et releve l'exception, ce qui amene Mangum a retourner HTTP 500.

> **Note** : avec FastAPI + Mangum, la fonction Lambda elle-meme retourne une reponse
> valide (HTTP 500 structure) plutot que de crasher. La metrique Lambda "Errors" n'est
> pas incrementee, mais le stack trace Python est bien visible dans CloudWatch Logs
> sous `/aws/lambda/stchabodi-iot-ingestion`.

Sortie attendue dans le terminal :
```
-----------------------------------------------------------------
  Test 2 : records vide -> ValueError Lambda -> stack trace CloudWatch
-----------------------------------------------------------------
  Statut HTTP recu : 500
  -> Verifier /aws/lambda/stchabodi-iot-ingestion dans CloudWatch
     pour voir le stack trace Python complet de ce ValueError.
```

### 4.5 Test 3 - Schema invalide : sensor_id manquant (HTTP 422 attendu)

Ce test envoie un enregistrement sans le champ `sensor_id` qui est requis dans le modele
Pydantic `SensorRecord`. FastAPI detecte automatiquement la violation de schema et retourne
HTTP 422 (Unprocessable Entity) avec le detail de l'erreur de validation. La Lambda ne
realise aucun traitement metier.

Sortie attendue :
```
-----------------------------------------------------------------
  Test 3 : schema invalide (sensor_id manquant) -> HTTP 422 Pydantic
-----------------------------------------------------------------
  Statut HTTP recu : 422
  Reponse : {"detail": [{"loc": ["body", "records", 0, "sensor_id"],
             "msg": "field required", "type": "value_error.missing"}]}
```
---
## Etape 5 - Verification des donnees dans Amazon S3
Apres le Test 1, le fichier JSON brut doit etre present dans le bucket Data Lake.
Voici comment le verifier.
### 5.1 Lister les fichiers ingeres via la CLI
```bash
aws s3 ls s3://stchabodi-iot-datalake/raw-zone/ --recursive --region eu-west-3
```
Vous devriez voir une ligne comme :
```
2026-06-08 10:23:45    842 raw-zone/year=2026/month=06/12345678-abcd-ef01.json
```
Le chemin respecte le partitionnement temporel : `raw-zone/year=YYYY/month=MM/<id>.json`
### 5.2 Afficher le contenu d'un fichier ingere
Pour verifier que le fichier contient bien le payload original envoye par le Test 1 :
```bash
aws s3 cp s3://stchabodi-iot-datalake/raw-zone/year=2026/month=06/<request_id>.json - \
  --region eu-west-3
```
Remplacez `<request_id>` par la valeur retournee dans la reponse du Test 1.
### 5.3 Verification depuis la console AWS
Dans la console AWS, accedez au service S3, cliquez sur le bucket
`stchabodi-iot-datalake`, puis naviguez : `raw-zone/` -> `year=2026/` -> `month=06/`
**Capture d'ecran requise ici :** L'arborescence des fichiers dans S3 montrant le
chemin de partitionnement avec au moins un fichier JSON present.
---
## Etape 6 - Verification des metriques dans Amazon DynamoDB
### 6.1 Scanner la table via la CLI
```bash
aws dynamodb scan \
  --table-name stchabodi-iot-feature-store \
  --region eu-west-3 \
  --output json
```
Chaque element de la reponse correspond a une execution de la Lambda :
```json
{
  "request_id":      {"S": "12345678-abcd-ef01-2345-6789abcdef01"},
  "timestamp":       {"S": "2026-06-08T10:23:45.123456Z"},
  "s3_path":         {"S": "s3://stchabodi-iot-datalake/raw-zone/year=2026/month=06/...json"},
  "avg_temperature": {"N": "81.4"},
  "error_count":     {"N": "2"},
  "record_count":    {"N": "4"}
}
```
### 6.2 Verification depuis la console AWS
Dans la console AWS, accedez au service DynamoDB -> "Tables" -> selectionnez
`stchabodi-iot-feature-store` -> onglet "Explorez les elements de table".
Vous verrez les lignes inserees avec toutes les colonnes.
**Capture d'ecran requise ici :** La table DynamoDB avec au moins une ligne inseree,
montrant les colonnes avg_temperature (81.4) et error_count (2).
---
## Etape 7 - Deploiement de la documentation technique
### 7.1 Uploader le fichier HTML via la CLI
Depuis le dossier `devoir_final`, executez :
```bash
aws s3 cp index.html s3://stchabodi-tech-doc/index.html \
  --content-type "text/html; charset=utf-8" \
  --region eu-west-3
```
L'option `--content-type` est importante pour que le navigateur interprete le fichier
comme une page HTML et non comme du texte brut.
Si la commande reussit, vous obtenez :
```
upload: ./index.html to s3://stchabodi-tech-doc/index.html
```
### 7.2 Verifier la presence du fichier
```bash
aws s3 ls s3://stchabodi-tech-doc/ --region eu-west-3
```
Vous devriez voir `index.html` liste avec sa taille et la date d'upload.
### 7.3 Tester le blocage de l'acces direct S3
Ouvrez votre navigateur et tentez d'acceder directement au fichier via son URL S3 :
```
https://stchabodi-tech-doc.s3.eu-west-3.amazonaws.com/index.html
```
Vous devez obtenir une page d'erreur Access Denied (HTTP 403). C'est le comportement
attendu : le bucket a le Block Public Access active. Personne ne peut acceder
directement au bucket, meme en connaissant l'URL exacte d'un fichier.
**Capture d'ecran requise ici :** Le message Access Denied dans le navigateur.
### 7.4 Acceder via CloudFront OAC (acces securise)
Ouvrez l'URL `CloudFrontDocURL` recuperee dans les Outputs CloudFormation.
La page HTML de documentation s'affiche correctement. CloudFront intercepte la
requete, la signe avec SigV4 vers S3, et S3 l'accepte car la Bucket Policy autorise
specifiquement cette distribution CloudFront.
**Capture d'ecran requise ici :** La page de documentation affichee dans le navigateur
via l'URL CloudFront.
---
## Etape 8 - Monitoring et debogage avec Amazon CloudWatch
CloudWatch est l'outil de surveillance d'AWS. Pour une architecture serverless, c'est
la seule facon de voir ce qui se passe a l'interieur des fonctions Lambda. Chaque
instruction `print()` dans le code est enregistree automatiquement.
### 8.1 Acceder aux logs de la Lambda
Dans la console AWS :
1. Recherchez et ouvrez le service "CloudWatch"
2. Dans le menu de gauche : "Journaux" -> "Groupes de journaux"
3. Cherchez et cliquez sur : `/aws/lambda/stchabodi-iot-ingestion`
4. Vous voyez la liste des flux de journaux, un flux par invocation
5. Cliquez sur le flux le plus recent pour voir les logs
### 8.2 Log d'une execution reussie (Test 1)

Apres le Test 1, ouvrez le flux de log correspondant. Vous devez trouver cette sequence
qui prouve que chaque etape du pipeline s'est bien deroulee :
```
[START] request_id=12345678-abcd-ef01-2345-6789abcdef01 | 4 enregistrement(s)
[S3] Fichier sauvegarde : s3://stchabodi-iot-datalake/raw-zone/year=2026/month=06/...
[METRICS] avg_temperature=81.4C | error_count=2 | record_count=4
[DYNAMODB] Rapport enregistre : request_id=12345678-abcd-ef01-2345-6789abcdef01
[END] Succes - HTTP 201
```

**Capture d'ecran requise ici :** Le log d'une execution reussie montrant la sequence
complete de [START] a [END] avec le code HTTP 201.

### Log d'une execution en echec (Test 2 - ValueError sur records vide)

Le Test 2 a envoye `records: []`. L'endpoint FastAPI leve un `ValueError`. Retrouvez dans
CloudWatch le flux de log du Test 2. Vous devez voir le message d'erreur et le Traceback :
```
[ERROR-INTERNAL] ValueError: Le champ 'records' est vide - aucun enregistrement a ingerer
Traceback (most recent call last):
  File "/var/task/index.py", line XX, in ingest_iot_data
    raise ValueError("Le champ 'records' est vide - aucun enregistrement a ingerer")
ValueError: Le champ 'records' est vide - aucun enregistrement a ingerer
```
**Capture d'ecran requise ici :** Le log d'une execution en echec montrant le stack
trace Python complet du ValueError.
### Comprendre la difference entre les deux types d'erreurs

Il est utile de distinguer deux comportements dans notre code FastAPI.

**Erreur de validation schema (Test 3 - Pydantic ValidationError)** : FastAPI detecte
que le schema du payload n'est pas respecte (champ requis `sensor_id` absent) et
retourne automatiquement HTTP 422 sans entrer dans le handler. Le stack trace n'est
pas visible dans CloudWatch car l'exception est geree en interne par FastAPI.

**Erreur interne relevee (Test 2 - ValueError sur records vide)** : le handler leve
un `ValueError`, le `global_exception_handler` logue le stack trace complet dans
CloudWatch puis execute `raise`. Mangum intercepte l'exception et retourne HTTP 500.
La Lambda elle-meme ne "crashe" pas (elle retourne une reponse valide), mais l'erreur
est bien loguee et le stack trace Python est visible dans CloudWatch.

**Capture d'ecran requise ici :** Le log d'une execution en echec montrant le stack
trace Python complet du ValueError.
---
## Reponses aux questions theoriques
---
### Question 1 - Infrastructure as Code et AWS CloudFormation
L'Infrastructure as Code est une pratique qui consiste a decrire l'infrastructure
informatique sous forme de fichiers texte versionnables, exactement comme du code source.
Au lieu de cliquer dans une interface graphique pour creer un serveur ou une base de
donnees, on ecrit un fichier YAML ou JSON qui decrit ce que l'on veut, et un outil
s'occupe de le creer, modifier ou supprimer automatiquement.
Les avantages sont concrets et significatifs dans un contexte professionnel.
La reproductibilite permet de deployer exactement la meme infrastructure en dev, en
staging et en prod avec le meme fichier. On elimine les erreurs humaines liees a des
configurations manuelles differentes d'un environnement a l'autre.
La tracabilite est obtenue car l'infrastructure est dans un fichier texte versionnable
avec Git. On sait qui a modifie quoi, quand et pourquoi. Un historique complet des
changements est disponible.
L'automatisation est rendue possible car on peut integrer le deploiement dans un
pipeline CI/CD. A chaque merge sur la branche principale, l'infrastructure est mise
a jour automatiquement, sans intervention manuelle.
AWS CloudFormation est le service IaC natif d'AWS. Il prend un fichier template YAML
ou JSON en entree et gere le cycle de vie complet de l'infrastructure. Lors de la
creation, CloudFormation analyse les dependances entre ressources et les cree dans
le bon ordre. Par exemple, il cree d'abord le role IAM de la Lambda, puis la Lambda
elle-meme qui a besoin de ce role, puis l'API Gateway qui a besoin de la Lambda.
Lors d'une modification, CloudFormation calcule un change set (la difference entre
l'etat actuel et l'etat souhaite) et n'applique que les changements necessaires.
En cas d'erreur, CloudFormation effectue un rollback automatique pour revenir a
l'etat stable precedent.
Dans ce projet, notre `infrastructure/template.yaml` definit 13 ressources AWS
interconnectees deployees atomiquement en une seule operation.
---
### Question 2 - AWS Lambda et le modele Serverless vs Amazon EC2
AWS Lambda est un service de calcul qui execute du code en reponse a des evenements,
sans gestion de serveur. On fournit le code Python, on configure les permissions et
les variables d'environnement, et AWS s'occupe de tout le reste.
Avec EC2, on loue une machine virtuelle. On choisit sa taille, on installe un OS, on
configure un serveur web, on gere les mises a jour de securite, et on paye l'instance
24h/24 meme si elle ne traite aucune requete. C'est l'equipe qui est responsable de
maintenir le serveur en fonctionnement.
Avec Lambda, on ne paye qu'au moment ou le code s'execute, a la milliseconde. Quand
aucune donnee IoT n'arrive, la Lambda ne tourne pas et ne coute rien. Des que des
donnees arrivent, AWS demarre automatiquement autant d'instances que necessaire.
| Aspect | Lambda (Serverless) | EC2 (Instance virtuelle) |
|--------|---------------------|--------------------------|
| Provisionnement | Zero - AWS gere tout | Manuel : type, AMI, reseau |
| Facturation | A la milliseconde d'execution | A l'heure, meme au repos |
| Scalabilite | Automatique, instantanee | Auto Scaling Groups a configurer |
| Maintenance OS | Prise en charge par AWS | A la charge de l'equipe |
| Duree max d'execution | 15 minutes | Illimitee |
| Etat | Stateless (sans persistance) | Stateful possible |
Pour un use case IoT avec des capteurs qui envoient des donnees de facon sporadique,
Lambda est nettement plus adapte. EC2 serait gaspilleur car l'instance consommerait
des ressources meme quand aucun capteur ne transmet.
---
### Question 3 - L'interet d'un CDN CloudFront devant l'API Gateway pour l'IoT
Placer CloudFront devant l'API Gateway apporte plusieurs benefices essentiels pour
une infrastructure IoT mondiale.
La latence globale est reduite significativement. CloudFront dispose de plus de 400
Points of Presence repartis dans le monde entier. Quand un capteur installe en Asie
envoie ses donnees, la requete arrive d'abord au PoP CloudFront le plus proche en
Asie, qui etablit une connexion optimisee vers notre API en Europe. Le gain de latence
peut etre de 100 a 300 ms.
La protection contre les attaques est assuree par le fait que CloudFront absorbe le
trafic malveillant en bordure du reseau, avant qu'il n'atteigne l'infrastructure. On
peut egalement coupler CloudFront avec AWS WAF pour filtrer les requetes suspectes.
La stabilite des endpoints est garantie : si on reconstruit l'API Gateway, l'URL
CloudFront reste inchangee. Les capteurs IoT deployes sur le terrain n'ont pas besoin
d'etre reconfigures.
La reduction des couts est possible pour les routes GET grace au cache CloudFront.
Pour nos POST d'ingestion, le cache est desactive (TTL=0) car chaque requete est
unique et ne doit pas etre mise en cache.
---
### Question 4 - S3 comme Data Lake et DynamoDB comme Serving Layer
Dans une architecture Big Data, on distingue deux couches de stockage avec des roles
tres differents. Comprendre pourquoi on ne peut pas tout mettre dans une seule base
relationnelle est fondamental.
S3 comme Data Lake permet un stockage illimite a faible cout (quelques centimes par
Go par mois). Les donnees y sont conservees dans leur format original, sans
transformation, ce qui garantit qu'on peut toujours retraiter depuis la source si
les besoins analytiques evoluent. AWS Athena peut faire des requetes SQL directement
sur les fichiers JSON stockes dans S3, sans serveur. Apache Spark peut lire des
partitions S3 en parallele. Le partitionnement temporel applique permet a Athena de
ne scanner que les partitions pertinentes, reduisant les couts d'analyse.
DynamoDB comme Serving Layer garantit une latence inferieure a 10 millisecondes pour
les lectures par cle primaire. C'est precisement ce dont ont besoin les applications
temps reel. La table DynamoDB stocke des donnees deja agregees et calculees,
directement exploitables par une application de monitoring sans traitements supplementaires.
Une base relationnelle unique (PostgreSQL, MySQL) serait inadaptee pour plusieurs
raisons. Le modele transactionnel est inadapte a l'ingestion de millions de lignes
par heure. Le stockage est bien plus couteux que S3 pour des volumes importants. Les
SGBDR ne scalent pas horizontalement sans ingenierie complexe de sharding ou replication.
---
### Question 5 - Le modele de responsabilite partagee AWS applique a S3
Le modele de responsabilite partagee definit la frontiere entre ce qu'AWS securise et
ce que le client doit securiser. Cette frontiere change selon le type de service.
AWS est responsable de la securite de l'infrastructure physique et logicielle qui fait
tourner S3 : les datacenters, les serveurs physiques, les cables reseau, et le logiciel
S3 lui-meme. Si AWS a une faille dans son propre logiciel, c'est sa responsabilite.
Si un datacenter est affecte, c'est AWS qui gere la redondance et la recuperation.
Le client est responsable de ce qui concerne son utilisation de S3. Les politiques
d'acces (Bucket Policy, ACL, IAM) : c'est le client qui definit qui peut lire, ecrire
ou supprimer des objets dans ses buckets. Le chiffrement des donnees : par defaut S3
chiffre au repos avec SSE-S3, mais pour des donnees sensibles on peut choisir
SSE-KMS avec ses propres cles. La configuration du Block Public Access : si on active
accidentellement l'acces public sur un bucket contenant des donnees sensibles, c'est
la responsabilite du client. La gestion des identifiants : si les cles AWS IAM sont
compromises, c'est le client qui doit les revoquer.
Dans ce projet, nous appliquons ce modele en configurant BlockPublicAccess a true sur
le bucket de documentation, une Bucket Policy qui n'autorise que la distribution
CloudFront, et un role IAM pour la Lambda avec uniquement les permissions minimales.
---
### Question 6 - Static Website Hosting public vs CloudFront avec OAC
L'option Static Website Hosting de S3 permet d'exposer un bucket comme un site web
public. C'est pratique pour des tests, mais totalement inadapte pour une documentation
interne confidentielle.
Des qu'un bucket est en hebergement public, son URL est accessible par n'importe qui
sur Internet sans authentification. Des bots peuvent scanner et indexer le contenu.
Des concurrents peuvent acceder a des documents techniques confidentiels. L'URL S3
utilise HTTP par defaut, les donnees transitent en clair. Le bucket directement expose
n'a aucune protection contre les attaques DDoS.
Notre approche avec CloudFront et OAC est radicalement differente. Le bucket S3 est
entierement prive avec toutes les options Block Public Access activees. Une tentative
d'acces direct retourne immanquablement HTTP 403, meme en connaissant l'URL exacte.
La distribution CloudFront est configuree avec un Origin Access Control. L'OAC signe
chaque requete vers S3 avec AWS Signature V4. La Bucket Policy n'autorise que les
requetes signees par cette distribution CloudFront specifique identifiee par son ARN.
Quand un utilisateur ouvre l'URL CloudFront, CloudFront recoit la requete via HTTPS,
signe une nouvelle requete vers S3 avec SigV4, et S3 la retourne apres verification.
L'utilisateur n'a jamais acces direct au bucket. Des restrictions geographiques et
AWS WAF peuvent etre ajoutees pour renforcer encore la securite.
---
### Question 7 - Amazon CloudWatch pour superviser et deboguer une Lambda
Quand on developpe une application web classique, on peut se connecter au serveur et
lire les logs. Avec une architecture serverless, la Lambda s'execute dans un
environnement ephemere gere par AWS. CloudWatch est donc l'outil de diagnostic
incontournable car c'est le seul moyen de voir ce qui se passe a l'interieur.
Chaque invocation de la Lambda cree une entree dans CloudWatch Logs dans le groupe
/aws/lambda/<nom-de-la-fonction>. Tout ce que le code ecrit via print() est
automatiquement enregistre, sans aucune configuration supplementaire.
En plus des logs, CloudWatch collecte des metriques automatiquement : Invocations
(nombre total d'appels), Duration (temps d'execution), Errors (executions en echec),
Throttles (appels rejetes pour limite de concurrence). Ces metriques permettent de
configurer des CloudWatch Alarms pour envoyer des alertes automatiques.
Quand la Lambda leve une exception non geree via `raise`, le runtime Lambda la recoit,
marque l'invocation comme ERROR, enregistre le Traceback Python complet avec le
numero de ligne exact, et incremente la metrique Errors. L'API Gateway retourne
HTTP 502 a l'appelant.
Dans notre projet, nous utilisons traceback.print_exc() pour enrichir les logs dans
les erreurs gerees. Pour les erreurs internes relevees (Test 2 - ValueError),
l'exception est loguee par le global_exception_handler de FastAPI, puis relevee.
Mangum intercepte cette exception et retourne HTTP 500 de facon propre a API Gateway.
Cela signifie que la Lambda elle-meme ne "crashe" pas techniquement (elle retourne
une reponse valide), mais le stack trace Python complet est bien visible dans
CloudWatch Logs sous /aws/lambda/stchabodi-iot-ingestion pour le diagnostic.
---
### Question 8 - Pourquoi Lambda atteint ses limites avec 50 Go, et quelle alternative
Lambda est excellent pour traiter des evenements de petite taille en temps reel.
Mais ses contraintes techniques le rendent inadapte aux gros volumes.
La limite de duree d'execution est de 15 minutes. Lire 50 Go depuis S3, les parser
et les transformer prendrait bien plus de temps meme sur une machine puissante.
La memoire maximale est de 10 Go de RAM. Un fichier de 50 Go ne peut pas etre charge
en memoire. Il faudrait le traiter par morceaux, ce qui complexifie enormement le code.
Le payload HTTP maximal accepte par API Gateway est de 6 Mo. Un fichier de 50 Go ne
peut pas etre envoye via une requete HTTP classique.
L'espace de stockage temporaire /tmp est limite a 10 Go. Insuffisant pour materialiser
un fichier de 50 Go localement.
| Contrainte Lambda | Limite | Inadequation pour 50 Go |
|-------------------|--------|--------------------------|
| Duree max | 15 minutes | Traitement en 15 min impossible |
| RAM max | 10 Go | Fichier non chargeable en memoire |
| Payload HTTP | 6 Mo | Fichier non envoyable via POST |
| Stockage /tmp | 10 Go | Espace de travail insuffisant |
La solution recommandee est AWS Glue avec Apache Spark. Glue est un service ETL
serverless specifiquement concu pour traiter des volumes massifs. Spark distribue le
traitement sur plusieurs machines en parallele. Un fichier de 50 Go est automatiquement
decoupes en partitions traitees simultanement. Il n'y a pas de limite de duree ni de
taille de fichier.
Architecture recommandee :
```
[Fichier 50 Go depose dans S3]
         |
   (notification S3 Event)
         |
         v
[AWS Glue Job - Apache Spark]
   - Lecture du fichier en parallele
   - Transformation et nettoyage
   - Calcul des agregats
         |
    +----+----+
    |         |
    v         v
[S3 Parquet] [DynamoDB]
 (stockage   (metriques
  optimise)   temps reel)
```
Lambda reste pertinente pour les micro-batches de quelques Mo ou pour declencher des
traitements. AWS Glue prend le relais des que les volumes deviennent importants.
---
## Checklist de validation finale
Infrastructure et deploiement :
- [ ] Pile CloudFormation creee avec statut CREATE_COMPLETE (capture console CloudFormation)
- [ ] Les 2 URLs CloudFront recuperees dans les Outputs de la pile
- [ ] test_client.py configure avec la valeur de CloudFrontIngestionURL
Pipeline IoT (Test 1 - payload valide) :
- [ ] HTTP 201 recu en reponse au payload de 4 capteurs
- [ ] Fichier JSON present dans S3 sous raw-zone/year=.../month=.../ (capture console S3)
- [ ] Entree DynamoDB creee avec request_id, timestamp, s3_path, avg_temperature, error_count (capture DynamoDB)
Documentation technique (sous-systeme 2) :
- [ ] index.html uploade dans le bucket -tech-doc via la commande AWS CLI ci-dessus
- [ ] Acces direct via URL S3 retourne HTTP 403 Access Denied (capture navigateur)
- [ ] Acces via CloudFrontDocURL affiche la page HTML correctement (capture navigateur)
Monitoring CloudWatch :
- [ ] Log d'une execution reussie visible (capture Test 1 - sequence START->S3->DYNAMODB->END)
- [ ] Stack trace Python complet visible pour l'execution en echec (capture Test 2 - ValueError)
Rapport final :
- [ ] Toutes les captures d'ecran integrees dans le rapport
- [ ] Les 8 questions theoriques redigees et documentees
- [ ] Documentation convertie en PDF
- [ ] Dossier compresse en ZIP contenant : infrastructure/template.yaml, src/index.py, test_client.py, rapport PDF
---
## Preparation du ZIP pour la soumission
Structure attendue dans le ZIP :
```
devoir_final_stchabodi.zip
├── infrastructure/
│   └── template.yaml
├── src/
│   └── index.py
├── test_client.py
├── index.html
└── rapport_stchabodi.pdf
```
Commande PowerShell pour creer le ZIP depuis le dossier parent :
```bash
cd D:\Master_1\aws
Compress-Archive -Path ".\devoir_final\*" -DestinationPath ".\devoir_final_stchabodi.zip"
```
Pour convertir DOCUMENTATION.md en PDF :
- Visual Studio Code avec l'extension "Markdown PDF" (clic droit -> Export as PDF)
- Pandoc en ligne de commande : pandoc DOCUMENTATION.md -o rapport_stchabodi.pdf
- Copier le contenu dans Google Docs et exporter via Fichier -> Telecharger -> PDF
------
## Guide de deploiement avec AWS SAM CLI
Le projet utilise **AWS SAM CLI** (Serverless Application Model) pour construire et
deployer l'infrastructure, exactement comme dans le TP4. SAM emballe automatiquement
le code Python, gere le bucket S3 intermediaire, et orchestre le deploiement
CloudFormation en mode guide.
### Structure apres migration vers SAM
```
devoir_final/
├── infrastructure/
│   └── template.yaml       <- template SAM (Transform: AWS::Serverless-2016-10-31)
├── src/
│   ├── index.py            <- code source de la Lambda (reference par CodeUri)
│   └── requirements.txt    <- dependances Python (vide : boto3 est pre-installe)
├── Makefile                <- raccourcis make validate / build / deploy
├── test_client.py
├── index.html
└── DOCUMENTATION.md
```
La principale difference avec la version CloudFormation pure : le code de la Lambda
n est plus ecrit en inline dans le YAML. Il vit dans `src/index.py` et SAM s'occupe
de le packager lors du `sam build`.
---
### Etape A - Verifier l'installation de SAM CLI
```bash
sam --version
```
Reponse attendue : `SAM CLI, version 1.x.x`
Si SAM CLI n'est pas installe, suivez le guide officiel :
https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html
Verifiez aussi que Docker est installe et en cours d'execution (requis pour sam build) :
```bash
docker --version
```
> SAM CLI utilise Docker pour construire le package Lambda dans un environnement
> identique a celui de production AWS. Sans Docker, utilisez l'option `--use-container=false`
> si toutes vos dependances sont compatibles (ce qui est notre cas ici).
---
### Etape B - Valider le template
Avant de construire quoi que ce soit, on valide la syntaxe du template SAM/CloudFormation :
```bash
make validate
```
Equivalent direct :
```bash
sam validate --region eu-west-3 --template infrastructure/template.yaml --lint
```
Reponse attendue si tout est correct :
```
infrastructure/template.yaml is a valid SAM Template
```
Si une erreur apparait, le message indique precisement la ligne et la propriete
incorrecte. Corrigez avant de continuer.
---
### Etape C - Construire le package Lambda
`sam build` lit `infrastructure/template.yaml`, localise la fonction Lambda via
`CodeUri: ../src/`, installe les dependances de `src/requirements.txt`, puis
genere un artefact deployable dans `.aws-sam/build/`.
```bash
make build
```
Equivalent direct :
```bash
sam build --region eu-west-3 --template infrastructure/template.yaml
```
Sortie attendue :
```
Building codeuri: .../src/ runtime: python3.11 ...
Running PythonPipBuilder:ResolveDependencies
Running PythonPipBuilder:CopySource
Build Succeeded
Built Artifacts  : .aws-sam/build
Built Template   : .aws-sam/build/template.yaml
Commands you can use next
=========================
[*] Validate SAM template: sam validate
[*] Invoke Function: sam local invoke
[*] Deploy: sam deploy --guided
```
Le dossier `.aws-sam/build/` contient maintenant le code Python pret a etre uploade
sur AWS. Ce dossier est ignore par Git (il est dans `.gitignore`).
---
### Etape D - Premier deploiement (mode guide interactif)
Le premier deploiement utilise le mode `--guided` qui pose des questions et cree
le fichier `samconfig.toml` pour les deploiements suivants.
```bash
make deploy
```
Equivalent direct :
```bash
sam deploy --guided \
  --region eu-west-3 \
  --stack-name tp-final-iot-pipeline-stchabodi \
  --template-file .aws-sam/build/template.yaml \
  --no-fail-on-empty-changeset \
  --parameter-overrides Environment=stchabodi \
  --capabilities CAPABILITY_IAM
```
SAM posera les questions suivantes. Voici les reponses recommandees :
```
Configuring SAM deploy
======================
        Looking for config file [samconfig.toml] :  Not found
        Setting default arguments for 'sam deploy'
        =========================================
        Stack Name [sam-app]: tp-final-iot-pipeline-stchabodi
        AWS Region [eu-west-3]: eu-west-3
        Parameter Environment [stchabodi]: stchabodi
        #Shows you resources changes to be deployed and require a 'Y' to initiate deploy
        Confirm changes before deploy [y/N]: y
        #SAM needs permission to be able to create roles to connect to the resources in your template
        Allow SAM CLI IAM role creation [Y/n]: y
        #Preserves the state of previously provisioned resources when an operation fails
        Disable rollback [y/N]: N
        Save arguments to configuration file [Y/n]: y
        SAM configuration file [samconfig.toml]: samconfig.toml
        SAM configuration environment [default]: default
```
SAM va ensuite afficher le changeset et demander confirmation :
```
CloudFormation stack changeset
-----------------------------------------
Operation  LogicalResourceId      Type
-----------------------------------------
+ Add      S3BucketRaw            AWS::S3::Bucket
+ Add      S3BucketDoc            AWS::S3::Bucket
+ Add      DynamoDBTable          AWS::DynamoDB::Table
...
-----------------------------------------
Changeset created successfully.
Previewing CloudFormation changeset before deployment
======================================================
Deploy this changeset? [y/N]: y
```
Repondez `y`. Le deploiement demarre et prend 3 a 5 minutes.
---
### Etape E - Recuperer les Outputs (URLs CloudFront)
A la fin du deploiement, SAM affiche automatiquement les Outputs de la pile :
```
CloudFormation outputs from deployed stack
-----------------------------------------
Key    CloudFrontIngestionURL
Value  https://XXXXXXXXXXXXX.cloudfront.net/ingest
Key    CloudFrontDocURL
Value  https://YYYYYYYYYYYYY.cloudfront.net
-----------------------------------------
```
Notez ces deux URLs. Vous pouvez aussi les retrouver a tout moment avec :
```bash
aws cloudformation describe-stacks \
  --stack-name tp-final-iot-pipeline-stchabodi \
  --query 'Stacks[0].Outputs' \
  --output table \
  --region eu-west-3
```
> **Capture d'ecran requise :** les Outputs de la pile dans la console CloudFormation
> ou dans le terminal apres `sam deploy`.
---
### Etape F - Uploader la documentation dans S3
Une fois la pile deployee, uploadez la page de documentation dans le bucket prive :
```bash
aws s3 cp index.html s3://stchabodi-tech-doc/index.html \
  --content-type "text/html; charset=utf-8" \
  --region eu-west-3
```
---
### Etape G - Configurer et lancer les tests
Ouvrez `test_client.py`, remplacez `CLOUDFRONT_INGESTION_URL` par la valeur
recuperee dans les Outputs, puis lancez :
```bash
python test_client.py
```
Les trois tests (payload valide, corrompu, JSON invalide) s'executent dans l'ordre.
---
### Etape H - Deploiements suivants (apres une modification du code)
Apres avoir modifie `src/index.py` ou `infrastructure/template.yaml`, le cycle
est toujours : build puis deploy-update (pas besoin de `--guided` a nouveau).
```bash
make build
make deploy-update
```
SAM compare l'etat actuel de la pile avec les changements et n'applique que le delta.
---
### Etape I - Nettoyage en fin de TP
Pour supprimer la pile et toutes ses ressources AWS (evite les couts) :
```bash
make delete
```
Puis nettoyer les artefacts locaux :
```bash
make clean
```
> Attention : la suppression de la pile supprime aussi les buckets S3 seulement
> s'ils sont vides. Si des fichiers ont ete ingeres, videz d'abord le bucket :
> `aws s3 rm s3://stchabodi-iot-datalake --recursive`
---
### Recapitulatif des commandes SAM
| Commande make | Commande SAM equivalente | Quand l'utiliser |
|---------------|--------------------------|------------------|
| `make validate` | `sam validate --lint` | Verifier la syntaxe avant chaque build |
| `make build` | `sam build` | Apres chaque modification du code ou du template |
| `make deploy` | `sam deploy --guided` | Premier deploiement uniquement |
| `make deploy-update` | `sam deploy` | Tous les deploiements suivants |
| `make delete` | `aws cloudformation delete-stack` | Fin du TP / nettoyage |
| `make clean` | Suppression `.aws-sam/` | Nettoyer les artefacts locaux |

---

*Documentation produite dans le cadre du Devoir Final - Introduction a AWS, Master 1, Juin 2026*
