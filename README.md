# LLMpostor

***Fail the Turing Test. Win the game.***

A multiplayer guessing game where humans try to pass as robots.

<img width="856" height="662" alt="Image" src="https://github.com/user-attachments/assets/1d0ede70-1424-4b9a-b9b5-9634d0c13ad7" />

## Public servers

- [LLMpostor.com](https://LLMpostor.com)
- Add yours...

## How to Play

1. **Join a Room**: Navigate to a room URL (e.g., `/my-room`) or create one from the home page
2. **Wait for Players**: Need at least 2 players to start a round
3. **Write Responses**: When a round starts, write a response that mimics the target AI model
4. **Guess the AI**: Try to identify which response was actually written by the AI
5. **Score Points**: Earn 1 point for correctly guessing the AI response and 5 points when another player guesses your response is the AI

## Philosophy

LLMpostor is a social game for a wide audience—from AI enthusiasts to AI skeptics to folks that think it's pronounced "A1". The core of the game is simple: **fail the Turing Test, win the game.** But beneath this simple premise lies a deeper purpose: to help people become more discerning directors and consumers of AI by honing their ability to distinguish between human and AI-generated content.

### Learning by Impersonation

The most effective way to understand a system is to try to replicate it. In LLMpostor, players don't just passively consume AI-generated content; they actively try to *think* and *write* like an LLM. This process of impersonation is a powerful learning tool. It forces players to confront the subtle nuances of AI-generated text, from its sterile tone and occasional logical gaps to its help inducing creativity and hidden biases. By trying to mimic an LLM, players develop a more intuitive understanding of how these models work, what they do well, and where they fall short.

### Exposing Hidden Biases

The prompts in LLMpostor are crafted to be fun and engaging, but they also serve an educational purpose. Many prompts are designed to probe the "jagged edge" of AI capabilities, using ambiguous questions, logical riddles, and creative challenges to see where the models excel and where they struggle.

More importantly, the prompts are designed to reveal the hidden biases that are often present in LLMs. For example, a prompt asking for names of "senior engineers" might elicit a list of predominantly Western names from an AI model. There are *many* dimensions of bias in the training data. The developers of these models address some, ignore others, and are completely ignorant of most. By exposing these biases in a playful context, LLMpostor encourages players to think critically about the AI-generated content they encounter.

### Developed with AI

LLMpostor is not just a game *about* human AI interactions; it's also a product *of* human AI interactions. The initial MVP was developed by a human with the help of [Kiro](https://kiro.dev/), and subsequent (and very necessary) refactoring and feature development have been assisted by [Claude Code](https://www.anthropic.com/claude-code) and [Gemini](https://codeassist.google/). If you notice any bugs please blame the AI and not the human that naively hit merge.

### An Open and Evolving Platform

LLMpostor is an open-source project, and we welcome contributions from the community. While we appreciate help with feature development, our primary goal is to build a community of content creators. We envision a future where experts in various fields-from medicine and law to music and art-can create their own prompt packs to explore the intersection of AI and their domain of expertise.

We are committed to ensuring that LLMpostor is a safe and inclusive space for all players. To that end, we have established the following initial guidelines for prompt creation:

*   **Promote Critical Thinking:** Prompts should encourage players to think critically about AI, its capabilities, and its limitations. They should spark curiosity and conversation, not just test for right or wrong answers.
*   **Avoid Harmful Stereotypes:** While a core goal is to expose biases in AI, prompts must be crafted to do so without perpetuating harmful stereotypes or creating a hostile environment for any group of people.
*   **Respect Privacy:** Prompts must not ask for or encourage the sharing of personal or sensitive information.
*   **Be Original and Creative:** We encourage the community to create original and creative prompts that are not only educational but also fun and engaging. We are very aware that as an open source project, these prompts will be ingested by the next generation of models. So we will need consistent creativity from meat machines to keep the game interesting and useful.

These guidelines are a starting point, and we welcome feedback and suggestions.

## Features

- **Real-time multiplayer gameplay** using Socket.IO
- **Scoring system** with deception and detection points
- **Automatic game flow** with timed phases and progression
- **Room-based sessions** for private games with friends
- **Random room joining** to find open games

## Architecture

LLMpostor features a modern, modular architecture:

### Backend
- **Service Container**: Dependency injection with singleton/transient lifecycle management
- **Configuration Factory**: Type-safe configuration with environment-specific settings
- **Performance Optimizations**: Multi-level caching, database optimization, payload compression
- **Reliability Features**: Connection recovery, error handling, metrics collection

### Frontend  
- **Event-Driven Architecture**: Modular JavaScript with EventBus communication
- **Performance Enhancements**: Asset loading optimization, memory management, DOM caching
- **Modular Design**: 7 specialized modules (GameClient, SocketManager, UIManager, etc.)

For detailed frontend architecture, see [`docs/FRONTEND_ARCHITECTURE.md`](docs/FRONTEND_ARCHITECTURE.md).

## Quick Start

### Development Server

The easiest way to run the development server:

```bash
make dev
```

The server will be available at http://localhost:8000

### Running Tests

Run all tests (Python + JavaScript):
```bash
make test
```

Or run specific test suites:
```bash
make test-python    # Run Python tests only
make test-js        # Run JavaScript tests only
```

## Development

### Adding Content

Edit `prompts.yaml` to add new prompts and AI responses:

```yaml
prompts:
  - id: "unique_id"
    prompt: "Your prompt text"
    model: "AI Model Name"
    response: "The AI's response to this prompt"
```

### Configuration

The application uses a Configuration Factory system with type-safe settings:

**Core Settings:**
- `PORT` - Server port (default: 8000)  
- `SECRET_KEY` - Flask secret key (required in production)
- `PROMPTS_FILE` - Prompts file path (default: prompts.yaml)
- `MAX_PLAYERS_PER_ROOM` - Maximum players per room (default: 8)
- `RESPONSE_TIME_LIMIT` - Response phase duration in seconds (default: 180)
- `GUESSING_TIME_LIMIT` - Guessing phase duration in seconds (default: 120)

**Performance Settings:**
- `CACHE_TTL` - Cache time-to-live in seconds (default: 3600)
- `MAX_RESPONSE_LENGTH` - Maximum response length (default: 500)

### Environment Configuration

For production deployments, copy `.env.example` to `.env` and customize as needed.

## Roadmap

 - Add more prompts
 - Better theme
 - Multiple responses for each LLM prompt
 - Scripts to generate prompt responses

## Requirements

- Python 3.11+ (for local development)
- uv (for dependency management)
- Node.js 18+ (for JavaScript testing)
- Docker & Docker Compose (for containerized deployment)
