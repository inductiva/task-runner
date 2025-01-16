DOCKER_COMPOSE_ENV_FILE=.env
UID=$$(id -u)
HOSTNAME:=$(shell uname -n)
TAG_DEV=dev
TAG_MAIN=main

DOCKER_COMPOSE_COMMAND=\
	HOSTNAME=$(HOSTNAME) docker compose \
	--env-file $(DOCKER_COMPOSE_ENV_FILE)

DOCKER_COMPOSE_COMMAND_TASK_RUNNER=\
	$(DOCKER_COMPOSE_COMMAND) \
	-p task-runner-$(UID) \
	-f docker-compose.yml

DOCKER_COMPOSE_COMMAND_TASK_RUNNER_CUDA=\
	$(DOCKER_COMPOSE_COMMAND) \
	-p task-runner-cuda-$(UID) \
	-f docker-compose.cuda.yml

DOCKER_COMPOSE_COMMAND_TASK_RUNNER_LITE=\
	$(DOCKER_COMPOSE_COMMAND) \
	-p task-runner-lite-$(UID) \
	-f docker-compose.lite.yml

.PHONY: %

%: help

help:
	@echo Run:
	@echo "  make task-runner-up: starts task-runner building from source"
	@echo "  make task-runner-lite-up: starts task-runner in lite mode (faster)"
	@echo "  make task-runner-cuda-up: starts task-runner with CUDA support"
	@echo "  make task-runner-down stops task-runner building from source"
	@echo "  make task-runner-lite-down stops task-runner in lite mode"
	@echo "  make task-runner-cuda-down stops task-runner with CUDA support"
	@echo Utils:
	@echo "  make lint-fix: run linter and fix issues"
	@echo "  make format: run formatter"
	@echo "  make style: run formatter and linter"


task-runner-up:
	$(DOCKER_COMPOSE_COMMAND_TASK_RUNNER) up --build

task-runner-lite-up:
	$(DOCKER_COMPOSE_COMMAND_TASK_RUNNER_LITE) up --build

task-runner-cuda-up:
	$(DOCKER_COMPOSE_COMMAND_TASK_RUNNER_CUDA) up --build

task-runner-down:
	$(DOCKER_COMPOSE_COMMAND_TASK_RUNNER) down

task-runner-lite-down:
	$(DOCKER_COMPOSE_COMMAND_TASK_RUNNER_LITE) down

task-runner-cuda-down:
	$(DOCKER_COMPOSE_COMMAND_TASK_RUNNER_CUDA) down

lint-fix:
	ruff check --config=./pyproject.toml --fix

format:
	yapf . --in-place --recursive --parallel --exclude=third_party


style: format lint-fix