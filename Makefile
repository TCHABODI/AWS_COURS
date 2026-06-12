.PHONY: validate build build-no-docker deploy deploy-update delete clean

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ENVIRONMENT  = stchabodi
AWS_REGION   = eu-west-3
TEMPLATE     = infrastructure/template.yaml
STACK_NAME   = tp-final-iot-pipeline-$(ENVIRONMENT)

# ---------------------------------------------------------------------------
# Validation du template CloudFormation/SAM
# ---------------------------------------------------------------------------
validate:
	sam validate --region $(AWS_REGION) --template $(TEMPLATE) --lint

# ---------------------------------------------------------------------------
# Construction du package Lambda (src/index.py -> .aws-sam/build/)
# Necessite Docker en cours d'execution
# ---------------------------------------------------------------------------
build:
	sam build --region $(AWS_REGION) --template $(TEMPLATE)

# Construction sans Docker (packages Python purs : fastapi/mangum ne compilent pas)
# A utiliser si Docker n'est pas disponible
build-no-docker:
	sam build --region $(AWS_REGION) --template $(TEMPLATE) --use-container=false

# ---------------------------------------------------------------------------
# Premier deploiement interactif (cree samconfig.toml)
# ---------------------------------------------------------------------------
deploy:
	sam deploy --guided \
		--region $(AWS_REGION) \
		--stack-name $(STACK_NAME) \
		--template-file .aws-sam/build/template.yaml \
		--no-fail-on-empty-changeset \
		--parameter-overrides Environment=$(ENVIRONMENT) \
		--capabilities CAPABILITY_IAM

# ---------------------------------------------------------------------------
# Mises a jour suivantes (utilise samconfig.toml existant)
# ---------------------------------------------------------------------------
deploy-update:
	sam deploy \
		--region $(AWS_REGION) \
		--stack-name $(STACK_NAME) \
		--template-file .aws-sam/build/template.yaml \
		--no-fail-on-empty-changeset \
		--parameter-overrides Environment=$(ENVIRONMENT) \
		--capabilities CAPABILITY_IAM

# ---------------------------------------------------------------------------
# Suppression de la pile et de toutes ses ressources AWS
# ---------------------------------------------------------------------------
delete:
	aws cloudformation delete-stack \
		--stack-name $(STACK_NAME) \
		--region $(AWS_REGION)

# ---------------------------------------------------------------------------
# Nettoyage des artefacts locaux (compatible Linux/macOS/Windows Git Bash)
# ---------------------------------------------------------------------------
clean:
	rm -rf .aws-sam/ 2>/dev/null; true
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; true
	find . -type f -name "*.pyc" -delete 2>/dev/null; true
