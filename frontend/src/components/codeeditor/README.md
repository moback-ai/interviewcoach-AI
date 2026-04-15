# Code Editor Component

A professional, full-featured code editor with compilation and testing capabilities built for the Interview Coach platform.

## Features

### 🎯 **Core Functionality**
- **Multi-language Support**: JavaScript, Python, Java, C++, C#, Go, Rust, TypeScript
- **Real-time Compilation**: Execute code instantly with live output
- **Syntax Highlighting**: Full Monaco Editor integration with VS Code features
- **Error Detection**: Comprehensive error reporting and debugging
- **Test Execution**: Built-in testing framework support

### 🛠️ **Editor Features**
- **Monaco Editor**: Same editor that powers VS Code
- **Auto-completion**: Intelligent code suggestions
- **Multiple Themes**: Dark, Light, and High Contrast modes
- **Font Size Control**: Adjustable editor font size
- **Keyboard Shortcuts**: 
  - `Ctrl/Cmd + Enter`: Run code
  - `Ctrl/Cmd + Shift + Enter`: Run tests
- **Code Formatting**: Auto-format on paste and type

### 🚀 **Execution Features**
- **Secure Execution**: Sandboxed code execution with timeouts
- **Resource Limits**: 10-second execution timeout
- **Multiple Output Tabs**: Output, Errors, and Test Results
- **Real-time Status**: Live execution status and timing
- **Error Parsing**: Intelligent error message formatting

### 💾 **File Management**
- **Save/Load**: Export and import code as JSON
- **Auto-save**: Automatic localStorage persistence
- **Share**: Generate shareable links
- **Reset**: Quick code reset functionality

## Components

### `CodeEditor.jsx`
Main editor component with Monaco Editor integration.

**Props:**
- `initialCode`: Starting code content
- `language`: Programming language (default: 'javascript')
- `onCodeChange`: Callback for code changes
- `onRun`: Callback for code execution
- `onTest`: Callback for test execution
- `isRunning`: Execution status
- `output`: Execution output
- `errors`: Error messages
- `testResults`: Test execution results
- `executionTime`: Execution duration in milliseconds

### `OutputPanel.jsx`
Output display component with tabbed interface.

**Features:**
- **Output Tab**: Display program output
- **Errors Tab**: Show compilation and runtime errors
- **Tests Tab**: Display test results and coverage
- **Collapsible**: Minimize/maximize output panel
- **Real-time Updates**: Live status indicators

### `CodeEditorPage.jsx`
Main page component integrating all features.

**Features:**
- **Full-screen Layout**: Optimized for coding
- **Header Controls**: Save, load, share, reset
- **Split Layout**: Editor and output side-by-side
- **Quick Actions**: One-click run and test buttons

## Supported Languages

| Language | Extension | Compiler/Interpreter |
|----------|-----------|---------------------|
| JavaScript | `.js` | Node.js |
| Python | `.py` | Python 3 |
| Java | `.java` | javac + java |
| C++ | `.cpp` | g++ |
| C# | `.cs` | dotnet |
| Go | `.go` | go run |
| Rust | `.rs` | rustc |
| TypeScript | `.ts` | ts-node |

## Backend Integration

### API Endpoint: `/api/execute`

**Request:**
```json
{
  "code": "console.log('Hello World');",
  "language": "javascript",
  "testMode": false
}
```

**Response:**
```json
{
  "success": true,
  "output": "Hello World\n",
  "errors": "",
  "testResults": null
}
```

### Security Features
- **Timeout Protection**: 10-second execution limit
- **Resource Isolation**: Temporary directory execution
- **Error Handling**: Comprehensive error catching
- **Cleanup**: Automatic temporary file removal

## Usage

### Basic Usage
```jsx
import CodeEditor from '@/components/codeeditor/CodeEditor';

function MyComponent() {
  const [code, setCode] = useState('');
  const [output, setOutput] = useState('');
  
  const handleRun = async (code, language) => {
    // Execute code via API
    const response = await fetch('/api/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, language })
    });
    const result = await response.json();
    setOutput(result.output);
  };

  return (
    <CodeEditor
      initialCode={code}
      onCodeChange={setCode}
      onRun={handleRun}
      output={output}
    />
  );
}
```

### Full Page Integration
```jsx
import CodeEditorPage from '@/pages/CodeEditorPage';

// Add to your routes
<Route path="/code-editor" element={<CodeEditorPage />} />
```

## Customization

### Themes
The editor supports three built-in themes:
- `vs-dark`: Dark theme (default)
- `vs-light`: Light theme
- `hc-black`: High contrast theme

### Language Configuration
Add new languages by extending the `languages` array in `CodeEditor.jsx`:

```javascript
const languages = [
  { value: 'javascript', label: 'JavaScript', extension: '.js' },
  { value: 'python', label: 'Python', extension: '.py' },
  // Add your language here
  { value: 'php', label: 'PHP', extension: '.php' }
];
```

### Backend Language Support
Add execution support in `backend/app.py`:

```python
def execute_php(code, temp_dir, test_mode=False):
    """Execute PHP code"""
    try:
        code_file = os.path.join(temp_dir, 'main.php')
        with open(code_file, 'w') as f:
            f.write(code)
        
        result = subprocess.run(
            ['php', code_file],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=temp_dir
        )
        
        return {
            'success': result.returncode == 0,
            'output': result.stdout,
            'errors': result.stderr if result.returncode != 0 else '',
            'testResults': None
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'PHP execution failed: {str(e)}'
        }
```

## Performance Considerations

- **Lazy Loading**: Monaco Editor loads only when needed
- **Debounced Updates**: Code changes are debounced to prevent excessive API calls
- **Memory Management**: Automatic cleanup of temporary files
- **Resource Limits**: Execution timeouts prevent infinite loops

## Browser Support

- **Modern Browsers**: Chrome 80+, Firefox 75+, Safari 13+, Edge 80+
- **WebAssembly**: Required for Monaco Editor
- **Local Storage**: Used for code persistence

## Security Notes

⚠️ **Important Security Considerations:**

1. **Code Execution**: All code runs in subprocess with timeouts
2. **File System**: Temporary directories are automatically cleaned
3. **Resource Limits**: Memory and CPU usage are limited
4. **Input Validation**: All inputs are validated before execution
5. **Error Sanitization**: Error messages are sanitized before display

## Troubleshooting

### Common Issues

1. **Monaco Editor Not Loading**
   - Check browser console for errors
   - Ensure WebAssembly is supported
   - Verify network connectivity

2. **Code Execution Fails**
   - Check backend server is running
   - Verify language compilers are installed
   - Check API endpoint configuration

3. **Syntax Highlighting Issues**
   - Ensure language is supported
   - Check Monaco Editor language configuration
   - Verify file extensions match

### Debug Mode
Enable debug logging by setting:
```javascript
localStorage.setItem('codeEditor_debug', 'true');
```

## Future Enhancements

- [ ] **Docker Integration**: Containerized execution for better security
- [ ] **Collaborative Editing**: Real-time multi-user editing
- [ ] **Version Control**: Git integration for code management
- [ ] **Advanced Testing**: Jest, pytest, JUnit integration
- [ ] **Code Templates**: Pre-built code snippets
- [ ] **Performance Profiling**: Execution time and memory analysis
- [ ] **AI Code Suggestions**: Intelligent code completion
- [ ] **Debugging Tools**: Breakpoints and step-through debugging