# Project Overview

This project is designed to facilitate automated interaction with project files through a series of defined actions and an agent system. It utilizes OpenAI's API to simulate a decision-making process for tasks such as reading and writing project files, listing files, and terminating sessions based on collected data.

## Key Components

### 1. `api_keys.py`

This file contains the essential API keys needed for authentication with external services like OpenAI. It stores these keys in a dictionary format for use across the project.

### 2. `readme_generator.py`

This is the core file of the project, containing the logic for generating responses using language models, managing actions, and evolving memory through an agent.

- **Classes and Functions**:
  - `Prompt`, `Goal`, `Action`, `Environment`: Define the structure and capabilities of the agent.
  - `Agent`: Manages the interaction loop, processing inputs, generating responses, and executing actions.
  - `generate_response`: A key function that queries the OpenAI API and returns generated content or tool invocations.

## Usage

To use this project, execute the `readme_generator.py` file which initializes the agent with predefined goals, such as reading files and writing to a README, and initiates the interaction loop.

## Goals

The agent operates with specific goals:
- **Gather Information**: Read each file in the project to understand its function.
- **Terminate**: After reading all files and extracting necessary data, the agent provides a concluding message through termination.

This system is designed to illustrate automated data processing and decision-making via natural language processing capabilities. It demonstrates the potential for advanced project management activities using AI-driven tools.