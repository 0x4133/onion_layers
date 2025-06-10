# 🧅 Onion Layers - Visual ALM (Advanced Language Model) Tree Interface

A sophisticated web-based conversation tree interface for Ollama that visualizes your AI conversations as an interactive branching network. Create, explore, and manage complex conversation paths with advanced editing capabilities and ghost branch protection.

## ✨ Features

### 🌳 **Interactive Conversation Trees**
- **Visual Network**: See your entire conversation history as an interactive tree
- **Branch Navigation**: Click any node to continue conversations from that point
- **Real-time Updates**: Watch your conversation tree grow dynamically
- **Smart Layout**: Automatic network positioning with smooth animations

### ✏️ **Advanced Node Editing** *(NEW!)*
- **Edit Any Node**: Modify user messages and AI responses at any point
- **Ghost Branch Protection**: Preserve existing conversation paths when editing
- **Edit History Tracking**: Full audit trail of all changes made
- **Visual Indicators**: Edited nodes are clearly marked in the network
- **Safe Operations**: Intelligent handling of child nodes during edits

### 👻 **Ghost Branch Management** *(NEW!)*
- **Automatic Protection**: Create ghost branches when editing nodes with children
- **Branch Preservation**: Keep all conversation paths safe during modifications
- **Ghost Restoration**: Restore ghost branches back to the main tree
- **Ghost Cleanup**: Permanently delete unnecessary ghost branches
- **Visual Management**: Dedicated interface for ghost branch operations

### 💬 **Rich Conversation Features**
- **Markdown Support**: Full markdown rendering for AI responses
- **Multi-Model Support**: Switch between different Ollama models
- **Context Preservation**: Maintains full conversation history for context
- **Export/Import**: Save and restore entire conversation trees
- **Real-time Status**: Live Ollama connection monitoring

