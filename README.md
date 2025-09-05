# LLMposter

A multiplayer guessing game where players try to identify AI-generated responses among human submissions.

## Features

- **Real-time multiplayer gameplay** using Socket.IO
- **AI response integration** with configurable prompts and models
- **Scoring system** with deception and detection points
- **Responsive web interface** that works on desktop and mobile
- **Automatic game flow** with timed phases and progression
- **Room-based sessions** for private games with friends

## Quick Start

### Development Server

The easiest way to run the development server:

```bash
make dev
```

Or manually with uv:

```bash
uv run python run_dev.py
```

The server will be available at http://localhost:8000

### Alternative Methods

**Using Gunicorn directly:**
```bash
uv run gunicorn --config gunicorn.conf.py --reload wsgi:app
```

**Using Flask development server (not recommended for Socket.IO):**
```bash
uv run python app.py
```

### Running Tests

```bash
make test
```

Or with uv:
```bash
uv run pytest tests/ -v
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

### Project Structure

```
├── app.py                 # Main Flask application
├── src/                   # Core game modules
│   ├── room_manager.py    # Room and player management
│   ├── game_manager.py    # Game logic and scoring
│   ├── content_manager.py # Prompt and content handling
│   └── error_handler.py   # Error handling and validation
├── templates/             # HTML templates
├── static/               # CSS, JavaScript, and assets
├── tests/                # Test suite
├── prompts.yaml          # Game content and AI responses
├── gunicorn.conf.py      # Production server configuration
└── run_dev.py           # Development server runner
```

### Configuration

The application uses environment variables for configuration:

- `PORT` - Server port (default: 8000)
- `FLASK_ENV` - Environment mode (development/production)
- `SECRET_KEY` - Flask secret key for sessions
- `PROMPTS_FILE` - Path to prompts YAML file (default: prompts.yaml)

### Adding Content

Edit `prompts.yaml` to add new prompts and AI responses:

```yaml
prompts:
  - id: "unique_id"
    prompt: "Your prompt text"
    model: "AI Model Name"
    response: "The AI's response to this prompt"
```

## Docker Deployment

### Quick Docker Setup

```bash
# Build and run with docker-compose
docker-compose up --build

# Or run in background
docker-compose up -d --build
```

The application will be available at http://localhost:8000

### Production Deployment

For production with nginx reverse proxy:

```bash
# Run with production profile (includes nginx)
docker-compose --profile production up -d --build
```

### Environment Configuration

Create a `.env` file to customize deployment:

```bash
# Server configuration
HOST_PORT=8000
FLASK_ENV=production
SECRET_KEY=your-secret-key-here

# Game settings
RESPONSE_TIME_LIMIT=180
GUESSING_TIME_LIMIT=120
RESULTS_DISPLAY_TIME=30
MAX_PLAYERS_PER_ROOM=8
MAX_RESPONSE_LENGTH=1000

# Production settings
LOG_LEVEL=info
```

### Manual Docker Build

```bash
# Build image
docker build -t llmpostor .

# Run container
docker run -p 8000:8000 -v ./prompts.yaml:/app/prompts.yaml:ro llmpostor
```

## Testing Framework

LLMpostor includes a comprehensive test suite using Vitest to ensure reliability and prevent regressions in the JavaScript frontend modules.

### Test Infrastructure
- **Modern testing framework** with native ES modules support and fast execution
- **jsdom environment** for DOM testing without browser overhead
- **230+ unit tests** covering all JavaScript modules
- **50+ integration tests** for cross-module scenarios and bug prevention
- **Coverage reporting** with 90% line coverage requirements

### Running Tests
```bash
# Install dependencies
npm install

# Run all tests
npm test

# Run tests with coverage report
npm run test:coverage

# Run tests in watch mode during development
npm run test:watch

# Run tests with UI (browser-based test runner)
npm run test:ui
```

### Test Organization
```
tests/
├── setup.js              # Global test setup and DOM mocking
├── helpers/
│   ├── testUtils.js      # Test utilities and helper functions
│   └── mockFactory.js    # Mock object factory for consistent mocking
├── unit/                 # Unit tests for individual modules
│   ├── GameStateManager.test.js
│   ├── EventManager.test.js
│   ├── UIManager.test.js
│   ├── SocketManager.test.js
│   ├── TimerManager.test.js
│   └── ToastManager.test.js
└── integration/          # Integration tests for cross-module scenarios
    └── critical-bugs.test.js
```

### Critical Bug Prevention
The test suite includes specific regression tests for bugs we've encountered:

1. **Double Initialization Bug**: Prevents UIManager from initializing twice
2. **Button State Race Condition**: Ensures response submitted state persists
3. **Response Filtering Bug**: Filters player's own response during voting
4. **Invalid Guess Index**: Sends correct filtered indices to server
5. **Phase State Corruption**: Handles rapid phase changes correctly

This testing framework transforms the previously "fragile" JavaScript codebase into a robust, maintainable system with high confidence in stability and correctness.

## Requirements

- Python 3.11+ (for local development)
- uv (for dependency management)
- Node.js 18+ (for JavaScript testing)
- Docker & Docker Compose (for containerized deployment)

## License

MIT License