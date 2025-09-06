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

Run all tests (Python + JavaScript):
```bash
make test
```

Or run specific test suites:
```bash
make test-python    # Run Python tests only
make test-js        # Run JavaScript tests only
```

Manual test commands:
```bash
uv run pytest tests/ -v    # Python tests
npm run test:run           # JavaScript tests
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
├── static/js/            # Frontend JavaScript modules
│   ├── game-modular.js   # Modular entry point (current)
│   ├── game.js          # Original monolithic file (legacy)
│   ├── home.js          # Home page functionality
│   └── modules/         # Modular JavaScript architecture
│       ├── SocketManager.js     # WebSocket communication
│       ├── GameStateManager.js  # State management
│       ├── TimerManager.js      # Timer functionality
│       ├── ToastManager.js      # Notifications
│       ├── UIManager.js         # DOM manipulation
│       ├── EventManager.js      # Business logic coordination
│       └── GameClient.js        # Main coordinator
├── templates/             # HTML templates
├── tests/                # Test suite (Python backend + JavaScript frontend)
├── docs/                 # Documentation
│   └── FRONTEND_ARCHITECTURE.md  # Detailed frontend architecture docs
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
- **Modern testing framework** using Vitest with native ES modules support and fast execution
- **jsdom environment** for DOM testing without browser overhead  
- **190 JavaScript tests** covering all frontend modules (7 test files, 190 individual tests)
- **Comprehensive Python test suite** with 16 test files for backend functionality
- **Coverage reporting** and regression prevention for critical bugs

### Running Tests

**Using Makefile (Recommended):**
```bash
make install       # Install all dependencies (Python + JavaScript)
make test          # Run all tests (Python + JavaScript)
make test-python   # Run Python tests only  
make test-js       # Run JavaScript tests only
```

**Manual JavaScript Testing:**
```bash
npm install        # Install JavaScript dependencies
npm test          # Run all JavaScript tests
npm run test:coverage  # Run tests with coverage report
npm run test:watch    # Run tests in watch mode during development
npm run test:ui      # Run tests with UI (browser-based test runner)
```

### Test Organization
```
tests/
├── setup.js              # Global test setup and DOM mocking
├── helpers/
│   ├── testUtils.js      # Test utilities and helper functions
│   └── mockFactory.js    # Mock object factory for consistent mocking
├── unit/                 # Unit tests for individual modules (JavaScript + Python)
│   ├── GameStateManager.test.js  # JavaScript frontend tests
│   ├── EventManager.test.js
│   ├── UIManager.test.js
│   ├── SocketManager.test.js
│   ├── TimerManager.test.js
│   ├── ToastManager.test.js
│   ├── test_game_manager.py      # Python backend tests
│   ├── test_room_manager.py
│   ├── test_content_manager.py
│   └── test_error_handler.py
├── integration/          # Integration tests for cross-module scenarios
│   ├── critical-bugs.test.js     # JavaScript bug prevention tests
│   ├── test_automatic_game_flow.py
│   ├── test_guessing_phase.py
│   ├── test_round_mechanics.py
│   └── test_scoring_and_results.py
└── e2e/                  # End-to-end tests
    └── test_client_error_recovery.py
```

### Critical Bug Prevention
The test suite includes specific regression tests for bugs we've encountered:

1. **Double Initialization Bug**: Prevents UIManager from initializing twice
2. **Button State Race Condition**: Ensures response submitted state persists
3. **Response Filtering Bug**: Filters player's own response during voting
4. **Invalid Guess Index**: Sends correct filtered indices to server
5. **Phase State Corruption**: Handles rapid phase changes correctly

## Frontend Architecture

The frontend has been refactored from a monolithic 1,417-line JavaScript file into a clean, modular architecture with 7 focused modules. This provides better maintainability, extensibility, and testability while maintaining 100% functional parity.

For detailed documentation about the modular frontend architecture, see [`docs/FRONTEND_ARCHITECTURE.md`](docs/FRONTEND_ARCHITECTURE.md).

### Key Benefits of Modular Architecture

- **Maintainability**: Each module has a single, clear responsibility
- **Extensibility**: Easy to add new features without modifying existing code  
- **Testability**: Modules can be unit tested individually (190 tests with 100% pass rate)
- **Reusability**: Components can be reused across different contexts
- **Debugging**: Clear separation makes issues easier to trace and fix
- **Performance**: Better resource management and optimized DOM operations

## Requirements

- Python 3.11+ (for local development)
- uv (for dependency management)
- Node.js 18+ (for JavaScript testing)
- Docker & Docker Compose (for containerized deployment)

## License

MIT License