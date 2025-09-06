# LLMpostor

***Fail the Turing Test. Win the game.***

A multiplayer guessing game where humans try to pass as robots.

<img width="856" height="662" alt="Image" src="https://github.com/user-attachments/assets/1d0ede70-1424-4b9a-b9b5-9634d0c13ad7" />

## Public servers

- [LLMpostor.com](https://LLMpostor.com)
- Add yours...

## Features

- **Real-time multiplayer gameplay** using Socket.IO
- **Scoring system** with deception and detection points
- **Automatic game flow** with timed phases and progression
- **Room-based sessions** for private games with friends
- **Random room joining** to find open games

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

## How to Play

1. **Join a Room**: Navigate to a room URL (e.g., `/my-room`) or create one from the home page
2. **Wait for Players**: Need at least 2 players to start a round
3. **Write Responses**: When a round starts, write a response that mimics the target AI model
4. **Guess the AI**: Try to identify which response was actually written by the AI
5. **Score Points**: Earn points for correct guesses and fooling other players

## Scoring

- **1 point** for correctly identifying the AI response
- **5 points** for each player who mistakes your response for the AI

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

Key environment variables:
- `PORT` - Server port (default: 8000)  
- `SECRET_KEY` - Flask secret key
- `PROMPTS_FILE` - Prompts file path (default: prompts.yaml)

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