### 🎨 **Modern UI/UX**
- **Dark Theme**: Beautiful gradient-based dark interface
- **Responsive Design**: Works on all screen sizes
- **Smooth Animations**: Polished interactions and transitions
- **Keyboard Shortcuts**: Quick access to common actions
- **Modal Dialogs**: Professional editing interfaces

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- [Ollama](https://ollama.ai/) installed and running
- At least one Ollama model installed (e.g., `llama2`, `mistral`, `codellama`)

### Installation
```bash
# Clone the repository
git clone https://github.com/yourusername/onion_layers.git
cd onion_layers

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Ensure Ollama is running
ollama serve

# Start the web interface
python app.py
```

### First Steps
1. Open http://localhost:5000 in your browser
2. Verify Ollama connection (green status indicator)
3. Select your preferred model from the dropdown
4. Start your first conversation!

## 📖 User Guide

### Basic Conversation Flow
1. **Start Fresh**: Type your message and press Enter or click Send
2. **Branch Out**: Click any existing node to continue from that point
3. **Explore Paths**: Create multiple conversation branches to explore different topics
4. **Navigate**: Use the network view to visualize your conversation structure

### Node Editing Workflow
1. **Select Node**: Click any node in the conversation tree
2. **Edit Content**: Click the "✏️ Edit Node" button in the sidebar
3. **Choose Protection**: Decide whether to create ghost branches for existing children
4. **Make Changes**: Modify the user message or AI response
5. **Save**: Apply changes and see the updated tree

### Ghost Branch Management
1. **Automatic Creation**: Ghost branches are created when editing nodes with children
2. **View Ghosts**: Click "👻 Manage Branches" to see all ghost branches
3. **Restore Branches**: Bring ghost branches back to the main tree
4. **Clean Up**: Delete unnecessary ghost branches to keep things organized

### Advanced Features
- **Keyboard Shortcuts**:
  - `Ctrl/Cmd + Enter`: Send message
  - `Escape`: Close modals or clear input
- **Export/Import**: Save entire conversation trees with ghost branches
- **Model Switching**: Change AI models during conversations
- **Reset Tree**: Start completely fresh when needed

## 🔧 Configuration

### Environment Variables
```bash
# Ollama Configuration
OLLAMA_URL=http://localhost:11434    # Default Ollama URL
OLLAMA_MODEL=llama2                  # Default model

# Application Settings
FLASK_DEBUG=True                     # Enable debug mode
FLASK_HOST=0.0.0.0                  # Host interface
FLASK_PORT=5000                     # Port number
```

### File Structure
```
onion_layers/
├── app.py                          # Main Flask application
├── main.py                         # Core ALM functionality
├── templates/index.html            # Web interface template
├── static/
│   ├── css/style.css              # Application styles
│   └── js/app.js                  # Frontend JavaScript
├── alm_tree_memory.json           # Conversation tree storage
├── alm_ghost_branches.json        # Ghost branch storage
└── requirements.txt               # Python dependencies
```

## 🎯 Use Cases

### 📚 **Learning & Research**
- Explore different explanations of complex topics
- Branch conversations to ask follow-up questions
- Compare AI responses across different models
- Edit responses to explore alternative explanations

### 💻 **Development & Debugging**
- Test different approaches to coding problems
- Edit prompts to improve AI responses
- Branch conversations for different programming languages
- Preserve working solutions while exploring alternatives

### ✍️ **Creative Writing**
- Develop story branches and character arcs
- Edit dialogue to improve flow
- Explore different plot directions
- Preserve original ideas while experimenting

### 🔍 **Prompt Engineering**
- Test and refine prompts systematically
- Edit and compare different prompt variations
- Build libraries of effective prompts
- Track prompt evolution and effectiveness

## 🛠️ Technical Details

### Architecture
- **Backend**: Flask web framework with RESTful API
- **Frontend**: Vanilla JavaScript with vis.js for network visualization
- **Storage**: JSON-based file system for persistence
- **Communication**: Real-time AJAX for Ollama integration

### API Endpoints
```
GET  /api/status                    # Ollama status and models
GET  /api/tree                      # Get conversation tree
POST /api/chat                      # Send message
POST /api/tree/reset                # Reset conversation tree
GET  /api/tree/export               # Export tree data

# Editing Endpoints
POST /api/node/<id>/edit            # Edit node content
GET  /api/ghost-branches            # Get all ghost branches
POST /api/ghost-branches/<id>/restore  # Restore ghost branch
DELETE /api/ghost-branches/<id>     # Delete ghost branch
```

### Data Structure
```json
{
  "nodes": {
    "node_id": {
      "id": "uuid",
      "user_input": "User message",
      "ai_response": "AI response",
      "model_used": "llama2",
      "timestamp": "ISO datetime",
      "children": ["child_node_ids"],
      "edit_history": [
        {
          "timestamp": "ISO datetime",
          "ghost_created": "ghost_id"
        }
      ]
    }
  },
  "root_id": "first_node_id"
}
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Ollama](https://ollama.ai/) for the excellent local LLM platform
- [vis.js](https://visjs.org/) for the powerful network visualization
- [Flask](https://flask.palletsprojects.com/) for the web framework
- The open-source community for inspiration and tools

## 🐛 Troubleshooting

### Common Issues

**Ollama Connection Failed**
- Ensure Ollama is running: `ollama serve`
- Check if models are installed: `ollama list`
- Verify URL in configuration

**Ghost Branches Not Showing**
- Check browser console for JavaScript errors
- Ensure ghost branch file has correct permissions
- Restart the application

**Network Not Displaying**
- Clear browser cache and cookies
- Check if vis.js library is loading correctly
- Verify no JavaScript errors in console

**Edit Operations Failing**
- Ensure you have write permissions to the data directory
- Check that the node ID exists in the tree
- Verify no other processes are accessing the files

### Getting Help
- Open an issue on GitHub with detailed error information
- Include browser console logs and Python traceback
- Describe steps to reproduce the problem
- Mention your OS, Python version, and Ollama version

---

*Built with ❤️ for the AI conversation community* 