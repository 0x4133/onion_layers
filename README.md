# Visual ALM - Autonomous Language Model

A robust, interactive web application for conversing with local Ollama models through branching conversation trees. Experience AI conversations in a visual, tree-based interface that allows you to explore different conversation paths and branch from any point in your dialogue history.

## 🌟 Features

- **Visual Conversation Trees**: See your conversations as an interactive tree with branching paths
- **Branch from Any Point**: Click on any node to start a new conversation thread from that point
- **Local Ollama Integration**: Works with your local Ollama installation - no external API keys needed
- **Persistent Memory**: Conversations are saved automatically and persist across sessions
- **Responsive Design**: Works on desktop and mobile devices
- **Real-time Status**: Check Ollama connection status in real-time
- **Modern UI**: Beautiful, gradient-based interface with smooth animations
- **Error Handling**: Comprehensive error handling with helpful user feedback

## 🚀 Quick Start

### Prerequisites

1. **Python 3.8+** installed on your system
2. **Ollama** running locally on your machine

### Step 1: Install Ollama

First, install Ollama if you haven't already:

```bash
# On macOS (using Homebrew)
brew install ollama

# On Linux
curl -fsSL https://ollama.ai/install.sh | sh

# On Windows
# Download from https://ollama.ai/download
```

### Step 2: Start Ollama and Download a Model

```bash
# Start Ollama service
ollama serve

# In another terminal, download a model (e.g., Gemma 2B)
ollama pull gemma2:2b

# Or download the default model used by ALM
ollama pull gemma3:4b
```

### Step 3: Install ALM

```bash
# Clone the repository
git clone <repository-url>
cd onion_layers

# Create a virtual environment
python -m venv .venv

# Activate virtual environment
# On Linux/macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 4: Run the Application

```bash
# Start the web interface
python app.py

# Or start the CLI interface
python main.py
```

### Step 5: Open in Browser

Open your browser and navigate to: `http://localhost:5001`

## 🎯 Usage

### Web Interface

1. **Starting a Conversation**: Type your message in the input box at the bottom and press Enter or click Send
2. **Visual Tree**: Your conversation appears as a tree with green nodes (your messages) and blue nodes (AI responses)
3. **Branching**: Click on any node in the tree to start a new conversation thread from that point
4. **Controls**: 
   - **Reset Tree**: Clear all conversation history
   - **Center View**: Center the tree view
   - **Check Ollama**: Verify Ollama connection status
5. **Status Messages**: Real-time feedback appears in the messages area at the bottom left

### CLI Interface

```bash
python main.py
```

Type your messages and get responses. Type 'exit' to quit.

## ⚙️ Configuration

### Environment Variables

You can configure the application using environment variables:

```bash
# Web server configuration
export ALM_HOST=0.0.0.0          # Default: 0.0.0.0
export ALM_PORT=5001             # Default: 5001
export ALM_DEBUG=true            # Default: false

# Run the app
python app.py
```

### Ollama Model Configuration

Edit `main.py` to change the Ollama model:

```python
OLLAMA_MODEL = "gemma3:4b"  # Change to your preferred model
```

Available models (run `ollama list` to see installed models):
- `gemma2:2b` - Smaller, faster model
- `gemma3:4b` - Default model (good balance)
- `llama2` - Meta's LLaMA model
- `codellama` - Code-focused model
- `mistral` - Fast and capable model

## 🏗️ Project Structure

```
onion_layers/
├── app.py                 # Flask web application
├── main.py               # CLI interface and core Ollama integration
├── templates/
│   └── index.html        # Web interface template
├── static/
│   └── css/
│       └── style.css     # Application styles
├── requirements.txt      # Python dependencies
├── setup.py             # Package setup
├── test_alm.py          # Unit tests
├── test_web_app.py      # Web app tests
├── test_integration_ui.py # UI integration tests
└── README.md            # This file
```

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test files
pytest test_alm.py
pytest test_web_app.py

# Run UI integration tests (requires Selenium)
pytest test_integration_ui.py
```

### UI Testing

For UI tests, you'll need Chrome and ChromeDriver:

```bash
# Install ChromeDriver (macOS)
brew install chromedriver

# Install Selenium
pip install selenium

# Run UI tests
pytest test_integration_ui.py
```

## 🐛 Troubleshooting

### Common Issues

1. **Ollama Not Connected**
   - Ensure Ollama is running: `ollama serve`
   - Check if models are installed: `ollama list`
   - Verify Ollama is accessible: `curl http://localhost:11434/api/tags`

2. **Port Already in Use**
   - Change the port: `ALM_PORT=5002 python app.py`
   - Or kill the process using the port: `lsof -ti:5001 | xargs kill`

3. **Memory/Tree Issues**
   - Reset the tree using the "Reset Tree" button
   - Or delete the memory files: `rm alm_*.json`

4. **Dependencies Issues**
   - Update pip: `pip install --upgrade pip`
   - Reinstall requirements: `pip install -r requirements.txt --force-reinstall`

### Debug Mode

Enable debug mode for more detailed error messages:

```bash
ALM_DEBUG=true python app.py
```

### Logs

Check the log files for detailed error information:
- `alm_web.log` - Web application logs
- `alm.log` - CLI application logs

## 🔌 API Endpoints

The web application provides a REST API:

- `GET /` - Main web interface
- `GET /api/status` - System and Ollama status
- `POST /api/chat` - Send a chat message
- `GET /api/tree` - Get conversation tree
- `POST /api/tree/reset` - Reset conversation tree
- `GET /api/node/<id>` - Get specific node details
- `GET /api/health` - Health check

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and add tests
4. Run the test suite: `pytest`
5. Commit your changes: `git commit -am 'Add feature'`
6. Push to the branch: `git push origin feature-name`
7. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- [Ollama](https://ollama.ai/) for providing the local LLM infrastructure
- [Vis.js](https://visjs.org/) for the interactive network visualization
- [Flask](https://flask.palletsprojects.com/) for the web framework

## 🔮 Future Features

- [ ] Export conversation trees as images or PDFs
- [ ] Import/export conversation trees as JSON
- [ ] Search functionality within conversations
- [ ] Custom node styling and themes
- [ ] Multiple model support in same session
- [ ] Conversation templates and presets
- [ ] Integration with other LLM providers

---

**Enjoy exploring AI conversations with Visual ALM!** 🚀✨ 