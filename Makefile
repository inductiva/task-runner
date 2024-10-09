DOCKER_COMPOSE_ENV_FILE=.env

DOCKER_COMPOSE_COMMAND=\
	docker compose \
	--env-file $(DOCKER_COMPOSE_ENV_FILE)

DOCKER_COMPOSE_COMMAND_TASK_RUNNER=\
	$(DOCKER_COMPOSE_COMMAND) \
	-p task-runner \
	-f docker-compose.yml

DOCKER_COMPOSE_COMMAND_TASK_RUNNER_LITE=\
	$(DOCKER_COMPOSE_COMMAND) \
	-p task-runner-lite \
	-f docker-compose.lite.yml

.PHONY: %

%: help

help:
	@echo Run:
	@echo "  make task-runner: starts task-runner"
	@echo "  make task-runner-lite: starts task-runner in lite mode (faster)"
	@echo "  make task-runner-down: stops task-runner"
	@echo "  make task-runner-lite-down stops task-runner in lite mode"
	@echo Utils:
	@echo "  make lint-fix: run linter and fix issues"
	@echo "  make format: run formatter"
	@echo "  make style: run formatter and linter"

task-runner-up:
	$(DOCKER_COMPOSE_COMMAND_TASK_RUNNER) up --build	

task-runner-lite-up:
	$(DOCKER_COMPOSE_COMMAND_TASK_RUNNER_LITE) up --build

task-runner-down:
	$(DOCKER_COMPOSE_COMMAND_TASK_RUNNER) down

task-runner-lite-down:
	$(DOCKER_COMPOSE_COMMAND_TASK_RUNNER_LITE) down

lint-fix:
	ruff check --config=./pyproject.toml --fix

format:
	yapf . --in-place --recursive --parallel --exclude=third_party


style: format lint-fix